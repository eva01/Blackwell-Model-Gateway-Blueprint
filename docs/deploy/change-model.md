# Use a different model

[Documentation](../README.md) · [Architecture](../reference/architecture.md)

**For:** an operator adapting the working example after its first successful installation.


The blueprint separates the model backend from access management. Replacing the model does not require replacing the gateway, but it does require validating a new serving configuration.

| Change | Where to configure it |
|---|---|
| Model repository and exact revision | `MODEL_ID`, `MODEL_REVISION` in private `inference/backend.env` |
| Container with support for the model and GPU | `VLLM_IMAGE`; for Slurm also rebuild the pinned `VLLM_SQSH` |
| Memory, context and concurrency | `MAX_MODEL_LEN`, `MAX_NUM_SEQS`, `GPU_MEMORY_UTILIZATION`, `KV_CACHE_DTYPE` |
| Model-specific parsers and serving flags | Review `inference/serve.sh`; its current reasoning/tool parsers are Qwen-specific |
| Request defaults | Review `gateway.yaml`, `scripts/verify.py` and `scripts/context_probe.py`; `enable_thinking` is model-specific |
| Backend and public model names | Keep `SERVED_MODEL`, `gateway.yaml`, key scopes, probe scripts and client configuration consistent |
| Client token limits | `client/opencode.json`, if using OpenCode |

Choose the new model's documented quantization, GPU support and runtime settings. Keep the GPU allocation and network boundaries intact. A different model may require different memory, parsers or tensor parallelism; the supplied launch path intentionally exposes one GPU/MIG device. Repeat startup, generation, usage, streaming and any required tool-call acceptance on the actual target. Update `versions.json` and record fresh evidence before distributing a customized package. The included Qwen results do not qualify other models.
