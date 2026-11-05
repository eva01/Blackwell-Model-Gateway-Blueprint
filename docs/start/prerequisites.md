# Prerequisites and package installation

[Documentation](../README.md) · [Gateway commands](../operate/cli.md) · [Manual host setup](host-setup.md)

Choose the machine you are preparing. The **default B200 deployment has a CPU gateway host and a separate Slurm GPU allocation**. Install gateway packages on the CPU host; the cluster administrator supplies the compute-node stack. An RTX demo puts both roles on one dedicated Linux server.

## Package checklist

| Machine | Required component | Package or source |
|---|---|---|
| Gateway and demo hosts | Bash and standard command-line utilities | Ubuntu `bash`, `coreutils`, `grep`, `sed` |
| Gateway and demo hosts | Python 3.10+ with SQLite and TLS support | Ubuntu `python3`; helpers use its standard library |
| Gateway and demo hosts | HTTPS downloads and trust roots | `curl`, `ca-certificates` |
| Gateway and demo hosts | Repository signing tools | `gnupg` |
| Gateway and demo hosts | Backend-key generation | `openssl` |
| Gateway and demo hosts | Administrator password hashing | `apache2-utils` supplies `htpasswd` |
| Gateway and demo hosts | Project download/extraction and editing | `git`, `unzip`, `nano`; Git and ZIP are alternative download paths |
| Gateway and demo hosts | SSH/SCP for access and file transfer | `openssh-client` |
| Remotely managed hosts | SSH service and an authorized login | Site-managed `openssh-server` or equivalent; not installed by this helper |
| Gateway and demo hosts | Docker Engine and Compose plugin | Official Docker repository: `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, `docker-compose-plugin` |
| Ubuntu automatic installer | Package management and service manager | Existing Ubuntu `apt`, `dpkg`, systemd; administrator/root or `sudo` access |
| Standalone GPU demo only | Compatible NVIDIA GPU driver | Administrator-selected version; must satisfy [GPU compatibility](../deploy/gpu-compatibility.md) |
| Standalone GPU demo only | NVIDIA Container Toolkit | Official NVIDIA repository: `nvidia-container-toolkit` and its dependencies |
| B200 compute environment | Slurm, configured GPU GRES/cgroups, Enroot and Pyxis | Site administrator's supported packages/modules; not installed by this helper |
| B200 model-staging host | Hugging Face `hf` CLI | Site-provided `huggingface_hub` CLI environment with access to the approved model source; not installed by the gateway helper |
| B200 compute environment | Compatible NVIDIA driver and pre-created MIG `4g.90gb` device | Site administrator; scheduler assigns the device |
| GPU inference container | Python, PyTorch, CUDA libraries and vLLM | Already included in the pinned NVIDIA vLLM image |
| Gateway container | agentgateway | Already included in the pinned gateway image |
| Optional coding-agent laptop | OpenCode and the language/toolchain used by the user's project | Official OpenCode distribution; project-specific runtimes as needed |
| Published service | HTTPS ingress and certificates | Existing site-managed reverse proxy; the supplied snippet targets NGINX |

No host installation of PyTorch, vLLM, CUDA toolkit, Node.js, a Python package manager, or the `sqlite3` command-line program is required for the gateway CLI. Python's SQLite module is sufficient. Install project runtimes on the agent's machine only when its tools need them. Model files, registry access, DNS, disk space, TLS and firewall policy remain installation requirements even though they are not host packages.

## 1. Check what is available

From the repository root on the gateway host:

```bash
./gateway prerequisites
```

For the standalone GPU demo:

```bash
./gateway prerequisites --role demo
```

The check prints `OK`, `MISSING` or `UNSUPPORTED` and exits nonzero if required checks fail. It checks command availability, Python modules, Docker Compose and access to the local Docker daemon. The demo role also checks driver visibility, `nvidia-ctk` and Docker's registered NVIDIA runtime. These read-only checks do not start a model or qualify GPU kernels.

If executable permissions were lost when extracting a ZIP, use `sh gateway prerequisites`. The prerequisite launcher does not need Python, so it can install Python when missing.

## 2. Install missing packages on Ubuntu

The automatic installer supports **Ubuntu 24.04 LTS x86-64 hosts managed by systemd**. Run it as the intended service owner with administrator-approved sudo access:

```bash
./gateway prerequisites --install
```

On a standalone GPU demo host, use:

```bash
./gateway prerequisites --role demo --install
```

The installer uses Ubuntu packages and the [official Docker](https://docs.docker.com/engine/install/ubuntu/) and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) repositories. It downloads signing keys and installs packages through APT; it does not execute a downloaded installation script. It skips installed base packages and uses `--no-upgrade`; dependency changes can still be required by APT. Installing Docker can start its service, and package-maintenance hooks can affect running services. Use an administrator-approved maintenance window on an existing host.

Existing conflicting container packages or unusable repository definitions stop automatic Docker setup with an explanation. The installer does not remove them or replace the host's container stack. Review such hosts using [manual host setup](host-setup.md). Package versions come from the host's configured repositories at installation time; the application images and model revision remain pinned separately in `versions.json`.

For macOS, Windows, other Linux distributions or cluster-managed compute nodes, use the appropriate administrator-managed setup. This blueprint's host-networked gateway stack runs on Linux; a laptop can edit the repository or run an API client without installing the serving stack.

## 3. Finish administrator-controlled setup

Package installation alone may still leave the check failing. The installer does not change account privileges, install GPU drivers, configure the GPU runtime, partition MIG devices or modify Slurm.

- **Docker access:** follow [service-owner access](host-setup.md#4-give-the-installation-account-docker-access), log out/in if group membership changed, and repeat the check as that account. Docker-group access grants root-level host control. Do not run application bootstrap or the gateway CLI with sudo to bypass an access failure.
- **Demo GPU driver:** the administrator installs the compatible driver and reboots if required. `nvidia-smi` must then see the assigned GPU.
- **Demo GPU runtime:** after toolkit installation, the administrator follows [enable GPUs in Docker](host-setup.md#5-enable-gpus-in-docker) to configure the runtime and schedule the necessary Docker restart. This can affect other containers.
- **B200 cluster:** follow the [Slurm runbook](../deploy/b200-slurm.md). Do not run the Docker installer on compute nodes. Enroot/Pyxis, MIG and device isolation belong to the cluster administrator.

Rerun the appropriate prerequisite check, then continue with [B200 installation](../deploy/b200-slurm.md) or [standalone demo installation](install.md). These setup commands were prepared and source-reviewed; they were not run on a server during this update.
