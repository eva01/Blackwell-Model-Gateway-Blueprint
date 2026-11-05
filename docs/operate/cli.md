# Control the gateway from the terminal

[Documentation](../README.md) · [Prerequisites](../start/prerequisites.md) · [Administration](administration.md)

Use `./gateway` on the **Linux gateway host**, from the repository root, as the service owner. It wraps Docker Compose and the existing Python helpers. No extra Python packages are needed. The commands manage the gateway; Slurm and the inference launcher continue to manage the model separately.

For a new server, first follow [prerequisites](../start/prerequisites.md), then the [B200 installation](../deploy/b200-slurm.md) or [standalone demo](../start/install.md). `./gateway start` expects bootstrap to have created the private `.env`, credentials and data directories.

## Everyday commands

| Command | Result |
|---|---|
| `./gateway` or `./gateway --help` | Show available commands |
| `./gateway prerequisites` | Check gateway-host packages and local Docker access |
| `./gateway prerequisites --install` | Install missing prerequisites on supported Ubuntu hosts |
| `./gateway start` | Create/start the gateway container using the current Compose configuration |
| `./gateway status` | Show the container and whether the gateway readiness endpoint responds |
| `./gateway logs` | Show the last 100 gateway log lines |
| `./gateway logs --follow --tail 200` | Follow logs; press Ctrl+C to stop watching |
| `./gateway restart` | Restart the gateway |
| `./gateway stop` | Stop the gateway, preserving its database and secrets |
| `./gateway users list` | Show user-key IDs, names, model scopes and budgets |
| `./gateway usage` | Show recorded per-user totals for the last 24 hours |
| `./gateway backup` | Save a new private SQLite snapshot under `runtime/backups/` |

Use `./gateway COMMAND --help` for options. A nonzero exit status means the command failed; `status` also exits nonzero when the gateway is not ready. Readiness alone does not confirm that the model is available. These commands do not run inference or acceptance tests.

The wrapper uses the local Docker `default` context and Compose project `qwen-agentgateway`. It refuses `DOCKER_HOST` and `DOCKER_CONTEXT` overrides so a command on this host does not silently control a remote deployment. Do not use it to manage a differently named existing project until you complete [migration](administration.md#migrate-an-existing-installation).

`restart` does not reread changed Compose environment values. After editing `.env` or `compose.yaml`, use `./gateway start`; Compose recreates the gateway if its configuration changed. Expect a brief service interruption when recreating or restarting it.

## Give a user access

Create a key with a deliberate daily budget:

```bash
./gateway users add developer-a --daily-tokens 1000000
```

The secret is written to `runtime/secrets/developer-a.key` with mode `0600`. It is not printed. The gateway stores its hash and limits the key to `qwen-coder`. Transfer the file through your approved secret channel. The command refuses to overwrite an existing file.

For another output location or a replacement key, choose a new private filename:

```bash
./gateway users add developer-a --daily-tokens 1000000 \
  --out /PRIVATE/EXISTING/DIRECTORY/developer-a-rotation.key
```

Replace the example path with an existing private directory. Paths passed with `--out` are relative to your current terminal directory unless absolute. Creating another key does not revoke the earlier one. Names can repeat; resource IDs identify individual keys.

To deliberately create a key without a budget, use `--unlimited` instead of `--daily-tokens`. The command requires one of these choices. Budget accounting and reset behavior are described in [Usage and budgets](administration.md#usage-and-budgets).

List keys and revoke an individual key using its **KEY ID**:

```bash
./gateway users list
./gateway users revoke KEY_ID_FROM_LIST
```

Revocation takes a short interval to propagate, and an in-flight request can finish. Local secret files are not deleted automatically. `./gateway users list --json` provides complete metadata without exposing secret values or hashes.

## Read usage

```bash
./gateway usage
./gateway usage --days 7
./gateway usage --all --user developer-a
./gateway usage --days 7 --json
```

The command queries the local SQLite database in read-only mode and groups persisted requests by user. It shows request count, input/output tokens, errors and requests missing token usage. The default is a rolling 24-hour reporting window, distinct from the budget reset boundary. A user with no recorded requests in the selected window has no row; missing attribution is shown explicitly.

Totals can lag while requests are running or logs are being written. The report does not calculate remaining key budgets, GPU billing or estimated tokens for responses without usage. It reads metadata only, not prompt or response payloads.

## Save a database backup

```bash
./gateway backup
./gateway backup --out /PRIVATE/EXISTING/BACKUP_DIRECTORY/gateway.db
```

Each default backup uses a new UTC timestamped filename. The helper uses SQLite's online backup API, checks snapshot integrity and refuses to overwrite an existing destination. The file has mode `0600`.

This is a **database snapshot**, not a full recovery archive. Back up the matching configuration and secrets separately through the site's encrypted off-host process. Follow [backup and restore](administration.md#back-up-and-restore) to restore; a copy on the same disk does not protect against losing that disk.

## If a command fails

| Message or symptom | Next step |
|---|---|
| Permission denied when invoking `./gateway` | If your ZIP extractor lost executable permissions, run `chmod +x gateway`, or invoke `sh gateway --help` |
| Python is missing | `./gateway prerequisites --install` can bootstrap Python on supported Ubuntu hosts |
| Gateway is not initialized | Complete bootstrap in the installation guide; do not invent credentials or run it over existing state |
| Docker is missing or inaccessible | Run the prerequisite check; have the administrator approve Docker access for the service owner |
| Administrator HTTP 401/403 | Check `runtime/secrets/admin.json` against the running gateway's administrator login |
| Key output already exists | Choose a new `--out` filename; do not overwrite a user's existing secret |
| No database or no request-log table | Start the pinned gateway and let it initialize its database before reporting usage |
| Unsupported schema after changing gateway versions | Use the pinned version or adapt the metadata query to that version's schema |

The CLI and installer were source-reviewed but not executed in this update, at the user's request. No live-service or package-installation result is implied.
