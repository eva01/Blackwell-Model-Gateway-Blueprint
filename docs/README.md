# Documentation: start here

[← Repository overview](../README.md)

**Default installation: B200 MIG 4g.90gb with a 200K-input service target.** If you are new, begin with the [README's step-by-step installation path](../README.md#install-step-by-step): choose the host, obtain the files, check packages, follow the matching runbook, make a request, then qualify the deployment. The RTX PRO 6000 Blackwell path is for demos.

**An AI coding agent can help you install it.** Open the repository in an already-working agent with approved terminal/SSH access and give it the [copy-and-paste installation prompt](../README.md#install-with-an-ai-agent). It follows the same manual guide; you supply the site details and administrator access. The hosted model and optional OpenCode client are configured afterward, so the new service is not needed to power the installation assistant.

Manual installation remains complete and requires no AI agent. Your first success is an authenticated API reply; accepting a 200K service also requires the real long-context and tool-calling checks.

## First commands on the gateway host

After downloading the project, enter its root directory and run:

```bash
./gateway prerequisites
```

On supported Ubuntu 24.04 x86-64 hosts, install missing packages with `./gateway prerequisites --install`, then repeat the check. For a standalone GPU demo, add `--role demo` to each command. Complete administrator-owned driver, account-access and runtime steps in [Prerequisites](start/prerequisites.md); do not install Docker on Slurm compute nodes. If a ZIP lost executable permissions, use `sh gateway prerequisites` or restore them with `chmod +x gateway`.

Next, follow the selected installation guide below through model launch and gateway bootstrap. `./gateway start` only manages an already-configured gateway. After setup, use `./gateway status`, `./gateway users list`, `./gateway usage` and `./gateway backup`; the [CLI guide](operate/cli.md) explains every command.

## Choose your path

| Your situation | Reading order | Finished when |
|---|---|---|
| You want an AI agent to help install | [Installation prompt](../README.md#install-with-an-ai-agent) → matching runbook below | Agent reports what was installed, the first reply, completed checks and any blockers |
| **Primary installation: B200 MIG 4g.90gb** | Administrator follows [B200 cluster deployment](deploy/b200-slurm.md) | Allocation, isolation, gateway, client and 200K-input checks pass |
| You want a standalone RTX demo | [Demo installation](start/install.md) → [Administration](operate/administration.md) | The API and relevant acceptance checks pass |
| Your demo server needs prerequisites | Administrator completes [Host setup](start/host-setup.md) → [Demo installation](start/install.md) | The demo API and acceptance checks pass |
| You need to check/install gateway-host packages | [Prerequisites](start/prerequisites.md) | Required packages and operator access are ready |
| You want simple terminal controls | [Gateway CLI](operate/cli.md) | You can manage the gateway, keys, usage and backups |
| You only need to call an existing service | Obtain the gateway URL, individual user key and model name from its operator | Your client can make an authenticated request |
| You maintain or customize the code | [Architecture](reference/architecture.md) → [Implementation](reference/implementation.md) | You understand the components and can run local checks |

For an API-only user, the operator supplies access details; there is no reason to install a second model server. For the standalone example, the installer follows one main guide from beginning to end. The cluster runbook is the primary deployment path; the standalone guide is a separate demo path.

## Start — first installation

| Guide | Who reads it | What it covers |
|---|---|---|
| [Standalone demo installation](start/install.md) | Demo installer | Server/laptop commands, configuration edits, first API request, expected results and troubleshooting |
| [Host setup](start/host-setup.md) | Linux administrator | Preparing a new Ubuntu demo host, Docker access and NVIDIA Container Toolkit |
| [Prerequisite checklist and installer](start/prerequisites.md) | Gateway or demo installer | Packages by machine role, missing-package installation and manual administrator steps |

The manual guide introduces the terminology and credential types. It marks which terminal to use, and makes OpenCode optional. Ask the administrator to resolve missing driver, host permissions or hardware allocation before starting the application steps.

## Deploy — hardware and model choices

| Guide | When to use it |
|---|---|
| [GPU compatibility](deploy/gpu-compatibility.md) | Confirming RTX Blackwell versus B200, or diagnosing preflight failures |
| [B200 with Slurm](deploy/b200-slurm.md) | Deploying on a scheduler-managed MIG slice with a separate gateway host |
| [Use a different model](deploy/change-model.md) | Adapting the example after the original installation works |
| [Coding-agent settings and tool calling](deploy/agent-settings.md) | Connecting OpenCode or implementing a tool loop with the recommended Qwen defaults |

## Operate — after installation

[Gateway CLI](operate/cli.md) is the quick command reference for daily operation. [Administration](operate/administration.md) explains user keys, the browser playground, usage accounting, backups, restore, troubleshooting and migration.

## Reference — deeper detail and historical evidence

| Document | Purpose |
|---|---|
| [Architecture](reference/architecture.md) | Component responsibilities, storage and access boundaries |
| [Implementation map](reference/implementation.md) | File responsibilities and local development checks |
| [Validation](reference/validation.md) | What was tested, historical results and remaining acceptance work |
| [Release audit](reference/release-audit.md) | Dated upstream version observations for the included example |
| [Sources](reference/sources.md) | Upstream documentation supporting the design |

These references support review and troubleshooting. They are not additional installation steps. Historical reports do not certify a new server or a different model.

## Command conventions

Commands in the guides run from the **repository root** unless the step says otherwise. Moving the documentation into subfolders does not change where scripts run. Follow the stated host and terminal labels, replace placeholders before running commands, and stop when a check fails.

For example, `python3 scripts/bootstrap.py ...` runs from the directory containing `compose.yaml`, not from this documentation directory. The guide gives the complete arguments at the point they are needed.
