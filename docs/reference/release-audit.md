# Release and guidance audit — 5 November 2026

[Documentation](../README.md) · [← Overview](../../README.md) · [Setup guide](../start/install.md)


This historical audit records the selected agentgateway + SQLite stack and upstream release observations. The existing gateway, model and NVIDIA inference-container pins are current within the selected release channels. No runtime upgrade is needed for those three artifacts.

## Verified release selection

| Component | Current release checked | Package decision |
|---|---|---|
| agentgateway | 1.7.0, published 27 October 2026 | Retain the existing immutable image digest; latest stable upstream release |
| NVIDIA vLLM container | 26.10-py3 | Official registry tag resolves exactly to the existing image digest |
| NVIDIA Qwen3.8-27B-NVFP4 | Main revision `482ca0f3832238542f8f5295dde86b5f22711d80` | Matches the existing pinned model revision |
| NVIDIA Pyxis | 0.24.0 | Current upstream reference for site integration; installation on site not inspected |
| NVIDIA Enroot | 4.2.1 | Current upstream reference for site integration; installation on site not inspected |
| OpenCode | 1.19.5 | Current upstream client reference; not a newly validated end-to-end client run |

Release sources: [agentgateway](https://github.com/agentgateway/agentgateway/releases/tag/v1.7.0), [NVIDIA vLLM index](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/index.html), [model metadata](https://huggingface.co/api/models/nvidia/Qwen3.8-27B-NVFP4), [Pyxis](https://github.com/NVIDIA/pyxis/releases/tag/v0.24.0), [Enroot](https://github.com/NVIDIA/enroot/releases/tag/v4.2.1), [OpenCode](https://github.com/anomalyco/opencode/releases/tag/v1.19.5). Machine-readable release observations are in [release-audit.json](../../evidence/release-audit.json).

The registry resolution of `nvcr.io/nvidia/vllm:26.10-py3` is `sha256:0a0de9362545e3e062750bec4ad4f722422a04a81182b5258a7deda4325e9313`, matching `versions.json` and the serving templates. NVIDIA's [26.10 release notes](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/rel-26-10.html) identify vLLM 0.31.0 and CUDA 13.4.3, and describe Qwen3.8 caches for RTX PRO 6000. The installed Python version string has a development suffix because it is NVIDIA's packaged build; it does not mean this package uses a floating nightly image.

Upstream vLLM is a different release channel: its latest final semantic-version release observed here is [0.32.0](https://github.com/vllm-project/vllm/releases/tag/v0.32.0). Its GitHub `releases/latest` endpoint currently returns `v0.33.0rc3` despite `prerelease:false`. That release-candidate name is not selected as a production default. This package deliberately uses the current NVIDIA container and its supplied CUDA, PyTorch and vLLM together; it does not independently replace packages inside that container. Therefore, “current NVIDIA container stack” is accurate; “newest upstream version of every dependency” is not.

## What is NVIDIA guidance, and what is a site choice?

- NVIDIA's [Dynamo gateway guide](https://docs.nvidia.com/dynamo/kubernetes/installation/gateway-api-inference-extension) recommends agentgateway for a focused gateway when the Kubernetes cluster is not already standardized on Istio. This supports the gateway selection, but the recommendation's documented scope is Dynamo/Kubernetes. Our standalone Slurm combination is an adaptation, not an NVIDIA-certified blueprint.
- NVIDIA's [model card](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4) uses vLLM, FP8 E4M3 KV cache, the `qwen3` reasoning parser, the `qwen3_coder` tool parser and chunked prefill. The sample follows those serving choices. The card's example uses four tensor-parallel devices and higher concurrency; our one-MIG target instead uses TP=1, concurrency=1, conservative memory and staged context qualification. These are explicit capacity adaptations, not copied performance guarantees.
- [Pyxis](https://github.com/NVIDIA/pyxis) and [Enroot](https://github.com/NVIDIA/enroot) are NVIDIA projects used by the Slurm template. The administrator must match their installed versions and plugin build to the site's Slurm release. Their latest release numbers are references, not evidence that the cluster has been upgraded or that an arbitrary plugin binary is ABI-compatible.
- Existing MIG devices remain owned by Slurm allocations and device cgroups, following [Slurm MIG guidance](https://slurm.schedmd.com/gres.html#MIG_Management). The sample never repartitions a shared GPU or substitutes root access for an allocation.
- SQLite, hybrid configuration storage, hashed virtual keys, budgets and the protected admin UI follow [agentgateway's own documentation](https://agentgateway.dev/docs/standalone/latest/documentation/setup/database/). SQLite is the selected single-instance storage backend, not a separate NVIDIA database recommendation.

NVIDIA's NVFP4 MoE-specific backend guidance must not be applied to a different model merely because both use Blackwell. This package's 27B checkpoint and its parsers/settings are qualified separately. No unrelated Dynamo, NIM, Kubernetes or service-mesh layer is required by this single-MIG design.

## Compatibility and update rule

Use the latest applicable stable vendor release that passes this deployment's acceptance tests, then pin its image digest and model revision. Keep the published vendor container dependencies together. Recheck this audit at installation and each planned upgrade; it is a dated observation, not a perpetual latest-version guarantee. No background updater is enabled.

The prototype driver is 595.112.07, an observed working version, not a verified latest/recommended B200 driver. The administrator must select a currently supported driver for the B200, OS and container using the [CUDA compatibility guide](https://docs.nvidia.com/deploy/cuda-compatibility/) and the NVIDIA container release notes. The site's driver, Slurm, Open OnDemand, container runtime and host patches cannot be certified remotely without the site inventory. Do not upgrade the cluster stack solely to match a higher version number without compatibility checks.

SQLite is supplied within the pinned agentgateway image; this audit did not independently certify its embedded library as the latest SQLite release. Persistent local storage, backup/restore and a single gateway instance remain the design constraints.

No runtime configuration or model parameters changed during this audit. The existing 26-check gateway evidence remains the executed baseline. Actual B200 MIG, Slurm integration, 200K context and the site's full OpenCode workflow remain acceptance work as documented in [validation record](validation.md).
