#!/usr/bin/env bash
# Pass the site's account, partition, typed MIG GRES, time and optional reservation to sbatch.
#SBATCH --job-name=qwen
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=logs/%x-%j.log
#SBATCH --signal=B:TERM@120
set -euo pipefail
: "${INFERENCE_PACKAGE_ROOT:?Set to this package on storage visible to the allocated node}"
: "${BACKEND_ENV:?Set to the private backend.env visible to that node}"
set -a
source "$BACKEND_ENV"
set +a
: "${SLURM_JOB_ID:?Submit with sbatch}" "${VLLM_SQSH:?}" "${MODEL_CACHE:?}" "${BACKEND_KEY_FILE:?}"
[[ -r "$VLLM_SQSH" && -s "$BACKEND_KEY_FILE" ]] || exit 2
mkdir -p "$MODEL_CACHE"
export HF_HOME=/cache/huggingface
# This cluster template targets a B200 4g.90gb allocation, not an arbitrary SM100 device.
export EXPECTED_MIG_PROFILE=4g.90gb
# srun and Pyxis propagate the allocated device visibility. No Docker socket or --gpus all.
srun --ntasks=1 --kill-on-bad-exit=1 \
  --container-image="$VLLM_SQSH" \
  --container-mounts="$INFERENCE_PACKAGE_ROOT/inference:/opt/inference:ro,$MODEL_CACHE:/cache,$BACKEND_KEY_FILE:/run/secrets/backend.key:ro" \
  --container-workdir=/opt/inference \
  --container-env=HF_HOME,GPU_PROFILE,EXPECTED_MIG_PROFILE,MODEL_ID,MODEL_REVISION,SERVED_MODEL,MAX_MODEL_LEN,MAX_NUM_SEQS,GPU_MEMORY_UTILIZATION,MAX_NUM_BATCHED_TOKENS,KV_CACHE_DTYPE,VLLM_PORT,VLLM_HOST \
  env BACKEND_KEY_FILE=/run/secrets/backend.key bash /opt/inference/serve.sh "$@" &
step_pid=$!
trap 'kill -TERM "$step_pid" 2>/dev/null || true; wait "$step_pid" || true' TERM INT
wait "$step_pid"
