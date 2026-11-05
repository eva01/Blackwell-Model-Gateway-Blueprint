#!/usr/bin/env bash
# Standalone RTX PRO 6000 Blackwell or B200 host. Slurm uses serve.sbatch.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
[[ -z "${SLURM_JOB_ID:-}" ]] || { echo 'Use serve.sbatch under Slurm' >&2; exit 2; }
set -a
source "${BACKEND_ENV:-$root/inference/backend.env}"
set +a
: "${VLLM_IMAGE:?}" "${MODEL_CACHE:?}" "${BACKEND_KEY_FILE:?}"
[[ -s "$BACKEND_KEY_FILE" ]] || exit 2
mkdir -p "$MODEL_CACHE"
# Explicit single device; a clean prototype defaults to GPU 0.
exec docker run --rm --name qwen-prototype \
  --gpus "device=${PROTOTYPE_GPU:-0}" --shm-size 8g \
  -p "127.0.0.1:${VLLM_PORT:-8000}:${VLLM_PORT:-8000}" \
  -v "$root/inference:/opt/inference:ro" -v "$MODEL_CACHE:/cache" \
  -v "$BACKEND_KEY_FILE:/run/secrets/backend.key:ro" \
  -e HF_HOME=/cache/huggingface -e BACKEND_KEY_FILE=/run/secrets/backend.key \
  -e GPU_PROFILE -e MODEL_ID -e MODEL_REVISION -e SERVED_MODEL -e MAX_MODEL_LEN -e MAX_NUM_SEQS \
  -e GPU_MEMORY_UTILIZATION -e MAX_NUM_BATCHED_TOKENS -e KV_CACHE_DTYPE -e VLLM_PORT -e VLLM_HOST \
  --entrypoint bash "$VLLM_IMAGE" /opt/inference/serve.sh "$@"
