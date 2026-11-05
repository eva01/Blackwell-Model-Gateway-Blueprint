# Operate the gateway

[Documentation](../README.md) · [← Overview](../../README.md) · [Setup guide](../start/install.md)

For routine operation, use the [Gateway CLI](cli.md): `./gateway status`, `./gateway users list`, `./gateway usage` and `./gateway backup`. The lower-level commands remain available for troubleshooting and recovery.


## Credentials and key lifecycle

The backend key authenticates agentgateway to vLLM. The administrator password controls the UI and configuration API. Each researcher has a separate model-scoped virtual key. Keep these three credential types distinct.

Use the protected UI at port 14002, or the native-API helper:

```bash
./gateway users add researcher-b --daily-tokens 1000000
./gateway users list
./gateway users revoke RESOURCE_ID_FROM_LIST
```

Keys created through the UI and API persist in the same SQLite database. The supplied helper stores the hash in the gateway and the raw token in a private output file. It is a thin client for agentgateway, not a second key service. Keep the admin JSON private; move a researcher key to its owner through an approved secret channel and remove unnecessary copies afterwards.

The helper's create/list output contains only resource ID, name/user, model scope, budgets and storage type. It does not print stored key values or hashes, including keys created with the UI's raw-key storage option. Prefer hash storage. Administrator APIs and the SQLite database remain privileged data and must not be copied into support transcripts.

Resource writes and data-plane reloads are asynchronous. Allow a short propagation interval, then verify a revoked key receives 401. Requests already running can finish. Rotate by creating a replacement, updating the client, and revoking the previous key. **Automatic key expiry is not implemented by this sample**; a `24h` budget window is not a key expiration date. If time-limited access is mandatory, use explicit revocation or a separately approved identity/expiry mechanism.

## Browser playground

Forward **both** management port 14002 and inference port 4001 from the gateway host:

```bash
ssh -N -L 14002:127.0.0.1:14002 -L 4001:127.0.0.1:4001 user@gateway-host
```

Use the SSH account and reachable hostname provided by your administrator. Keep the tunnel terminal open while using the browser. If your host requires a bastion, obtain the site-approved SSH connection command from its administrator.

1. Open `http://127.0.0.1:14002/ui/llm/playground` and sign in with the administrator credentials.
2. If the page reports that browser access is not allowed, click **Apply CORS**. Confirm the allowed origin is exactly `http://127.0.0.1:14002`. The native UI saves this policy in SQLite under hybrid storage; it survives a gateway restart. For another browser URL, allow that exact scheme, hostname and port instead. `localhost` and `127.0.0.1` are different origins.
3. Select model **qwen-coder**. Select **Raw value** under Virtual API key and paste the individual user key into **Raw API key**. Helper-created keys are stored as hashes and cannot be recovered or selected as saved raw keys. Administrator sign-in does not authenticate model requests: the playground sends the supplied bearer key and omits browser cookies/Basic credentials.
4. Send `Reply exactly PLAYGROUND_OK.` Expect HTTP 200, that response, and input/output token counts. Send a follow-up to check conversation history.

The raw key is held in page state, not saved to localStorage; paste it again after a page reload. The v1.7.0 native playground requests a complete response (`stream: false`); streaming API support is tested separately by `scripts/verify.py`. The browser playground is an administrator diagnostic interface, not a user self-service portal. Give users their individual API key and inference URL for OpenCode, not administrator credentials.

If CORS is owned by baseline YAML in another deployment, edit that file rather than trying to override it through hybrid storage. This sample leaves the browser origin for the administrator to configure at commissioning. Keep the persistent SQLite directory when restarting or recreating the container. [Upstream playground guide](https://agentgateway.dev/docs/standalone/latest/documentation/llm/playground/)

## Usage and budgets

The UI Analytics/Logs pages and SQLite store input/output usage and request metadata. Per-key attribution uses the key's `user` metadata. This sample explicitly sets `standardAttributes.user` because the upstream default gives the key creator/owner priority; without this change, administrator-issued keys are attributed to the administrator. When creating a key in the UI, set `user` metadata to the researcher identifier. The default policy selects metadata-only database logging; acceptance verifies that synthetic prompt/response payloads are absent. Do not add prompt/body logging or full-payload tracing without an explicit data-handling decision.

The sample uses **token budgets**. No dollar price is invented for local GPU inference. Native budgets charge completed responses when upstream usage is present; they can overshoot by an in-flight request and concurrent requests. A key that consumes its allowance is blocked on subsequent requests. Daily windows align to UTC boundaries. This is access accounting, not exact GPU billing or a hard pre-reservation of all output tokens. [Native virtual-key controls](https://agentgateway.dev/docs/standalone/latest/documentation/llm/cost-controls/virtual-keys/)

A `24h` window resets at 00:00 UTC; convert that boundary to your local time zone. The CLI requires either `--daily-tokens` or an explicit `--unlimited`; the lower-level `scripts/keys.py create` helper still defaults to no budget when that flag is omitted. Assign an owner and deliberate allowance to each user key before distribution. Multiple keys for one user have separate per-key budgets.

The upstream budget implementation periodically persists counters, so a graceful-restart test is not proof of zero accounting loss on a crash. Missing upstream usage is not charged. This prototype also passed a completed streaming request with `stream_options` omitted: usage was returned and the next request was blocked by its one-token budget. Client disconnects, cancelled streams and abrupt gateway failure have not been qualified; do not use these counters for strict billing or promise exact crash durability. [Budget accounting semantics](https://agentgateway.dev/docs/standalone/latest/documentation/llm/cost-controls/budget-limits/)

vLLM performs prefix/KV caching. The gateway stores accounting data; it does not expand GPU KV capacity. The inference template enables prefix caching and cached-prompt usage details. Cached-token reporting should be checked separately if it is part of the site's accounting contract.

SQLite grows with request volume. Assign an owner and retention policy before production use. Docker stdout logs are rotated by this sample, but that does not prune SQLite request records. This sample does not run a scheduled retention worker.

## Start, inspect, stop and update

```bash
./gateway status
./gateway logs
curl --fail http://127.0.0.1:15022/healthz/ready
./gateway restart
./gateway stop
./gateway start
```

The container restarts with Docker according to `unless-stopped`; enable the site's Docker service at boot. A healthy gateway process does not prove the Slurm model job is ready. Monitor both model availability and gateway status. The vLLM backend remains scheduled independently.

To change the backend address, edit `.env`, then recreate the gateway using `docker compose up -d --force-recreate gateway`. A plain restart does not reread changed Compose environment values. Keep the same database volume/directory.

For a version upgrade, retain a database backup and the old configuration/image digest, test the new version on a separate copy, and repeat acceptance. Do not assume an older binary can read a database migrated by a newer version.

## Back up and restore

Use SQLite's online backup API while the service is running:

```bash
umask 077
mkdir -p /private/service/backups
python3 scripts/backup.py runtime/data/agentgateway.db \
  /private/service/backups/agentgateway-YYYYMMDD-HHMM.db
```

This includes committed WAL content and checks backup integrity. A raw `cp` of only the active `.db` file can omit live WAL data. Back up the matching `gateway.yaml`, `compose.yaml`, private `.env` and `runtime/secrets` separately through the site's encrypted backup process. Never commit backups or secrets to GitHub. A backup on the same disk is not an off-host recovery copy.

Restore during a maintenance window:

1. Stop only this gateway: `docker compose stop gateway`.
2. Preserve the whole old `runtime/data` directory, including any WAL/SHM files, under a dated recovery name. Do not combine an old database with newer WAL/SHM files.
3. Create a fresh `runtime/data` owned by the configured UID/GID with mode 0700. Copy the verified snapshot to `runtime/data/agentgateway.db`, mode 0600.
4. Restore the matching config and secrets, then start the pinned gateway version.
5. Verify `PRAGMA integrity_check`, a retained user key, the admin UI and budget counters. Test a known revoked key too: restoring an older snapshot can resurrect keys revoked after the backup. Reapply subsequent revocations before reopening access.

## Troubleshooting

| Symptom | Check |
|---|---|
| Gateway exits with SQLite initialization error | Directory exists, is writable by `GATEWAY_UID:GATEWAY_GID`, and is mounted at `/data` |
| UI returns 401 | Use administrator Basic credentials, not a model API key |
| Playground reports browser access is not allowed | Apply CORS for the exact browser origin; forward both ports 14002 and 4001 |
| Playground returns authentication failed | Paste the raw individual user key; administrator login alone does not authenticate inference |
| UI edit returns 409 | Hybrid storage prevents overwriting a resource owned by the baseline YAML; edit that file instead |
| Newly created key briefly returns 401 | Wait for configuration reload, then retry; check strict-key policy and stored key scope |
| Model API returns 403 | Key's allowed model names must include `qwen-coder` |
| Model API returns 429 | Inspect the key's token budget and active vLLM load |
| Gateway returns an upstream error | Check Slurm job/node, backend key, private route, vLLM logs and configured `/v1` base URL |
| Stream stalls at a fixed interval | Check TLS proxy buffering and all proxy/backend/client timeout settings |
| Backend fails to initialize CUDA | Confirm the allocated MIG device, Slurm cgroups, driver and container compatibility |
| OOM with long prompts | Check total context, active sequences, KV-cache allocation and actual device memory |

The sample management listener uses Basic authentication over an SSH tunnel. If the operator publishes a browser-accessible admin service, use TLS plus the site's OIDC/authorization policy. Keep the unauthenticated debug listener disabled.

## Migrate an existing installation

The generalized configuration changes the Compose project name, model aliases and client environment variables. Treat these as a coordinated migration; replacing YAML alone does not migrate SQLite-managed keys or the running backend.

1. Schedule a maintenance window and take a consistent [SQLite backup](#back-up-and-restore). Record the existing Compose project name, runtime directory, backend configuration and key scopes privately.
2. Stop the old gateway using its existing Compose project name and configuration. Do not start a second gateway against the same SQLite file or loopback ports.
3. Update the private backend environment: `GPU_PROFILE=auto`, `MAX_MODEL_LEN=262144`, `SERVED_MODEL=qwen`, and the generic launcher variables `BACKEND_ENV` and `INFERENCE_PACKAGE_ROOT` where applicable. Restart the model under its normal Docker or Slurm lifecycle.
4. Keep the existing private `.env`, backend key and persistent `runtime/data`. Do not rerun bootstrap or replace them with prototype state. Start the gateway with the new Compose configuration and the same owned runtime directory.
5. Using the native key-management UI, update existing keys' allowed model scopes to `qwen-coder`, or issue replacement keys and revoke the old ones after the transition. Preserve owners and intended budgets.
6. Update clients to provider `inference`, model `inference/qwen-coder`, `INFERENCE_BASE_URL` and `INFERENCE_API_KEY`. The default client context is now 262144 with output allowance 32768; confirm matching server settings and pass 200K-input acceptance before reopening access. Adopt the [thinking and tool-calling settings](../deploy/agent-settings.md), including the OpenCode output-ceiling environment variable. Reconcile stored UI/playground model defaults with the new alias and thinking-mode preset.
7. Run gateway, isolation and client acceptance before reopening access. Retain the old configuration and snapshot for rollback; restore them as a matched set if needed.

Historical source labels in the distributed evidence have also been generalized. Their recorded hashes refer to original private artifacts; they are not checksums of newly renamed files.
