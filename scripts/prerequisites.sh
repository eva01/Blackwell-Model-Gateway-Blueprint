#!/usr/bin/env bash
set -euo pipefail

role=gateway
install_missing=false
while (($#)); do
  case "$1" in
    --role) [[ $# -ge 2 ]] || { echo '--role requires gateway or demo' >&2; exit 2; }; role=$2; shift 2 ;;
    --install) install_missing=true; shift ;;
    -h|--help)
      cat <<'HELP'
Usage: ./gateway prerequisites [--role gateway|demo] [--install]

Check host tools and local Docker access. No packages are changed without --install.
--role gateway  CPU gateway host (default); no NVIDIA packages needed.
--role demo     Standalone GPU host; also requires NVIDIA driver and Container Toolkit.
--install       Install missing packages on Ubuntu 24.04 x86-64 using sudo and official repositories.

Installation can start Docker. It does not remove conflicting packages, change Docker
group membership, configure GPU runtime, restart an existing Docker daemon, install
GPU drivers, partition MIG devices, or change Slurm nodes. See docs/start/prerequisites.md.
HELP
      exit 0 ;;
    *) echo "Unknown option: $1. Use ./gateway prerequisites --help" >&2; exit 2 ;;
  esac
done
[[ "$role" == gateway || "$role" == demo ]] || { echo '--role must be gateway or demo' >&2; exit 2; }

installed() { [[ $(dpkg-query -W -f='${Status}' "$1" 2>/dev/null || true) == 'install ok installed' ]]; }
as_root() { if [[ $EUID == 0 ]]; then "$@"; else sudo "$@"; fi; }

if $install_missing; then
  [[ -f /etc/os-release ]] || { echo 'Automatic installation requires Ubuntu 24.04 x86-64. See docs/start/prerequisites.md.' >&2; exit 2; }
  # Only the operating system's trusted release file is sourced.
  . /etc/os-release
  [[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 && $(uname -m) == x86_64 ]] || {
    echo 'Automatic installation supports Ubuntu 24.04 x86-64 only. Use the manual guide for other hosts.' >&2; exit 2;
  }
  [[ $EUID == 0 ]] || command -v sudo >/dev/null || { echo 'An administrator with sudo access must install packages.' >&2; exit 1; }
  [[ -d /run/systemd/system ]] || { echo 'Use a systemd-managed Ubuntu host, not a container or WSL shell.' >&2; exit 1; }
  [[ $EUID == 0 ]] || sudo -v
  base=(bash python3 ca-certificates curl gnupg openssl apache2-utils git unzip nano openssh-client coreutils grep sed)
  missing=()
  for package in "${base[@]}"; do installed "$package" || missing+=("$package"); done
  if ((${#missing[@]})); then
    printf 'Installing missing base packages: %s\n' "${missing[*]}"
    as_root apt-get update
    as_root apt-get install -y --no-upgrade "${missing[@]}"
  fi
  work=$(mktemp -d)
  trap 'rm -rf -- "$work"' EXIT
  docker_packages=(docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin)
  if command -v docker >/dev/null && ! installed docker-ce && ! installed docker.io && ! installed docker-ce-cli; then
    echo 'Docker is present outside the supported package managers. Review installation manually.' >&2
    exit 1
  fi
  need_docker=false
  if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
    need_docker=true
  elif ! installed docker-ce && ! installed docker.io; then
    need_docker=true
  fi
  if $need_docker; then
    conflicts=()
    for package in docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc; do
      if installed "$package"; then conflicts+=("$package"); fi
    done
    if ((${#conflicts[@]})); then
      printf 'Existing packages require administrator review; nothing will be removed: %s\n' "${conflicts[*]}" >&2
      echo 'Follow https://docs.docker.com/engine/install/ubuntu/ before continuing.' >&2
      exit 1
    fi
    # Existing repository ownership is left to the host administrator.
    as_root apt-get update
    if ! apt-cache policy docker-ce | grep 'Candidate: [0-9]' >/dev/null; then
      if [[ -e /etc/apt/sources.list.d/docker.sources || -e /etc/apt/sources.list.d/docker.list ]]; then
        echo 'Existing Docker repository has no package candidate. Repair it manually, then rerun.' >&2; exit 1
      fi
      curl -fsSL --retry 3 https://download.docker.com/linux/ubuntu/gpg -o "$work/docker.asc"
      as_root install -d -m 0755 /etc/apt/keyrings
      as_root install -m 0644 "$work/docker.asc" /etc/apt/keyrings/docker.asc
      cat >"$work/docker.sources" <<'REPO'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
REPO
      as_root install -m 0644 "$work/docker.sources" /etc/apt/sources.list.d/docker.sources
    fi
    as_root apt-get update
    missing=()
    for package in "${docker_packages[@]}"; do installed "$package" || missing+=("$package"); done
    if ((${#missing[@]})); then as_root apt-get install -y --no-upgrade "${missing[@]}"; fi
    as_root systemctl enable --now docker
  fi
  if [[ "$role" == demo ]] && ! command -v nvidia-ctk >/dev/null; then
    as_root apt-get update
    if ! apt-cache policy nvidia-container-toolkit | grep 'Candidate: [0-9]' >/dev/null; then
      if [[ -e /etc/apt/sources.list.d/nvidia-container-toolkit.list ]]; then
        echo 'Existing NVIDIA toolkit repository has no candidate. Repair it manually, then rerun.' >&2; exit 1
      fi
      curl -fsSL --retry 3 https://nvidia.github.io/libnvidia-container/gpgkey -o "$work/nvidia.asc"
      gpg --batch --dearmor -o "$work/nvidia.gpg" "$work/nvidia.asc"
      as_root install -m 0644 "$work/nvidia.gpg" /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
      curl -fsSL --retry 3 https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list -o "$work/nvidia.list"
      sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' "$work/nvidia.list" >"$work/nvidia-signed.list"
      as_root install -m 0644 "$work/nvidia-signed.list" /etc/apt/sources.list.d/nvidia-container-toolkit.list
    fi
    as_root apt-get update
    as_root apt-get install -y --no-upgrade nvidia-container-toolkit
  fi
fi

failed=0
check() {
  if "$@" >/dev/null 2>&1; then printf 'OK       %s\n' "$*";
  else printf 'MISSING  %s\n' "$*"; failed=1; fi
}
printf 'Prerequisites for role: %s\n' "$role"
if [[ $(uname -s) != Linux ]]; then
  echo 'UNSUPPORTED: gateway containers require a Linux host; this machine can edit the repo or run an API client.'
  failed=1
fi
for tool in bash python3 curl gpg openssl htpasswd git unzip nano ssh scp sha256sum grep sed; do check command -v "$tool"; done
check python3 -c 'import sqlite3, ssl; assert __import__("sys").version_info >= (3, 10)'
check python3 -c 'import ssl; assert ssl.create_default_context().cert_store_stats()["x509_ca"] > 0'
check docker compose version
check docker --context default info
if [[ "$role" == demo ]]; then
  check nvidia-smi -L
  check nvidia-ctk --version
  if docker --context default info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'; then
    echo 'OK       Docker NVIDIA runtime registered'
  else
    echo 'MISSING  Docker NVIDIA runtime; administrator must configure it and schedule a Docker restart.'
    failed=1
  fi
fi
echo 'Package checks do not qualify GPU kernels, model capacity, networking or a live deployment.'
if ((failed)); then
  echo 'See docs/start/prerequisites.md. On supported Ubuntu: ./gateway prerequisites --install'
  echo 'For daemon/access failures, ask the administrator to start Docker and grant approved access; rerun as the service owner.'
else
  echo 'Host prerequisite checks passed. Continue with the installation guide.'
fi
exit "$failed"
