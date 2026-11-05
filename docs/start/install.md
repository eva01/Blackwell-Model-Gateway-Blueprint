# Standalone demo: Blackwell Model Serving Blueprint

[Documentation](../README.md) · [← Overview](../../README.md) · [Prepare a Linux host](host-setup.md) · [B200 cluster installation](../deploy/b200-slurm.md)

Use the [prerequisite checker and installer](prerequisites.md) to prepare packages. Once bootstrap is complete, the [Gateway CLI](../operate/cli.md) provides short commands for daily operation.

If you prefer help from an AI coding agent, give it the [installation prompt](../../README.md#install-with-an-ai-agent) and select the standalone demo path. The commands below also work when followed manually.

**You do not need an AI agent to install or test this service.** Follow the commands manually, one block at a time. This guide takes you from a prepared Linux server to a working API with individual user keys and recorded usage. OpenCode is an optional client at the end.

The primary installation is **B200 MIG 4g.90gb**: follow the [manual B200/Slurm guide](../deploy/b200-slurm.md). This page is the **RTX PRO 6000 Blackwell standalone demo**, also usable with an assigned full B200. The launcher detects either device automatically. The included model is Qwen NVFP4. Other models need their own serving settings and validation; see [adapting the example](../deploy/change-model.md).

## Installation route

| Step | You will finish with |
|---|---|
| [Before you begin](#before-you-begin) | The right account, host details and terminal setup |
| [1. Prepare](#1-prepare-the-host-and-project) | A verified project copy on a prepared host |
| [2. Configure](#2-create-the-backend-configuration) | GPU settings and a private backend key |
| [3. Start the model](#3-check-the-gpu-and-start-the-model) | A healthy model server |
| [4. Start the gateway](#4-start-the-gateway) | An authenticated API endpoint |
| [5. Create a user](#5-issue-an-individual-user-key) | An individual model-scoped key |
| [6. Make a request](#6-test-the-api-without-an-ai-agent) | A real reply and token usage |
| [7. Verify](#7-run-acceptance-checks) | A passing acceptance report |
| [8. Operate](#8-share-and-operate) | A clear service handover and recovery path |

[Optional OpenCode client](#optional-connect-opencode) · [Troubleshooting](#troubleshooting)

## Before you begin

You need an SSH account on the server, its address, the project download or repository URL, and an assigned GPU. An administrator must prepare the driver, Docker/Compose and NVIDIA Container Toolkit first. For a new Ubuntu host, give them [Host setup](host-setup.md). The installer needs basic terminal access, not model-development experience.

| Term | Meaning in this guide |
|---|---|
| Server | The Linux machine with the GPU; both vLLM and the gateway run here |
| Laptop | The computer you use to connect to the server and open the browser |
| vLLM | The program that loads the model and generates responses |
| Gateway | The service that checks user keys, routes requests and records usage |
| Backend key | Private credential used between the gateway and vLLM |
| User key | Individual credential used to call the gateway |
| Admin login | Separate username/password for managing users and viewing usage |

Use **Bash** for the command blocks. If your terminal uses another shell, type `bash` first. Copy the entire block, including closing `PY` lines in Python examples. Do not copy the Markdown backticks. Replace example values such as `operator@server.example` before running them. If a command fails, stop and use [Troubleshooting](#troubleshooting) before continuing.

Open these terminals as needed:

| Terminal | Location | Purpose |
|---|---|---|
| A | SSH session on the server | Run the model; keep this open |
| B | Second SSH session on the same server | Configure and test the gateway |
| C | Your laptop | Keep the browser/API SSH tunnel open |

## 1. Prepare the host and project

**Where: terminal A, on the server.** From your laptop, connect using the account and address your administrator supplied:

```bash
ssh operator@server.example
bash
```

Check the prepared host:

```bash
id -un
nvidia-smi
python3 --version
docker version
docker compose version
command -v htpasswd
```

**Expected:** your service account, the assigned GPU, Python 3.10 or newer, Docker client **and server** details, a Compose version, and a path to `htpasswd`. If anything is missing, finish [Host setup](host-setup.md). Do not run the project as root.

Get the project using **one** of these methods.

**Already downloaded it while following the README?** Keep that same project directory. Skip Option A and Option B below, then continue at “From the project directory, verify the files.” Complete those checks and record the path before proceeding to section 2. Do not clone into an existing project directory.

**Option A — repository:** paste the repository URL provided by the maintainer when prompted. This does not assume a particular organization or repository name.

```bash
mkdir -p "$HOME/services"
cd "$HOME/services"
read -r -p 'Repository URL: ' REPOSITORY_URL
git clone "$REPOSITORY_URL" blackwell-model-serving
cd blackwell-model-serving
```

**Option B — release ZIP:** upload the supplied ZIP to the server, extract it into a fresh directory with `unzip`, then `cd` into the extracted directory containing `README.md` and `compose.yaml`. For example, from your laptop:

```bash
scp /path/to/release.zip operator@server.example:release.zip
```

Then on the server:

```bash
mkdir -p "$HOME/services/blackwell-release"
cd "$HOME/services/blackwell-release"
unzip "$HOME/release.zip"
ls
```

The ZIP may contain a top-level directory. Open that directory with `cd DIRECTORY_SHOWN_BY_LS`; if `README.md` and `compose.yaml` are already listed, stay where you are.

From the project directory, verify the files:

```bash
pwd
ls README.md compose.yaml
sha256sum -c MANIFEST.sha256
python3 -m unittest discover -s tests -v
df -h .
```

**Expected:** checksums report `OK`, tests finish with `OK`, and storage is sufficient for the image and model downloads. Write down the absolute path printed by `pwd`; use that same path in terminal B. Stop on checksum errors and obtain an intact package.

## 2. Create the backend configuration

**Where: terminal A, project directory.** These commands are for a fresh installation:

```bash
umask 077
mkdir -p runtime/secrets runtime/model-cache
cp -n inference/backend.env.example inference/backend.env
chmod 600 inference/backend.env
(set -o noclobber; openssl rand -hex 32 > runtime/secrets/inference.key)
pwd
nano inference/backend.env
```

The key command refuses to overwrite an existing file. If this installation already exists, reuse its credentials and follow [migration/operations](../operate/administration.md#migrate-an-existing-installation); do not delete secrets to bypass an error.

In the editor, change the following values, keeping the other lines intact. Replace `/YOUR/PROJECT/PATH` with the absolute path printed by `pwd`. Add the `PROTOTYPE_GPU` line if absent:

```bash
GPU_PROFILE=auto
PROTOTYPE_GPU=0
MODEL_CACHE="/YOUR/PROJECT/PATH/runtime/model-cache"
BACKEND_KEY_FILE="/YOUR/PROJECT/PATH/runtime/secrets/inference.key"
```

In nano, press **Ctrl+O**, **Enter** to save, then **Ctrl+X** to exit. On a Mac keyboard, use Control, not Command.

| Your allocation | `GPU_PROFILE` | GPU selection |
|---|---|---|
| RTX PRO 6000 Blackwell demo | `auto` | Assigned index from `nvidia-smi`, often `0` |
| Standalone full B200 | `auto` | Assigned index from `nvidia-smi` |
| Slurm-managed GPU/MIG | Follow the cluster guide | Slurm owns device selection |

Keep `MAX_MODEL_LEN=262144` and `MAX_NUM_SEQS=1`: the service starts directly with room for 200K input plus output. `VLLM_SQSH` is only used by Slurm and is ignored here. The environment file is shell code; only source the file you control.

Confirm that the paths you entered work, without displaying the key:

```bash
bash -c 'source inference/backend.env; test -d "$MODEL_CACHE" && test -s "$BACKEND_KEY_FILE" && echo "Paths and key: OK"'
```

**Expected:** `Paths and key: OK`. If absent, reopen the file and correct the paths.

## 3. Check the GPU and start the model

**Where: terminal A.** Run the compatibility check first:

```bash
bash inference/prototype-docker.sh --check-gpu
```

The first run may download the container. **Expected:** a JSON report containing `"visible_devices": 1`, `"cuda_smoke_test": "passed"`, and compute capability `12.0` for the RTX demo or `10.0` for B200. A successful check does not yet test model weights or NVFP4 inference.

Start the model:

```bash
bash inference/prototype-docker.sh
```

Leave this terminal open. The model downloads on first startup and the command continues running in the foreground. Do not press Ctrl+C unless you intend to stop it.

**Open terminal B:** SSH to the same server, start Bash and enter the project path recorded in step 1:

```bash
ssh operator@server.example
bash
cd /YOUR/PROJECT/PATH
curl --fail --silent --show-error --output /dev/null --write-out 'Model health: HTTP %{http_code}\n' http://127.0.0.1:8000/health
```

**Expected:** `Model health: HTTP 200`. If loading is still in progress, wait and rerun the health command. If terminal A reports an error or exits, diagnose it before continuing.

## 4. Start the gateway

**Where: terminal B, project directory.** Bootstrap supplies the model's backend key to the gateway and generates a separate administrator login:

```bash
python3 scripts/bootstrap.py \
  --backend-key-file "$PWD/runtime/secrets/inference.key" \
  --backend-url http://127.0.0.1:8000/v1
docker compose config --quiet
docker compose run --rm gateway --validate-only -f /config/gateway.yaml
```

**Expected:** `Initialized`, followed by successful configuration checks. Some checks print nothing on success. On any error, stop before the next block. If you already have vLLM, use its existing backend key and URL; the example expects the backend model alias `qwen`.

```bash
./gateway start
./gateway status
curl --fail --silent --show-error --output /dev/null --write-out 'Gateway readiness: HTTP %{http_code}\n' http://127.0.0.1:15022/healthz/ready
```

**Expected:** gateway status is running and readiness returns HTTP 200. If it has just started, retry the readiness request. If it exits, inspect `./gateway logs`.

The files in `runtime/secrets` are private credentials. The directory `runtime/data` holds SQLite state, including keys and usage. Keep both when restarting. No separate database installation is needed.

## 5. Issue an individual user key

**Where: terminal B.** Create a sample user with a daily token allowance:

```bash
./gateway users add developer-a \
  --daily-tokens 1000000 --out runtime/secrets/developer-a.key
./gateway users list
```

**Expected:** the list includes `developer-a` with allowed model `qwen-coder`. The raw key is stored in the named private file; the listing deliberately does not print it. Allow a short interval for a newly created key to become active. Use a distinct name and file for each later user.

## 6. Test the API without an AI agent

**Where: terminal B.** This uses Python's built-in HTTP client, reads the key from its private file and submits a small prompt. No OpenCode, paid API account or Python package installation is needed.

```bash
python3 - <<'PY'
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

key = Path("runtime/secrets/developer-a.key").read_text().strip()
request = Request(
    "http://127.0.0.1:4001/v1/chat/completions",
    data=json.dumps({
        "model": "qwen-coder",
        "messages": [{"role": "user", "content": "Say hello in one sentence."}],
        "max_tokens": 32768,
        "stream": False,
    }).encode(),
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
)
try:
    with urlopen(request, timeout=1800) as response:
        result = json.load(response)
        print("HTTP:", response.status)
    print("Reply:", result["choices"][0]["message"]["content"])
    print("Token usage:", result.get("usage"))
except HTTPError as error:
    raise SystemExit(f"Request failed: HTTP {error.code}; see the troubleshooting table")
except URLError as error:
    raise SystemExit(f"Cannot reach the gateway: {error.reason}")
PY
```

**Expected:** HTTP 200, a short reply and input/output token usage. The exact reply varies. This confirms a request passed through the gateway to the model.

The request inherits the gateway's thinking-mode defaults. Its output allowance includes reasoning and the final answer; it does not request a 32K-token answer. See [Coding-agent settings and tool calling](../deploy/agent-settings.md) before connecting an agent.

### Open the administrator interface

In **terminal C on your laptop**, run the following and leave it open. Replace the account and hostname:

```bash
ssh -o ExitOnForwardFailure=yes -N \
  -L 14002:127.0.0.1:14002 -L 4001:127.0.0.1:4001 \
  operator@server.example
```

A connected tunnel normally prints nothing and keeps running. On your laptop, open **http://127.0.0.1:14002/ui/** in a browser.

In terminal B, retrieve the administrator login for your own use:

```bash
cat runtime/secrets/admin.json
```

Sign in with the `username` and `password` from that file. Do not paste this output into support tickets or give it to API users. In **LLM → Virtual API Keys**, confirm the user and budget. Use the UI's usage/request views to inspect the sample request; names can differ by UI version. The acceptance test below verifies durable per-user usage in SQLite.

To test in the browser as an administrator, open **LLM → Playground**, apply CORS for the exact origin `http://127.0.0.1:14002` if prompted, select `qwen-coder`, choose **Raw value**, and paste the contents of `runtime/secrets/developer-a.key` into **Raw API key**. Submit a short message. Both SSH forwards are required. [Playground details](../operate/administration.md#browser-playground)

## 7. Run acceptance checks

**Where: terminal B.** Run this before inviting users; it intentionally restarts this gateway:

```bash
python3 scripts/verify.py --restart --out runtime/gateway-acceptance.json
```

**Expected:** the report ends with `"passed": true`. This smoke test uses short prompts; it does not validate the advertised long context. It tests authentication, model scope, budgets, streaming, tool calls, revocation, persistent usage and restart behavior. It creates/revokes temporary keys and does not restart vLLM.

This diagnostic deliberately disables thinking and forces one non-streaming tool call. It does not qualify thinking-mode, automatic or streamed tool calling; follow the [client integration procedure](../deploy/agent-settings.md#4-use-tools-from-your-client) for that path when a server is available.

If it fails, read the `failure` field, correct the cause and rerun. Then follow the [200K-input acceptance procedure](../deploy/b200-slurm.md#6-qualify-200k-context-separately), using `http://127.0.0.1:8000` as the backend URL for this standalone host. Keep both reports with the GPU preflight output and image/model pins. A working RTX demo does not prove a B200 deployment works.

## 8. Share and operate

The demo is ready for a supervised local trial when steps 3, 4, 6 and 7 pass, including the long-context check for a 200K service. Before wider access, assign an operator to configure [HTTPS and backend isolation](../deploy/b200-slurm.md#5-expose-the-user-api-through-the-existing-tls-ingress), backups and service lifecycle. Give ordinary users only their own key, the HTTPS `/v1` URL and model name `qwen-coder`; they do not need the administrator UI.

| Task | Manual action |
|---|---|
| See gateway logs | `./gateway logs` |
| Restart gateway | `./gateway restart` |
| Stop gateway | `docker compose down` — keep `runtime/` |
| Start gateway again | `./gateway start` |
| Stop model | Ctrl+C in terminal A |
| Start model again | From the project directory: `bash inference/prototype-docker.sh` |
| Revoke a user key | `./gateway users list`, then `./gateway users revoke RESOURCE_ID_FROM_LIST` |
| Back up state | Follow [backup and restore](../operate/administration.md#back-up-and-restore) |

The model's foreground launch is a commissioning workflow. Closing its SSH session can stop the service. Arrange an operator-managed service lifecycle before promising continuous availability. Loopback binding does not isolate other local users on a shared host; complete the [shared-host isolation procedure](../deploy/b200-slurm.md#41-mandatory-backend-isolation-execution-and-evidence) there.

## Optional: connect OpenCode

Install this only if you want an agent client after the API is working. On your laptop, follow the [official OpenCode installation instructions](https://opencode.ai/docs/) and check `opencode --version`. This sample's recorded client is OpenCode 1.19.5; a different version needs client acceptance.

Obtain a local copy of this package. In a Bash terminal on your laptop, enter its directory, then copy the supplied configuration into a **new** scratch directory:

```bash
cd /PATH/TO/LOCAL/PACKAGE
CLIENT_TRIAL_DIR=$(mktemp -d)
cp client/opencode.json "$CLIENT_TRIAL_DIR/opencode.json"
cd "$CLIENT_TRIAL_DIR"
export INFERENCE_BASE_URL=http://127.0.0.1:4001/v1
read -r -s -p 'Your individual user key: ' INFERENCE_API_KEY
printf '\n'
export INFERENCE_API_KEY
export OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=32768
opencode --model inference/qwen-coder
unset INFERENCE_API_KEY
```

Keep terminal C's tunnel open. Paste the individual user key at the prompt; it is intentionally hidden while typing. For a published service, replace the base URL with its HTTPS URL ending in `/v1`. The scratch directory avoids overwriting existing client settings. For a repeatable edit/test task, use the [OpenCode acceptance exercise](../deploy/b200-slurm.md#51-verify-opencode-on-an-ordinary-client).

## Troubleshooting

| What you see | What to do next |
|---|---|
| `command not found` | Check the command spelling and finish [Host setup](host-setup.md) |
| Cannot connect to Docker daemon / permission denied | Ask the administrator to check Docker and account access; log in again after group changes |
| Checksum mismatch | Obtain an intact package; do not continue with unknown files |
| Unsupported device / profile mismatch | Keep `GPU_PROFILE=auto` and check the allocated device; only B200 and RTX PRO 6000 Blackwell are recognized |
| No GPU visible / CUDA error | Have the administrator check driver/toolkit compatibility and allocation; see [GPU compatibility](../deploy/gpu-compatibility.md) |
| Container name already in use | Inspect `docker ps -a --filter name=qwen-prototype`; confirm whether this service is already running before stopping anything |
| Model download returns 401/403 | Ask the maintainer for the required registry/model access or mirror configuration; keep tokens out of committed files |
| Health request fails | Read terminal A; wait if loading, otherwise resolve the startup error |
| Bootstrap says already initialized | Reuse existing state; do not rerun first-time setup or delete the database |
| User request returns 401 | Wait briefly after key creation, then confirm the key file belongs to this gateway |
| User request returns 403 | Confirm the user's allowed model is `qwen-coder` |
| User request returns 429 | Check the key's budget and server load |
| Upstream error / failed generation | Check model health, backend URL, matching backend key and gateway logs |
| Browser cannot connect | Keep terminal C open; check its SSH errors and use `127.0.0.1:14002`, not port 8000 |
| Local forwarding port already in use | Close the previous tunnel for this service, then retry; do not terminate an unknown process |
| Out of GPU memory | Keep one sequence; check actual memory and other workloads. A smaller context is an explicit troubleshooting choice, not acceptance of the 200K service |

If blocked, give your administrator the failed step, error message, GPU model, driver version, container/model pins and a redacted log excerpt. Do not share `runtime/secrets`, `.env`, the private backend environment or the SQLite database. No AI assistant is required to complete this handover.
