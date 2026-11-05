# Blueprint architecture

[Documentation](../README.md) · [← Overview](../../README.md) · [Setup guide](../start/install.md) · [B200 cluster guide](../deploy/b200-slurm.md)

The blueprint serves a model behind a usage-aware gateway. Qwen and OpenCode are the supplied example model and optional client; other API clients can use the same gateway.

## One request, three responsibilities

1. **An API client** sends requests through the OpenAI-compatible API. If the client is OpenCode, it executes approved tool calls locally and sends their results back to the model.
2. **agentgateway** authenticates an individual key, checks model scope and token budgets, and forwards the request to vLLM using a separate backend credential.
3. **vLLM** loads the pinned Qwen NVFP4 model on one visible GPU or MIG device and returns text or tool calls.

The gateway maps public model `qwen-coder` to backend model `qwen`. Changing GPU profile does not change the client API.

## Where things run

| Component | Standalone | Cluster |
|---|---|---|
| OpenCode | Developer machine | Developer machine |
| agentgateway and SQLite | Linux GPU host | Stable Linux CPU service host |
| vLLM | Docker, one selected GPU | Slurm + Pyxis, one allocated GPU/MIG device |
| User ingress | SSH tunnel for commissioning | Site HTTPS reverse proxy |
| Administration | Separate authenticated loopback listener over SSH | Same |

SQLite stores configuration, hashed keys, budgets and usage metadata for **one gateway replica**. Put the active database on persistent local disk, not NFS/Lustre. Use the SQLite backup API for consistent snapshots. The configured logging mode excludes prompt and response bodies.

## Hardware portability

The default deployment is B200 MIG `4g.90gb` (SM100) under Slurm. RTX PRO 6000 Blackwell Server Edition (SM120) is the standalone demo. Both paths use the pinned NVIDIA vLLM image and the same model revision. The startup preflight detects the visible device and the Slurm launcher requires the `4g.90gb` profile; vLLM and its libraries select hardware-specific kernels at runtime. No architecture-specific compiled caches are copied from the RTX prototype.

Start with tensor parallelism 1, 262,144 total tokens, one sequence, FP8 E4M3 KV cache and 0.80 memory utilization. This is the configured baseline for 200K input plus output, not measured B200 capacity. A real 200K-input acceptance request is required; the launcher never silently reduces context. [Compatibility details](../deploy/gpu-compatibility.md).

## Access boundaries

The model API, management UI, metrics and readiness listeners bind to loopback on the gateway host. Public access goes through the model API's HTTPS route. The management listener requires separate credentials; the unauthenticated debug listener is disabled.

On a cluster, the private backend must be isolated from ordinary clients and unrelated jobs, including jobs on the same node. MIG isolates GPU resources, not network traffic. Follow the [positive and negative access checks](../deploy/b200-slurm.md#41-mandatory-backend-isolation-execution-and-evidence) before sharing keys.

## Operational limits

A Slurm job ending takes inference offline. This sample has no automatic job renewal or service discovery; the operator must renew the allocation and verify routing. SQLite state survives model restarts on the gateway host.

Token budgets account for completed usage; they are not exact GPU billing or fair scheduling. Long context and concurrency need separate acceptance. Historical RTX results do not establish B200 performance, 200K coding quality or production availability.
