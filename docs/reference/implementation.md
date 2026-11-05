# Implementation map

[Documentation](../README.md) · [← Overview](../../README.md)

| Component | Files | Responsibility |
|---|---|---|
| Gateway | `compose.yaml`, `gateway.yaml`, `.env.example` | Pinned service, loopback listeners, SQLite, access policies and model routing |
| Initialization | `scripts/bootstrap.py` | Private runtime directories, administrator credentials and backend key |
| Key management | `scripts/keys.py` | Create, list and revoke model-scoped user keys |
| Inference | `inference/serve.sh`, `inference/gpu_check.py` | Validate one allocated device and launch the pinned model |
| Standalone launch | `inference/prototype-docker.sh` | Select one GPU, mount cache and key, publish the backend on loopback |
| Cluster launch | `inference/serve.sbatch` | Run under Slurm/Pyxis without overriding scheduler device visibility |
| Verification | `scripts/verify.py`, `scripts/context_probe.py`, `scripts/backend_probe.py` | Gateway behavior, context capacity and network reachability |
| Recovery | `scripts/backup.py` | Consistent SQLite snapshot |
| Client | `client/opencode.json` | OpenAI-compatible provider and initial context limits |
| Operator CLI | `gateway`, `scripts/gateway_cli.py` | Local gateway lifecycle, private user keys, read-only usage totals and SQLite snapshots |
| Prerequisites | `scripts/prerequisites.sh` | Host checks and optional Ubuntu package installation; does not configure the cluster |
| Unit tests | `tests/` | Helpers, probes, GPU preflight and launcher argument forwarding |

The project uses Python's standard library for its helpers. The GPU check imports PyTorch from the inference container; local unit tests use a synthetic CUDA interface and do not claim hardware validation. The gateway bootstrap additionally needs `htpasswd` or Python `bcrypt`.

`MANIFEST.sha256` enumerates distributable files. Runtime data, secrets, model weights and local environments are excluded. Files in `evidence/` preserve sanitized historical reports; new commissioning reports belong in private `runtime/` storage.

The gateway verifier defaults to `runtime/gateway-acceptance.json`. The context probe records its thinking settings, context/output limits and stream completion status; retrieval only passes with a normal `stop` finish reason, final usage and the stream's completion marker. Truncated output or a streamed error cannot pass simply because the retrieval code appeared earlier.

## Local checks

Run these from the repository root. They are for maintainers; the installation guide includes the checks an installer needs.


These checks do not launch a GPU service:

```bash
python3 -m unittest discover -s tests -v
bash inference/serve.sh --dry-run
GPU_PROFILE=b200 bash inference/serve.sh --dry-run
sha256sum -c MANIFEST.sha256
```

The runtime preflight checks device visibility, expected compute capability and a small CUDA operation inside the inference image. It does **not** certify NVFP4 kernels or model capacity; model startup and inference acceptance are separate steps.
