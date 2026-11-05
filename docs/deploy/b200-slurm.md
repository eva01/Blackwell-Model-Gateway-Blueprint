# Blackwell blueprint: B200 MIG deployment with Slurm

[Documentation](../README.md)

Prepare the CPU gateway host with the [prerequisite checklist and installer](../start/prerequisites.md). For routine gateway commands, use the [CLI reference](../operate/cli.md). Cluster compute-node prerequisites remain administrator-managed.

This is the **default installation path: one B200 MIG 4g.90gb allocation**, serving a 200K-input workload with 262,144 total context tokens. Follow sections in order and record results on the site. The package is independent of the retired cloud prototype: download the pinned artifacts, generate new credentials and create a new SQLite database. Do not copy prototype credentials or its database into the new installation. This is a reference implementation using NVIDIA components, not an NVIDIA-certified blueprint.

**RTX demo or standalone full B200:** use the [standalone demo guide](../start/install.md). Both launch paths use `GPU_PROFILE=auto`; this cluster template additionally requires the B200 `4g.90gb` MIG profile.

See [what runs where](../../README.md#what-runs-where) for the inference path, administration, persistent state and scheduler control. The [AI-assisted installation prompt](../../README.md#install-with-an-ai-agent) can guide an already-working agent through this runbook with your site details.

## Read this before running commands

This is a manual administrator runbook; no AI agent is required. An Open OnDemand terminal is one way to access the cluster submission host. Run each block in order on the host named in the surrounding step. Replace every `SITE_*`, `JOB_ID` and example path with the values recorded in section 0; do not paste placeholders unchanged.

The installer needs the cluster administrator to provide the allocation, private routing, firewall policy and service accounts. Those values cannot be guessed. On an error, stop at that step, record its output without credentials, and use the [operations troubleshooting table](../operate/administration.md#troubleshooting). Do not advance to user-key distribution before the isolation checks pass.

For manual editing, use `nano inference/backend.env`: Ctrl+O then Enter saves, Ctrl+X exits. Keep separate terminal windows for the submission host and CPU gateway host. `hostname` shows which host you are on; `pwd` shows the current directory. The standalone [manual guide](../start/install.md) explains the three credential types and includes a plain HTTP test that does not need OpenCode.

## Deployment stages

| Stage | Outcome |
|---|---|
| [0. Prepare](#0-prepare-the-handover-and-identify-each-host) | Owners, hosts and site values recorded |
| [1. Confirm integration](#1-confirm-the-site-integration) | GPU, driver and scheduler requirements checked |
| [2. Stage artifacts](#2-stage-the-model-and-pinned-container) | Pinned weights, image and private key available |
| [3. Start inference](#3-submit-one-allocated-mig-device) | One allocated SM100 device serving the model |
| [4. Install gateway](#4-install-the-gateway-on-its-stable-cpu-host) | Persistent API and key management ready |
| [4.1. Verify isolation](#41-mandatory-backend-isolation-execution-and-evidence) | Authorized access works; unauthorized routes blocked |
| [5. HTTPS and client](#5-expose-the-user-api-through-the-existing-tls-ingress) | Real user route and OpenCode tested |
| [6. Context capacity](#6-qualify-200k-context-separately) | Accepted limits measured on the allocation |
| [7–8. Handover and recovery](#7-acceptance-and-handover) | Ownership, renewal and recovery agreed |

## 0. Prepare the handover and identify each host

Use the supplied ZIP or an approved checkout of the repository supplied by your maintainer. Repository access must be granted separately. Record the Git commit when deploying from Git, and verify the included manifest. On each Linux host receiving the ZIP:

If the README already led you to download the project on the gateway host, reuse that directory and skip its acquisition commands below. The submission host still needs a separate copy on compute-visible storage. Example directory names can differ from your checkout; record and use your actual absolute paths throughout.

```bash
unzip qwen-agentgateway-operator-sample.zip
cd qwen-agentgateway
sha256sum -c MANIFEST.sha256
```

Alternatively, deploy from Git:

```bash
# Set REPOSITORY_URL to the repository supplied by your maintainer.
git clone "$REPOSITORY_URL" qwen-agentgateway
cd qwen-agentgateway
git rev-parse HEAD
sha256sum -c MANIFEST.sha256
```

Stop on any missing file or checksum mismatch. All shell examples use **Bash**. Run the package as its designated non-root service owner; the administrator performs privileged driver, scheduler, firewall, filesystem and ingress work separately.

| Execution location | Account and files | Work performed |
|---|---|---|
| Cluster submission host / Open OnDemand terminal | Inference service account; package and private environment on compute-visible storage | Stage model/image, submit and inspect Slurm jobs |
| Allocated B200 compute node | Same inference account inside the Slurm/Pyxis allocation | Run vLLM on the assigned MIG device |
| Stable CPU gateway host | Gateway service account; separate package copy on persistent **local** disk | agentgateway, SQLite, native key administration, gateway tests |
| Ingress host | Site administrator; same host as loopback gateway in this sample | HTTPS certificate and NGINX route |
| Ordinary client and independent test job | Pilot user / separate unprivileged cluster account | OpenCode and negative isolation tests |

Complete these values with your administrator before installation; they cannot be inferred from the prototype:

| Required site value | Record |
|---|---|
| Inference and gateway service owners; installation approver | Names and non-root UID/GID |
| Cluster package and private environment paths | `INFERENCE_PACKAGE_ROOT`, `BACKEND_ENV` |
| Gateway package path on local disk | `GATEWAY_PACKAGE_ROOT` |
| Slurm account, partition, typed MIG GRES, duration and reservation/node policy | Administrator-approved values |
| Shared cache, SquashFS and backend-key paths | `MODEL_CACHE`, `VLLM_SQSH`, `BACKEND_KEY_FILE` |
| Node addresses, reserved backend port and gateway source addresses | Actual IPs/port; all relevant IPv4/IPv6 paths |
| Isolation implementation and independent test account | Administrator-owned configuration and test job access |
| Internal HTTPS name, trust chain and ingress owner | Certificate trusted by ordinary clients |
| Operating policy | Job renewal, fair-use limits, key revocation, backups, restore, retention and monitoring owners |

Provision the directory parents and ownership before running the staging commands. Shared package/model/image paths must be readable from the compute node; private key/environment files must be restricted to the service account and administrators. Check available storage with `df -h` on the model/cache and image filesystems before downloading. Runtime SQLite belongs only on the gateway's local disk.

Cluster submission host preflight (inference account):

```bash
bash --version
python3 --version
openssl version
hf --help >/dev/null
enroot version
sinfo --version
srun --help | grep -- --container-image
```

Gateway host preflight (gateway account):

```bash
test "$(id -u)" -ne 0
python3 --version
docker version
docker compose version
command -v htpasswd || python3 -c 'import bcrypt'
```

The administrator installs missing prerequisites through the site's supported repositories: Python 3.10+, Docker Engine/Compose v2 on the CPU host, `htpasswd` (Ubuntu `apache2-utils`) or Python `bcrypt`, and the approved Slurm/Pyxis/Enroot stack on the cluster. The `hf` CLI requires network access or an approved artifact mirror. Do not install Docker on the compute node for this Slurm path. Validate GPU driver/container compatibility in section 1; a successful CLI preflight alone is insufficient.

## 1. Confirm the site integration

Consult [release audit](../reference/release-audit.md) before commissioning. The 5 November 2026 audit recorded Pyxis 0.24.0 and Enroot 4.2.1. Confirm compatibility with the installed Slurm version and site support policy; these versions have not been inspected or installed at the deployment site. The pinned inference image is NVIDIA's 26.10-py3 release, verified against the official registry digest.

The target is **4g.90gb**, a MIG profile with approximately 90 GB device memory; “90B” is not the model's parameter count. This sample serves a 27B model. A full RTX PRO 6000 prototype and a B200 MIG slice have different compute and memory-bandwidth characteristics. Prototype timings cannot be used as B200 MIG performance figures.

The operator supplies the following values before launch:

| Value | How to establish it |
|---|---|
| Slurm account, partition and permitted job duration | Cluster administrator / service policy |
| Typed GRES name for the existing 4g.90gb instance | `scontrol show node NODE`, `slurmd -G` on the node |
| Supported NVIDIA driver and container runtime | Validate against the pinned vLLM image's CUDA/driver requirements |
| Pyxis + Enroot availability | `srun --help` must show `--container-image` |
| Service placement | Stable CPU gateway host, and an agreed Slurm node/reservation for inference |
| Shared package, image and model cache paths | Reachable by the allocated compute node; sufficient disk and permissions |
| Private backend address and reserved port | Site assigns an unused port per service on that node; gateway host can reach it |
| Internal HTTPS URL and certificate | Site reverse proxy / PKI team |

Slurm's documented MIG support expects devices to be partitioned beforehand and uses `AutoDetect=nvml`. The site's exact GRES type must be confirmed; `gpu:b200_4g.90gb:1` below is **an example, not an asserted site value**. Configure and validate device cgroups so the job sees exactly its allocated MIG device. Existing root access does not replace the allocation. [Slurm MIG management](https://slurm.schedmd.com/gres.html#MIG_Management)

The inspected prototype image contains vLLM `0.31.0+88641915.dev`, PyTorch `2.15.0a0+875d815502.nv26.10` and CUDA runtime **13.4**, and ran with host driver **595.112.07**. This is the tested artifact pin, not a claim that every B200 driver supports it. Check the site driver against the image's compatibility requirements before scheduling; if the operator chooses a different supported image, pin and repeat acceptance for that image.

Open OnDemand's terminal can submit and inspect the job. A browser session's lifetime should not determine this shared service's lifetime. Use the site's service account/reservation and ordinary `sbatch` lifecycle. The gateway should run on a service host approved for persistent processes rather than an arbitrary shared login node.

## 2. Stage the model and pinned container

On the **cluster submission host as the inference service account**, work in the shared package copy:

```bash
export INFERENCE_PACKAGE_ROOT=/SITE/SHARED/qwen-agentgateway
cd "$INFERENCE_PACKAGE_ROOT"
umask 077
cp -n inference/backend.env.example inference/backend.env
chmod 600 inference/backend.env
export BACKEND_ENV="$INFERENCE_PACKAGE_ROOT/inference/backend.env"
```

Keep `GPU_PROFILE=auto` and `MAX_MODEL_LEN=262144` in that private environment file. Edit the confirmed site cache, key, port and SquashFS paths. The runtime preflight must detect B200, compute capability `10.0` and MIG profile `4g.90gb`; see [GPU compatibility](gpu-compatibility.md). Preserve an existing file when rerunning; inspect it rather than overwriting it. Do not commit it.

Set `VLLM_PORT` to a site-reserved port for this service. Port 8000 in the examples is a placeholder. MIG isolation does not reserve TCP ports: two jobs on different slices of the same node can collide. The site must coordinate ports across co-resident jobs and check the selected port is available before launch. Use the same assigned port in the firewall, gateway backend URL and context-probe backend URL; do not derive an uncoordinated port from a job ID.

Generate a backend key once, on a host where the chosen path is writable by the service owner:

```bash
umask 077
mkdir -p /private/service/secrets
(set -o noclobber; openssl rand -hex 32 > /private/service/secrets/backend.key)
```

Replace `/private/service/secrets` with the administrator-provisioned service-owned path. The command refuses to overwrite an existing key: if it already exists, verify and reuse it or follow an intentional rotation procedure. Set `BACKEND_KEY_FILE` to that path. Securely transfer this **one backend key** to a private file owned by the gateway service account on the CPU host. The paths can differ between hosts; the key contents must match. API users receive separate gateway keys.

Using the trusted environment file:

```bash
set -a
source inference/backend.env
set +a
mkdir -p "$MODEL_CACHE/huggingface"
HF_HOME="$MODEL_CACHE/huggingface" hf download "$MODEL_ID" --revision "$MODEL_REVISION"
```

Pre-import the pinned container using the site's Enroot installation and registry credentials if needed:

```bash
enroot import --output "$VLLM_SQSH" \
  'docker://nvcr.io#nvidia/vllm@sha256:0a0de9362545e3e062750bec4ad4f722422a04a81182b5258a7deda4325e9313'
sha256sum "$VLLM_SQSH"
```

The SquashFS hash identifies the local import; it is distinct from the OCI image digest. Preserve both in the site acceptance record. Confirm registry/digest syntax with the installed Enroot version. If this cluster uses Apptainer instead of Pyxis, have its administrator adapt the launch to the supported runtime and demonstrate MIG cgroup isolation before use; that alternate launch is not tested by this sample. [NVIDIA Pyxis](https://github.com/NVIDIA/pyxis)

## 3. Submit one allocated MIG device

**Before starting the listener**, the cluster administrator must establish the backend network boundary described in section 4.1. Keep user access closed during commissioning. Use a dedicated service account for the inference job; a Slurm GPU allocation alone does not establish network isolation.

The initial environment uses `MAX_MODEL_LEN=262144`, `MAX_NUM_SEQS=1`, tensor parallel size 1, FP8 E4M3 KV cache and 0.80 GPU-memory utilization. Start directly at this long-context setting; there is no 32K warm-up configuration or automatic reduction. Section 6 tests at least 200,000 actual input tokens plus output allowance on the allocated slice.

```bash
mkdir -p logs
export INFERENCE_PACKAGE_ROOT="$PWD"
export BACKEND_ENV="$PWD/inference/backend.env"

# Replace each value with an administrator-approved value.
sbatch --account=SITE_ACCOUNT --partition=SITE_PARTITION \
  --gres=gpu:SITE_MIG_GRES_TYPE:1 --time=08:00:00 \
  inference/serve.sbatch
```

For a preflight-only allocation, append `--check-gpu` after `inference/serve.sbatch` in the command above. Require a successful JSON report with `profile: b200`, `compute_capability: 10.0` and `mig_profile: 4g.90gb`, then submit again without that argument to load the model.

Use a site-approved `--reservation` / `--nodelist` when assigning a stable service node. The script uses `srun` and Pyxis, leaves `CUDA_VISIBLE_DEVICES` to Slurm, and automatically checks the single visible device. It sets `EXPECTED_MIG_PROFILE=4g.90gb`; a full B200, a different slice or an unreported MIG profile fails preflight. It does not infer the profile from memory capacity. If CUDA omits the MIG profile from its device name, the check tries an exact match between the allocated CUDA device UUID and `nvidia-smi -L`. If neither identifies the profile, stop and have the administrator verify the allocation/runtime; do not bypass the check. It does not run Docker, repartition MIG, or request every GPU. Host CPU and RAM values in the template are starting requests; adjust them to the site's policy and observed peak host memory.

```bash
squeue -u "$USER"
scontrol show job JOB_ID
tail -f logs/qwen-JOB_ID.log
```

Confirm the log's visible CUDA device and memory correspond to the allocated slice and that vLLM finishes loading. Record the actual driver, GPU profile, model revision, image/SquashFS digest, KV-cache allocation and startup messages. Reach `/health` and perform an authenticated request from the gateway host before proceeding.

## 4. Install the gateway on its stable CPU host

On the **CPU gateway host as its non-root service account**, unpack and verify a separate copy on local disk. Do not run the gateway out of the shared cluster checkout. The administrator must give this account approved Docker access and ownership of the installation directory.

```bash
export GATEWAY_PACKAGE_ROOT=/SITE/LOCAL/qwen-agentgateway
cd "$GATEWAY_PACKAGE_ROOT"
test "$(id -u)" -ne 0
python3 -m unittest discover -s tests -v
```

Follow [gateway setup](../start/install.md#4-start-the-gateway), changing `--backend-url` to the compute node's private address:

```bash
python3 scripts/bootstrap.py \
  --backend-key-file /private/service/secrets/backend.key \
  --backend-url http://COMPUTE_NODE_PRIVATE_NAME:8000/v1
docker compose run --rm gateway --validate-only -f /config/gateway.yaml
./gateway start
```

Use the actual reserved backend port in the URL. Bootstrap generates **new** administrator credentials and the local SQLite runtime layout. It refuses an already initialized installation. Check `./gateway status`, `./gateway logs`, and `curl --fail http://127.0.0.1:15022/healthz/ready`. A ready gateway does not prove vLLM is ready; section 4.1 tests both. Use the [operations guide](../operate/administration.md#browser-playground) to open the protected admin UI over SSH, create a private commissioning key and test the playground. Keep that key with the commissioning team until isolation is accepted.

Place `runtime/data` on persistent **local disk** on the gateway host. Do not put the active SQLite file on an NFS/Lustre home or share it between gateway replicas. Backups can be copied to approved backup storage after a consistent SQLite snapshot is taken. Use a single gateway replica for this design.

Allow the assigned backend TCP port only from the gateway host and approved administrator paths. The supplied backend binds on the allocated node's interfaces so a separate CPU gateway can reach it; the site must enforce that boundary. Use an encrypted private transport or backend TLS if the site network requires it. Backend API authentication is retained either way.

The vLLM bearer key protects selected API path prefixes, not every route on its HTTP server. Do not use it as the sole protection for the compute-node listener. GPU/MIG device cgroups also do not isolate network access. An external firewall alone can leave other users or jobs on the same node able to reach the listener through loopback or the node address. This shared-node deployment requires site-enforced network isolation covering those callers. [vLLM security guidance](https://docs.vllm.ai/en/latest/usage/security/#api-key-authentication-limitations)

Before admitting users, check access from the authorized gateway host and separately from an ordinary client host and an unrelated job on the same compute node. The gateway must reach an authenticated model request. Unauthorized callers must be blocked from the entire backend listener, including a harmless GET `/health` or `/metrics`; a 401 only on `/v1/models` is insufficient evidence. Do not probe state-changing endpoints. Record these positive and negative checks with the site administrator; they have not been run at the deployment site.

When a job ends, is preempted or is rescheduled, the endpoint becomes unavailable until a replacement allocation is ready. This sample does not provide a Slurm job controller or automatic service discovery. For a new node, update `VLLM_BASE_URL` in the private gateway `.env` and run `docker compose up -d --force-recreate gateway`. The same SQLite directory retains user keys. Never point the gateway at a node before confirming the correct model service and backend key.

## 4.1 Mandatory backend-isolation execution and evidence

**Owner: Cluster administrator. Status: required, not executed at the deployment site. Do not distribute user keys or publish the user API until this gate is signed off.** A successful playground or gateway acceptance run does not waive it. The probe below records observations; it does not install firewall rules or automatically approve deployment.

The required route is `user → HTTPS ingress → agentgateway → private vLLM listener`. Users, ordinary client machines and unrelated jobs on the compute node must not reach vLLM directly. Keep the backend key with the inference/gateway service accounts only. Administrator access is a separate privileged path.

**Apply the boundary first.** Use the site's administrator-managed network namespace and firewall integration, or an equivalent enforced boundary that covers co-resident users. Binding to `127.0.0.1` alone does not isolate other processes in the same network namespace. A switch/router firewall alone does not cover local loopback traffic. The administrator must integrate the chosen mechanism with Slurm/Pyxis so the job retains its allocated MIG device, networking is established before vLLM starts, and rules are removed only when the service ends. Do not substitute an unreviewed global firewall flush or a network namespace that loses Slurm device isolation.

Record the service account, job ID, node, reserved backend port, actual bind addresses, approved gateway source addresses, firewall/namespace configuration reference, administrator and date. Protect any credentials separately. Confirm the gateway's configured backend URL matches this node and port. Repeat this gate after rescheduling to a different node, changing the network rules or changing the listener binding.

Run the following in one coordinated acceptance window while the inference job remains healthy. Use the same `RUN_ID` across all three vantage points and collect the reports in private operator storage. The sample ignores `runtime/` in Git; do not add site network inventories to the distributable evidence bundle.

On each test host, replace these values with the recorded site values:

```bash
export RUN_ID=inference-isolation-YYYYMMDD-HHMMSS
export TARGET_IP=SITE_COMPUTE_NODE_LITERAL_IP
export TARGET_PORT=SITE_RESERVED_PORT
export RUN_DIR="$PWD/runtime/isolation/$RUN_ID"
umask 077
mkdir -p "$RUN_DIR"
```

**A. Authorized gateway host — before the negative checks:**

```bash
python3 scripts/backend_probe.py --ip "$TARGET_IP" --port "$TARGET_PORT" \
  --expect allowed --vantage gateway-before --run-id "$RUN_ID" \
  > "$RUN_DIR/gateway-tcp-before.json"
python3 scripts/verify.py --out "$RUN_DIR/gateway-api-before.json"
```

Both commands must exit 0. The first establishes reachability of the exact target IP/port; the second tests authenticated model traffic through the configured gateway. It creates/revokes temporary keys. Do not use `--restart` during this coordinated window.

**B. Ordinary ordinary client machine — no VPN/SSH path reserved for administrators:**

```bash
python3 scripts/backend_probe.py --ip "$TARGET_IP" --port "$TARGET_PORT" \
  --expect blocked --vantage client-network --run-id "$RUN_ID" \
  > "$RUN_DIR/client-network.json"
```

**C. Unrelated Slurm job on the same compute node — a different, unprivileged account:**

The administrator arranges this job using the site's normal scheduler policy. Do not run the check as root or as the inference service account. Confirm its hostname equals the recorded compute node and record its independent job ID. From that job, run:

```bash
test -n "$SLURM_JOB_ID"
python3 scripts/backend_probe.py --ip "$TARGET_IP" --port "$TARGET_PORT" \
  --expect blocked --vantage same-node-address --run-id "$RUN_ID" \
  > "$RUN_DIR/same-node-address.json"
python3 scripts/backend_probe.py --ip 127.0.0.1 --port "$TARGET_PORT" \
  --expect blocked --vantage same-node-loopback --run-id "$RUN_ID" \
  > "$RUN_DIR/same-node-loopback.json"
```

Test every applicable backend IPv4/IPv6 and routed namespace address, each with a distinct report filename. Include `::1` where IPv6 is enabled. A test against an unused address does not cover the address on which vLLM actually listens. If unrelated users can also obtain a host shell outside a job, test that path too. Do not grant sudo or namespace-enter privileges merely to make a negative test pass.

**D. Authorized gateway host — after the negative checks:**

```bash
python3 scripts/backend_probe.py --ip "$TARGET_IP" --port "$TARGET_PORT" \
  --expect allowed --vantage gateway-after --run-id "$RUN_ID" \
  > "$RUN_DIR/gateway-tcp-after.json"
python3 scripts/verify.py --out "$RUN_DIR/gateway-api-after.json"
```

**Required interpretation and sign-off:**

| Result | Action |
|---|---|
| Exit 0, expected `allowed` | TCP connection succeeded; require the paired authenticated gateway test too |
| Exit 0, expected `blocked` | Connection was refused or timed out; this alone does not prove firewall enforcement |
| Exit 1 | Observation contradicts the required access boundary; stop handover and correct it |
| Exit 2, missing/empty report, skipped address or wrong account/node | Inconclusive; stop handover and rerun correctly |

The administrator must correlate the entire window with continuous backend readiness and the actual enforced rules: a stopped server, incorrect IP, absent listener or routing error is not proof of isolation. Any successful TCP connection from an unauthorized vantage fails this gate, even if `/v1/models` subsequently returns 401. The probe does not send credentials, inference prompts or state-changing requests.

Collect all reports under the same run ID, compare recorded source hosts, UIDs, job IDs, targets and times, and attach the enforced configuration reference. The cluster administrator and service owner must record an explicit pass or fail. **Only a complete passing record permits section 5 and user-key distribution.** This is an operator-enforced commissioning gate; the sample launch scripts cannot enforce remote firewall state or verify who ran a copied report.

## 5. Expose the user API through the existing TLS ingress

Proceed only after the complete section 4.1 record is approved. Keep access closed if any required isolation check is failed, skipped or inconclusive.

Keep the gateway model listener on loopback and put the site's HTTPS reverse proxy on the same CPU host. Publish only the `/v1/` model API route. The authenticated management listener stays reachable through an administrator SSH tunnel.

For an existing NGINX TLS server, adapt [nginx-location.conf](../../deploy/nginx-location.conf). It disables response buffering and allows extended streaming timeouts. Supply the internal DNS name and certificate through the normal site process. Do not expose the management API, metrics or readiness listeners to ordinary API users. External administrators should use a VPN/SSH tunnel or replace the sample Basic authentication with a site OIDC policy before publishing the UI.

The ingress administrator validates and reloads the existing server using the site's service manager; for NGINX managed by systemd:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Reload only after configuration validation succeeds. Initially allow the commissioning clients only. On the gateway host, verify the **real HTTPS route**, using the origin without `/v1` for this helper:

```bash
python3 scripts/verify.py --base-url https://SITE_INFERENCE_HOST \
  --out runtime/isolation/https-gateway-acceptance.json
```

Require a successful report with normal TLS certificate validation; do not add `--insecure` or disable certificate checks. Install the site's CA chain through the approved trust-store process if needed. An ordinary client must also complete section 5.1 over this hostname before wider rollout.

## 5.1 Verify OpenCode on an ordinary client

Install OpenCode from its [official release/distribution](https://opencode.ai/docs/), using the site-approved version, and record `opencode --version`. Version 1.19.5 was observed in the RTX prototype; qualify any selected replacement. Use a fresh scratch directory, not a user repository. OpenCode tools execute on this client, not inside vLLM. Keep normal tool approvals and restrict the trial to the scratch directory.

In a Bash terminal on the client, set `PACKAGE_ROOT` to its extracted package location and prepare the fixture:

```bash
export PACKAGE_ROOT=/PATH/TO/qwen-agentgateway
export TRIAL_DIR="$(mktemp -d)"
cp "$PACKAGE_ROOT/client/opencode.json" "$TRIAL_DIR/opencode.json"
cd "$TRIAL_DIR"
cat > calculator.py <<'PY'
def add(a, b):
    return str(a) + str(b)
PY
cat > test_calculator.py <<'PY'
import unittest
from calculator import add

class Addition(unittest.TestCase):
    def test_positive(self): self.assertEqual(add(2, 3), 5)
    def test_negative(self): self.assertEqual(add(-2, 1), -1)
    def test_zero(self): self.assertEqual(add(0, 0), 0)
PY
python3 -m unittest -v
```

Expect three baseline failures. Save the unchanged fixture checksums **outside** the agent's working directory:

```bash
python3 - <<'PY' > "$TRIAL_DIR.expected-sha256.json"
import hashlib, json
from pathlib import Path
print(json.dumps({p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                 for p in ['test_calculator.py', 'opencode.json']}))
PY
export INFERENCE_BASE_URL=https://SITE_INFERENCE_HOST/v1
read -r -s -p 'Commissioning user API key: ' INFERENCE_API_KEY
export INFERENCE_API_KEY
export OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=32768
opencode --version
opencode run --dir "$TRIAL_DIR" --model inference/qwen-coder \
  'Fix numeric addition in calculator.py. Read the files, run python3 -m unittest -v, edit only calculator.py, and rerun the tests. Do not modify tests or configuration.'
python3 -m unittest -v
python3 - <<'PY'
import hashlib, json, os
from pathlib import Path
expected = json.loads(Path(os.environ['TRIAL_DIR'] + '.expected-sha256.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in expected.items())
print('Tests and client configuration unchanged')
PY
unset INFERENCE_API_KEY
```

Pass only when the agent actually edits `calculator.py`, all three tests pass, the integrity check passes and the gateway attributes usage to the commissioning key. Save the client version, transcript, timings and test output in private acceptance records. This small task tests client integration, not general coding quality. Retain commissioning-only access until section 6 passes, then revoke the commissioning key and issue model-scoped, budgeted user keys through the [operations guide](../operate/administration.md). The client uses the [recommended thinking and tool-calling settings](agent-settings.md), with 262144 total context and 32768 output tokens; these are configured limits, not measured capacity. [OpenCode CLI](https://opencode.ai/docs/cli/), [project configuration](https://opencode.ai/docs/config/)

## 6. Qualify 200K context separately

The service starts directly at **262,144 total tokens**, with a client output allowance of **32,768 tokens**. vLLM's context limit covers prompt **and** output; see [engine arguments](https://docs.vllm.ai/en/latest/configuration/engine_args/#--max-model-len). Input includes conversation history, tool definitions and tool results. This provides headroom for a 200,000-token input without claiming that every coding task needs that much context.

The recorded RTX demo previously processed 200041 input tokens; [historical evidence](../../evidence/rtx-capacity-and-agent-summary.json) is not B200 MIG acceptance. Run the following on the **gateway host**, while the allocated model is healthy and access is restricted to commissioning users:

```bash
python3 scripts/keys.py create context-acceptance \
  --daily-tokens 1000000 --out runtime/secrets/context-acceptance.key
python3 scripts/context_probe.py \
  --base-url http://127.0.0.1:4001/v1 \
  --backend-url http://COMPUTE_NODE_PRIVATE_NAME:8000 \
  --backend-key-file runtime/secrets/backend.key \
  --key-file runtime/secrets/context-acceptance.key \
  --prompt-tokens 200000 --output-tokens 32768 --context-limit 262144 \
  --out runtime/b200-context-200k.json
```

Replace the backend address and port with the same allocated endpoint used by the gateway, **without `/v1`**: the probe calls the backend's `/tokenize` route. The private backend key and network isolation still apply. If rerunning, reuse the existing temporary key or revoke it and choose a new key name/file; do not overwrite a credential blindly. The standalone demo uses `http://127.0.0.1:8000` for this backend URL.

**Expected:** the report contains `"passed": true`, actual `usage.prompt_tokens` of at least `200000`, `"needle_retrieved": true` and `"finish_reason": "stop"`, with a completed stream and no streamed error. A successful small prompt or server startup alone does not pass this step. The test uses thinking mode and permits up to 32768 output tokens, including reasoning, but the retrieval response is short; it does not prove sustained generation of all 32768 tokens.

Complete acceptance in this order:

1. At the configured 262144 limit, check successful model/KV-cache allocation and run the gateway smoke test.
2. Run the long-context command above; retain the JSON report, job ID, actual device/profile and artifact pins. Collect peak GPU memory separately through site monitoring. The probe records time to first content and total duration, not GPU peak memory.
3. Repeat with representative repository context, long tool results and realistic output lengths. If OpenCode is the intended client, run an edit/test workflow too. Synthetic retrieval demonstrates capacity, not general coding quality.
4. Keep one active sequence until queueing latency is acceptable. Test concurrency separately before increasing it.
5. Revoke the temporary test key using its resource ID from `python3 scripts/keys.py list`, and remove its private key file after revocation.

If startup or the 200K request runs out of memory, **the 200K deployment has not passed**. Inspect the allocated slice, free memory, KV-cache allocation and runtime settings. Smaller contexts may be used as explicit diagnostic experiments, but do not silently lower the server or client limits and still advertise 200K. Restore the intended configuration and rerun acceptance, or document an explicitly reduced service specification.

## 7. Acceptance and handover

Include the signed section 4.1 isolation record and the passing section 6 long-context report in handover. Missing evidence means the deployment is not accepted for user use, even when all ordinary gateway tests pass.

Run the same gateway acceptance test from the new host; save a distinct B200 evidence report. Verify an ordinary key cannot access administration, keys/budgets survive a gateway restart, revocation propagates, SQLite restores successfully, and an allocated job shutdown gives a visible service failure instead of silently routing to another model. Agree on job renewal, maintenance windows, backup ownership and log retention before users depend on the endpoint.

The current sample has no configured request-rate or per-user concurrency limits. Per-key daily token budgets do not provide fair scheduling: one caller can queue many requests or occupy the single active sequence with long context. Start with a supervised pilot, agree on request/output limits and acceptable queue time, and test two competing users before opening class-wide access. The 262144/32768 limits in `client/opencode.json` are client settings, not server-enforced limits for arbitrary API clients. Admission controls must be enforced at the gateway/backend. Native local rate limits can operate without another database service, but their settings and behavior must be validated before adoption. [Agentgateway rate limits](https://agentgateway.dev/docs/standalone/latest/documentation/configuration/resiliency/rate-limits/)

Record a named primary and backup owner for Slurm job renewal, key issue/revocation, backups and restore, monitoring, database retention and incident response. Attach the site-input record, artifact hashes, isolation approval, HTTPS/API reports, OpenCode test, accepted context/concurrency values, restore-drill result and the agreed service hours. Do not promise uninterrupted availability from an eight-hour batch allocation.

## 8. Stop, renew and recover the inference job

During an agreed maintenance window, the inference service owner closes or pauses new user admission, records the exact job ID and stops only this service's allocation:

```bash
scancel JOB_ID_RECORDED_FOR_THIS_SERVICE
squeue -j JOB_ID_RECORDED_FOR_THIS_SERVICE
```

Confirm the allocation has ended and the gateway reports an upstream service failure. Do not use a broad user-wide cancellation. Return to section 3 to resubmit with the approved account, partition, MIG GRES, duration and reservation; record the new job ID/node. Verify startup, backend identity and health. If the node or port changes, keep user admission closed, edit only `VLLM_BASE_URL` in the gateway's private `.env` and run `docker compose up -d --force-recreate gateway` on the CPU host. Then repeat the section 4.1 isolation gate against the new target, followed by the real HTTPS route and OpenCode smoke task, before reopening access.

This sample does not automatically renew Slurm allocations. Configure an administrator-approved renewal/controller process or a manual duty schedule before service launch. Use the [backup and restore procedure](../operate/administration.md#back-up-and-restore) for the gateway; preserve the persistent local SQLite directory when renewing the inference job. Drill restore separately before users depend on the service.
