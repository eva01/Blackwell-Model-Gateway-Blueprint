#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")" && pwd)
case "${1:-}" in
  ''|--dry-run|--check-gpu) ;;
  *) echo 'Usage: serve.sh [--dry-run|--check-gpu]' >&2; exit 2 ;;
esac
case "${GPU_PROFILE:-auto}" in
  auto|rtx-pro-6000|b200) ;;
  *) echo 'GPU_PROFILE must be auto, rtx-pro-6000 or b200' >&2; exit 2 ;;
esac
model=${MODEL_ID:-nvidia/Qwen3.8-27B-NVFP4}
revision=${MODEL_REVISION:-482ca0f3832238542f8f5295dde86b5f22711d80}
context=${MAX_MODEL_LEN:-262144}
sequences=${MAX_NUM_SEQS:-1}
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'MODEL_REVISION must be a commit hash' >&2; exit 2; }
[[ "$context" =~ ^[1-9][0-9]*$ && "$sequences" =~ ^[1-9][0-9]*$ ]] || exit 2
args=(serve "$model" --revision "$revision"
  --served-model-name "${SERVED_MODEL:-qwen}"
  --host "${VLLM_HOST:-0.0.0.0}" --port "${VLLM_PORT:-8000}"
  --tensor-parallel-size 1 --max-model-len "$context" --max-num-seqs "$sequences"
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.80}"
  --kv-cache-dtype "${KV_CACHE_DTYPE:-fp8_e4m3}"
  --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder
  --max-num-batched-tokens "${MAX_NUM_BATCHED_TOKENS:-8192}"
  --enable-chunked-prefill --enable-prefix-caching --enable-prompt-tokens-details)
if [[ "${1:-}" == --dry-run ]]; then
  printf 'vllm'; printf ' %q' "${args[@]}"; printf '\n'
  exit 0
fi
# Preserve scheduler/container visibility; let the runtime select GPU kernels.
python3 "$root/gpu_check.py"
[[ "${1:-}" != --check-gpu ]] || exit 0
key_file=${BACKEND_KEY_FILE:-/run/secrets/backend.key}
[[ -s "$key_file" ]] || { echo 'Readable backend key file required' >&2; exit 2; }
VLLM_API_KEY=$(<"$key_file")
[[ -n "$VLLM_API_KEY" && ! "$VLLM_API_KEY" =~ [[:space:]] ]] || exit 2
export VLLM_API_KEY
exec vllm "${args[@]}"
