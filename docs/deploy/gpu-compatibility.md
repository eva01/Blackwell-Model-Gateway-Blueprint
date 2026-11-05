# GPU detection and context capacity

[Documentation](../README.md) · [Default B200 installation](b200-slurm.md) · [Standalone demo](../start/install.md)

## Default target and demo

| Deployment | Detected family | Architecture | Launch path |
|---|---|---|---|
| **Default: B200 MIG `4g.90gb`** | `b200`, MIG `4g.90gb` | 10.0 / SM100 | Slurm/Pyxis |
| RTX PRO 6000 Blackwell demo | `rtx-pro-6000` | 12.0 / SM120 | Standalone Docker |
| Full B200 alternative | `b200` | 10.0 / SM100 | Standalone Docker |

NVIDIA's [compute-capability table](https://developer.nvidia.com/cuda/gpus) distinguishes these devices from RTX 6000 Ada (8.9) and RTX A6000 (8.6). The [MIG profile table](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-mig-profiles.html#b200-mig-profiles) lists B200 `4g.90gb`. A MIG slice shares the parent GPU architecture but exposes a smaller allocation.

## Automatic detection

Leave `GPU_PROFILE=auto` in `inference/backend.env`. The same check runs for preflight and model startup:

1. Inspect CUDA visibility **inside the serving container**, after Docker or Slurm has assigned the device.
2. Require exactly one visible GPU/MIG device.
3. Match its reported name and compute capability to B200 or RTX PRO 6000 Blackwell. An unrelated product with the same compute capability is not assumed to be supported.
4. Read the MIG profile from the CUDA device name, or match the allocated CUDA device UUID to its MIG entry in `nvidia-smi -L`. Other devices in that inventory are never selected. The Slurm template sets `EXPECTED_MIG_PROFILE=4g.90gb`, requiring a B200 with that exact profile. A full GPU, a different slice or a missing profile fails that cluster check. Memory size alone never proves a MIG profile.
5. Run a small CUDA matrix multiplication and report device, memory, architecture, MIG profile and software versions as JSON.

Explicit `GPU_PROFILE=b200` or `rtx-pro-6000` remain available as assertions for an operator who wants to reject the other family. They do not change or emulate hardware. Normal installation requires no manual profile selection.

Detection does not configure MIG, pick a Slurm account/partition/GRES, reserve a TCP port, change drivers or override `CUDA_VISIBLE_DEVICES`. The cluster administrator still supplies those site values. If neither the CUDA name nor an exact UUID match establishes the MIG profile, the strict cluster check stops. The administrator must verify the allocation/runtime rather than guess from reported memory. A missing `mig_profile` is unknown, not proof of a full GPU.

## What makes the architecture portable

The gateway and SQLite run on the CPU. Both inference paths use the pinned NVIDIA vLLM container and model revision. Keep its PyTorch, CUDA, vLLM and kernel libraries together; they select kernels for the allocated device. Do not copy RTX compilation/autotuning caches to B200 or force SM120 kernels.

The [NVIDIA 26.10 container notes](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/rel-26-10.html) and [model card](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4) support evaluating the stack on Blackwell. They do not establish successful execution of this exact MIG configuration. The MoE-specific workaround in the release notes is not a reason to add MoE flags to this dense 27B model.

Match the host driver to the GPU, OS and pinned image using the [CUDA compatibility guide](https://docs.nvidia.com/deploy/cuda-compatibility/). The historical RTX driver is an observation, not a B200 minimum.

## Check before loading weights

For the standalone demo, from the project root:

```bash
bash inference/prototype-docker.sh --check-gpu
```

For the default Slurm deployment, append `--check-gpu` **after** `inference/serve.sbatch` in the approved `sbatch` command. The check runs inside the allocation and exits without downloading/loading model weights. Ordinary startup runs it automatically before loading the model.

A passing preflight checks basic CUDA execution. It does not exercise NVFP4, attention kernels or model capacity.

## Start directly with a 200K-input target

Both server and supplied client use **262,144 total context tokens** from the first launch. The client allows **32,768 output tokens**, leaving room for at least 200,000 input tokens, including history and tool content. One sequence and tensor parallelism 1 remain the defaults.

The total counts input and output together; [vLLM documents this meaning](https://docs.vllm.ai/en/latest/configuration/engine_args/#--max-model-len). These settings define the intended service, not a measured memory guarantee. There is no automatic smaller-context fallback.

Complete model startup, short gateway checks, [the real 200K-input probe](b200-slurm.md#6-qualify-200k-context-separately), and representative coding/client requests on the actual allocation. Keep concurrency changes separate. B200 model execution is still unverified in this repository's evidence; a passing GPU detector alone does not change that status.
