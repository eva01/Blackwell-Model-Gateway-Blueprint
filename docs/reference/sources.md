# Primary references and provenance

[Documentation](../README.md) · [← Overview](../../README.md) · [Setup guide](../start/install.md)


Reviewed 5 November 2026. URLs may describe newer releases later; the runnable sample pins agentgateway 1.7.0 and the recorded vLLM/model artifacts in [versions.json](../../versions.json).

For the current-release checks, exact NVIDIA recommendation scope and compatibility decisions, see [release audit](release-audit.md).

| Area | Primary source | Use in this sample |
|---|---|---|
| Agent defaults | [Official Qwen API guidance](https://huggingface.co/Qwen/Qwen3.8-27B#api-usage) | Thinking, preserved reasoning and sampling; reviewed 6 November 2026 |
| Client tool history | [OpenCode 1.19.5 transforms](https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/provider/transform.ts) | Reasoning history and output ceiling; see [agent settings](../deploy/agent-settings.md) |
| Quantized model | [NVIDIA Qwen3.8-27B-NVFP4 model card](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4) | Exact model identity and upstream license/reference |
| Agentgateway release | [v1.7.0 source](https://github.com/agentgateway/agentgateway/tree/v1.7.0) | Runtime and schema version |
| Exact configuration schema | [v1.7.0 schema/config.json](https://github.com/agentgateway/agentgateway/blob/v1.7.0/schema/config.json) | Field names, key hashes, token budgets and metadata logging |
| Native admin API | [v1.7.0 ui.rs](https://github.com/agentgateway/agentgateway/blob/v1.7.0/crates/agentgateway/src/ui.rs) | Resource create/list/delete used by the helper |
| SQLite | [Database guide](https://agentgateway.dev/docs/standalone/latest/documentation/setup/database/) | Single-instance database deployment |
| Durable UI edits | [Configuration storage](https://agentgateway.dev/docs/standalone/latest/documentation/setup/storage/) | Hybrid SQLite configuration storage |
| Key controls | [Virtual keys](https://agentgateway.dev/docs/standalone/latest/documentation/llm/cost-controls/virtual-keys/) | Generation, model restriction, budgets and revocation |
| Admin access | [Secure the UI](https://agentgateway.dev/docs/standalone/latest/documentation/setup/ui/secure-ui/) | Separate protected UI; unauthenticated debug interface disabled |
| Backend routing | [LLM configuration](https://agentgateway.dev/docs/standalone/latest/documentation/llm/about/) | Public model alias and upstream model name |
| OpenCode | [Providers](https://opencode.ai/docs/providers/) | OpenAI-compatible provider configuration |
| MIG | [Supported MIG profiles](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-mig-profiles.html) | Target profile naming and hardware distinction |
| Slurm | [GRES and MIG management](https://slurm.schedmd.com/gres.html#MIG_Management) | Pre-created MIG, typed GRES, scheduler ownership |
| Container jobs | [NVIDIA Pyxis](https://github.com/NVIDIA/pyxis) | srun container-image/mount/env interface |
| vLLM API | [OpenAI-compatible server](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html) | Chat, streaming, tool calls and tokenization |
| SQLite snapshots | [SQLite backup API](https://www.sqlite.org/backup.html) | Online consistent backup instead of copying a live DB file alone |

The vLLM image digest, model revision and initial serving parameters were taken from the existing prototype's recorded configuration, then inspected on the live RTX PRO 6000 host. This package's gateway tests use the existing model service; they do not establish that a fresh B200 deployment has passed. No MalayMMLU/ILMU or coding-quality benchmark is implied by the gateway acceptance tests.

NVIDIA Dynamo documents agentgateway as an option for its Kubernetes Gateway API integration. This sample uses standalone agentgateway and does not require Kubernetes or Dynamo. [Dynamo integration guide](https://docs.nvidia.com/dynamo/kubernetes/installation/gateway-api-inference-extension)

## GPU portability references

Checked on 5 November 2026: [NVIDIA compute capabilities](https://developer.nvidia.com/cuda/gpus), [B200 MIG profiles](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-mig-profiles.html#b200-mig-profiles), [NVIDIA vLLM 26.10](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/rel-26-10.html) and the [model card](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4). These support the architecture/profile distinction; target execution is a separate acceptance step.
