# Prepare a Linux serving host

[Documentation](../README.md) · [← Manual installation](install.md) · [Overview](../../README.md)

This page prepares a **new, dedicated Ubuntu 24.04 LTS x86-64 server** for the standalone demo. An administrator performs these steps. The application installer can then follow the main guide without an AI assistant. For another distribution, use its supported installation instructions; for Slurm, use the [cluster guide](../deploy/b200-slurm.md) and do not install Docker on compute nodes.

Run one command block at a time. Stop when a command fails. Skip a component's installation if its verification already passes. On an existing host, have its administrator review changes before replacing packages or restarting Docker, which can interrupt other containers.

For the complete package list and an optional missing-package installer, use [Prerequisites](prerequisites.md). On a clean Ubuntu demo host, `./gateway prerequisites --role demo --install` installs base, Docker and toolkit packages. Then complete the driver, service-owner access and GPU-runtime steps below. For a separate CPU gateway host, use the default `gateway` role and omit GPU setup.

## 1. Confirm the host and GPU driver

On the server:

```bash
cat /etc/os-release
uname -m
nvidia-smi
```

**Expected:** Ubuntu 24.04, `x86_64`, and your assigned RTX PRO 6000 Blackwell demo GPU or full B200 visible in `nvidia-smi`.

If `nvidia-smi` is missing or cannot communicate with the GPU, stop here. Have the administrator install the supported driver for this GPU and OS using the [NVIDIA driver guide](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/index.html), reboot if required, and rerun the check. The driver must also satisfy the pinned [vLLM container requirements](../deploy/gpu-compatibility.md#what-makes-the-architecture-portable). Seeing the GPU is necessary but does not establish container compatibility. The CUDA version shown by `nvidia-smi` is not the container's installed toolkit version.

## 2. Install command-line prerequisites

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg python3 openssl apache2-utils git unzip nano
```

**Expected:** the command completes without package errors. `apache2-utils` supplies the password-hashing tool used by bootstrap. Python model packages are already inside the inference image; do not install PyTorch or vLLM on the host.

## 3. Install Docker Engine and Compose

Check first:

```bash
docker version
docker compose version
```

If these already work, skip to step 4. For a clean host, add Docker's official package repository and install the engine and Compose plugin:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<DOCKER_REPO
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $VERSION_CODENAME
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
DOCKER_REPO
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
```

**Expected:** `hello-world` prints a successful Docker installation message. For conflicting packages or an existing runtime, follow the [official Docker Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/) rather than removing packages blindly.

## 4. Give the installation account Docker access

The main guide runs as a named, non-root service owner. If your administrator approves Docker-group access, run the following **while logged in as that account**:

```bash
sudo usermod -aG docker "$USER"
```

Log out of SSH and log back in. Then check without `sudo`:

```bash
id -un
docker run --rm hello-world
docker compose version
```

**Expected:** the intended account name, a successful Docker test and a Compose version. Docker-group membership grants root-level control of the host; it belongs only to approved operators. If policy prohibits it, the administrator must provide an approved deployment method. Do not work around permission errors by running the project's Python scripts as root. [Docker account setup](https://docs.docker.com/engine/install/linux-postinstall/)

## 5. Enable GPUs in Docker

Check whether `nvidia-ctk --version` already works. On a clean host without the toolkit:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey -o /tmp/container-toolkit-key.asc
sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg /tmp/container-toolkit-key.asc
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list -o /tmp/container-toolkit.list
sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' /tmp/container-toolkit.list | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
```

On the dedicated host, configure Docker and restart it:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
nvidia-ctk --version
docker version
```

**Expected:** both version checks succeed. The project's GPU preflight will test the selected device inside the exact serving image. These commands follow the [NVIDIA Container Toolkit installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html); retain the installed package versions in your deployment record.

## 6. Hand over a ready host

Give the installer the SSH account and host address, approved GPU index, a writable local installation directory, available storage, and any registry/network instructions. The model cache and image storage need room for their downloads and working files; inspect available space with `df -h` and size it for the pinned artifacts before starting.

The installer must be able to run `nvidia-smi`, `docker version`, `docker compose version`, `python3 --version` and `htpasswd -h` (which displays usage) as the service owner. Return to [step 1 of the manual guide](install.md#1-prepare-the-host-and-project).

These are documented preparation commands, checked against upstream guidance on 6 November 2026. They have not been executed against your server by this project.
