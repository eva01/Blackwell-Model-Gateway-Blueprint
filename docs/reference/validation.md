# Validation record and target acceptance

[Documentation](../README.md) · [← Overview](../../README.md) · [Setup guide](../start/install.md)


> **Historical evidence.** Reports in `evidence/` have generalized names and aliases. They preserve earlier outcomes, not a fresh execution of the renamed package. The new GPU preflight is unit-tested with synthetic CUDA interfaces; B200 startup and inference still require the hardware acceptance procedure in [GPU compatibility](../deploy/gpu-compatibility.md).


## Current deployment defaults

The default target is now **B200 MIG 4g.90gb**, with **262144 total context tokens** and a **200000-token input acceptance target** from first launch. The RTX installation is a demo. Hardware family is detected automatically, and the Slurm template requires exact MIG-profile evidence. The earlier GPU-detection changes were covered by local synthetic tests; they are **not new B200 execution evidence**. Historical reports below retain their original scope. Use the [current long-context acceptance command](../deploy/b200-slurm.md#6-qualify-200k-context-separately), which allows 32768 output tokens, for deployment.

## Agent settings update: 6 November 2026

Thinking and preserved reasoning are now enabled, with `xhigh` effort, the official thinking-mode sampling preset and a 32768-token client output allowance. OpenCode now declares tool-call and reasoning capabilities and retains `reasoning_content` across turns. The context probe now uses thinking mode and the same output allowance. No tests were run for this update, at the user's request; the prototype is retired. Existing reports do not validate these new settings. See [agent settings and tool calling](../deploy/agent-settings.md) for configuration, client responsibilities and remaining live verification.

## Static blindspot review: 6 November 2026

This review read the current files and relevant upstream source; it did not run tests or launch a service. An independent static review found no actionable issue in GPU/MIG detection, Docker/Slurm launchers or their installation steps.

The review resulted in four changes:

- OpenCode's header and stream-idle timeouts now match the gateway's 30-minute budget, with an explicit total request timeout. Its five-minute defaults could otherwise abort a queued request or long prefill early.
- The context probe passes reasoning effort through `chat_template_kwargs` to `/tokenize`, matching the generation template. The documented [tokenization request handler](https://docs.vllm.ai/en/latest/api/vllm/entrypoints/serve/tokenize/protocol/) does not forward a top-level `reasoning_effort` field into the template.
- Context acceptance now requires `finish_reason: stop`, a completed stream, returned usage and the retrieval code, with no streamed error. A truncated response containing the code no longer counts as success. Reports include the context/output limits and thinking settings.
- The gateway verifier writes to `runtime/gateway-acceptance.json` by default, so its normal invocation no longer replaces historical prototype evidence.

These are source-reviewed fixes, not new execution evidence. Automatic and streamed thinking-mode tool calling, B200 capacity and site networking still need live acceptance when a server is available.

## Operator CLI and prerequisite installer: 6 November 2026

The new [Gateway CLI](../operate/cli.md) wraps local Compose lifecycle commands, key management, read-only usage reporting and the existing SQLite backup helper. The [prerequisite installer](../start/prerequisites.md) checks host tools and optionally installs missing Ubuntu packages for the CPU gateway or standalone demo role.

An independent static review identified two issues before handover: service commands could inherit a remote Docker context, and missing Compose could bypass the guard for an unsupported existing Docker installation. The implementation now explicitly selects the local default context/project and checks Docker provenance independently of Compose availability. The reviewer found no remaining concrete blockers in the final source review.

No new CLI commands, package installers, tests or services were executed. The development workspace is on macOS; host installation is supplied for the supported Ubuntu server. Runtime behavior, installation on a fresh host, user-key operations and usage queries still require execution on that host.

## Executed prototype: 5 November 2026

The new agentgateway instance was tested against the existing vLLM backend on an **NVIDIA RTX PRO 6000 Blackwell Server Edition**, with 97887 MiB reported memory and driver 595.112.07. The backend advertises 262144 total context tokens with one active sequence. Artifact pins are in [versions.json](../../versions.json).

Agentgateway v1.7.0 ran as one Linux container with local SQLite, hybrid storage, loopback API/admin listeners and no separate database service. The exact runtime accepted the YAML used at that time with `--validate-only`; this does not validate later edits.

The [integration result](../../evidence/prototype-verification.json) records successful checks for:

- Missing/invalid key rejection and protected administrator access.
- Administrator UI HTML served behind authentication.
- Hashed virtual-key creation through the native configuration API.
- Model discovery, per-key model restriction and rejection of administration using a user key.
- Chat completion with usage and streamed completion with final usage.
- Structured tool-call arguments and a tool-result round trip.
- A token budget allowing the initial request and blocking the next after usage is charged.
- Keys and exhausted budgets surviving a gateway restart.
- Key revocation propagating to the model API.
- SQLite integrity, persisted researcher-attributed token usage, and no stored prompt/response payloads or synthetic prompt canary in log attributes.

The [short context probe](../../evidence/short-context-probe.json) used **2054 input tokens**, returned the embedded retrieval code and recorded streaming usage and time to first content. This verifies the probe's mechanics; it is not a 200K-context test or a performance benchmark. Timing values describe one synthetic request on that prototype only.

Local helper tests cover URL validation, a consistent SQLite backup with committed WAL data, refusal to overwrite a backup, private file permissions, and inference argument generation. Python/JSON parsing and Bash syntax checks passed. The gateway's readiness endpoint returned HTTP 200.

The [live browser playground check](../../evidence/playground-verification.json) also passed: Apply CORS saved the exact local UI origin; an empty bearer key returned 401; supplying the user key produced three HTTP 200 completions. The first returned `PLAYGROUND_OK` (654 ms, 29 input / 4 output tokens). The follow-up retained that marker and generated a Python palindrome function (2.2 s, 88 / 82 tokens). After restarting only the gateway, the CORS policy remained and the same browser/key returned `RESTART_OK` (891 ms, 189 / 4 tokens). An unrelated origin received no CORS allow-origin header before or after restart. These timings describe individual synthetic requests, not a benchmark. Native v1.7.0 playground requests are non-streaming; the separate integration check covers streaming.

## Findings incorporated into the sample

1. Native configuration writes return before the serving configuration has finished reloading. Acceptance waits for activation/revocation instead of assuming immediate propagation.
2. By default, the identity of the administrator who creates a key takes priority over the key's `user` metadata. The sample explicitly selects `apiKey.user` first for correct researcher attribution.
3. Native budget enum values in the pinned schema are `Tokens` and `Block`; the helper uses those exact values.
4. The debug/admin listener is distinct from the authenticated UI gateway. The sample disables the former rather than relying on UI authentication to protect it.

## Blindspot review — 5 November 2026

The final handover also preserves [earlier direct-vLLM RTX experiments](../../evidence/rtx-capacity-and-agent-summary.json). One synthetic request used 200041 input tokens, retrieved all five embedded facts and sampled 82605 MiB peak GPU memory. Separate OpenCode trials with a pinned working directory and thinking disabled passed five visible and fourteen holdout tests in both English and Malay. Earlier unpinned trials did not pass. These experiments used the direct backend, not the final agentgateway/HTTPS route, and do not establish B200 capacity, 200K coding quality or general coding performance. Original result hashes are included; local raw experiment artifacts are retained separately.

The 5 November blindspot review found and fixed a helper-output issue: listing a UI-stored raw key could print that credential. The CLI now emits an allowlisted summary; a synthetic-key regression test failed before the fix and passed afterwards. All four helper tests pass, and the summary was checked against the running gateway. This was a local helper fix; it did not change stored keys or gateway authentication.

An additional live check omitted `stream_options` from a completed streamed request. It returned HTTP 200 and 18 total tokens; a subsequent request returned 429 with a one-token budget. The temporary test key was revoked. This does not cover disconnects or cancellations.

The [backend probe validation](../../evidence/backend-probe-validation.json) checks the new read-only TCP helper. All eight helper tests pass. On the prototype, the service account reached `127.0.0.1:8000`, and an unrelated unprivileged local account also reached it: the required-blocked probe correctly exited 1. Loopback binding therefore does not establish shared-node isolation. No firewall was changed and no site acceptance is claimed. The user selected administrator-run site handover checks; [section 4.1 of the deployment guide](../deploy/b200-slurm.md#41-mandatory-backend-isolation-execution-and-evidence) requires complete evidence and sign-off before user access.

## Final handover verification

The prototype was stopped/deletion requested and its removal from cloud inventory was confirmed on 5 November 2026 at 12:38 UTC. [Retirement evidence](../../evidence/prototype-retirement.json). Two private local recovery archives passed checksum verification; the consistent SQLite snapshot also passed an extracted restore integrity check. These archives contain private state and are excluded from the operator ZIP. The tests below describe the historical prototype, which is no longer serving requests.

Before prototype retirement, a [fresh gateway run](../../evidence/final-gateway-verification.json) passed all 24 checks executed without a restart; the earlier record separately covers restart persistence. The [guide's OpenCode scratch task](../../evidence/final-opencode-verification.json) also passed through agentgateway on the RTX host: three baseline failures became three passing tests, the agent exited 0, tests/configuration were unchanged, and the run took 11.993 seconds. The temporary commissioning key was revoked. This validates the loopback gateway/client path, not the site's HTTPS route or full production workload.

## Not executed / not claimed

| Item | Status |
|---|---|
| B200 MIG 4g.90gb launch | Not executed; site deployment template and acceptance steps supplied |
| Slurm/Pyxis job, cgroups and MIG isolation | Shell/template reviewed; requires the operator's cluster |
| New clean-host model download/startup | Uses recorded pinned artifacts; this gateway test reused the existing model server |
| 200K input and realistic long-context coding | Not executed in this isolated gateway test |
| OpenCode through the site's HTTPS endpoint | RTX loopback gateway edit/test loop passed; repeat the guide's task through the site's real HTTPS URL |
| Site TLS ingress / SSO / firewall | Template and integration requirements supplied; not changed or tested at site |
| Full live disaster recovery | SQLite backup helper tested against WAL data; operator must drill complete restore with its secrets and configuration |
| Shared-node backend network isolation and port reservation | Required positive/negative access and collision checks documented; not executed at the deployment site |
| Multi-user fairness and cancellation accounting | No configured admission limits or tested competing-user/disconnect behavior; daily budgets alone do not establish these |
| Abrupt failure / crash durability | Graceful restart tested; no crash-injection or zero-loss accounting claim |
| Automatic key expiry | Not supplied; token-budget windows are not expiry |
| High availability / multiple gateway replicas | Outside this single-instance SQLite design |

## Repeatable long-context command

On the gateway host, issue a temporary key with a budget large enough for the test. Ensure the inference job is configured for the selected context limit, is allocated the intended MIG device and is reserved for acceptance work. The tokenization endpoint must be reachable from the test host with the backend key.

```bash
python3 scripts/keys.py create context-acceptance \
  --out runtime/secrets/context-acceptance.key
python3 scripts/context_probe.py \
  --base-url http://127.0.0.1:4001/v1 \
  --backend-url http://COMPUTE_NODE_PRIVATE_NAME:8000 \
  --key-file runtime/secrets/context-acceptance.key \
  --prompt-tokens 200000 --output-tokens 32768 --context-limit 262144 \
  --out runtime/b200-context-200k.json
```

The helper counts the chat template using vLLM's `/tokenize`, sends a streamed request through the gateway and checks actual returned input usage and retrieval success. It does not measure GPU peak memory; collect that through the site's supported device metrics and vLLM logs. Revoke the test key after the test and remove its raw token from the host.

Record GPU/MIG identity, driver, image/model revisions, context/concurrency settings, requests, output allowance, error rate, queue time and end-to-end coding results. The client already declares the intended limits; advertise them as qualified only after the target passes.
