#!/usr/bin/env bash
# Spark B only: serve the abliterated Qwen3.6-35B-A3B NVFP4+MTP checkpoint with
# vLLM on SIDE port 18091. Does not bind, stop, or replace llama.cpp GGUF on
# :18090 (live local-driver rollback).
#
# Run on spark-b4ec (ARM64 GB10). Do not run on Dell or Spark A.
# This script does not download weights.
set -euo pipefail

PREFERRED_MODEL="THe-Plague/Qwen3.6-35B-A3B-abliterated-NVFP4-MTP"
STOCK_NVIDIA_PREFIX="nvidia/Qwen3.6-35B-A3B"
ROLLBACK_PORT="${ROLLBACK_PORT:-18090}"
SERVE_PORT="${SERVE_PORT:-18091}"
SERVE_HOST="${SERVE_HOST:-0.0.0.0}"
MODEL_DIR="${MODEL_DIR:-${HOME}/models/THe-Plague/Qwen3.6-35B-A3B-abliterated-NVFP4-MTP}"
MODEL="${MODEL:-${MODEL_DIR}}"
IMAGE="${VLLM_IMAGE:-ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-vllm-spark-b-nvfp4-bakeoff}"
ENGINE="${ENGINE:-auto}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-32768}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.45}"
KV_CACHE_DTYPE="${KV_CACHE_DTYPE:-fp8}"
NUM_SPECULATIVE_TOKENS="${NUM_SPECULATIVE_TOKENS:-3}"
LOAD_FORMAT="${LOAD_FORMAT:-instanttensor}"
ATTENTION_BACKEND="${ATTENTION_BACKEND:-flashinfer}"
TP_SIZE="${TP_SIZE:-1}"
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: start_spark_b_vllm_qwen36_nvfp4_mtp.sh [--dry-run] [--help]

Spark-B-only bake-off serve for THe-Plague/Qwen3.6-35B-A3B-abliterated-NVFP4-MTP.
Serves vLLM on :18091. Never touches llama.cpp GGUF on :18090.

Environment:
  MODEL / MODEL_DIR   local checkpoint path (default ~/models/THe-Plague/...)
  SERVE_PORT          must stay 18091 (refuses 18090)
  SPARK_B_OK=1        skip host/arch guard (tests only)
  ENGINE=auto|native|docker
  --dry-run           print the vLLM command and exit after guards
EOF
}

log() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

require_spark_b() {
  if [[ "${SPARK_B_OK:-0}" == "1" ]]; then
    return 0
  fi
  local arch host
  arch="$(uname -m)"
  host="$(hostname -s 2>/dev/null || hostname)"
  case "$arch" in
    aarch64|arm64) ;;
    *) die "not ARM64 (got ${arch}). Spark B GB10 only — do not run on Dell." ;;
  esac
  case "$host" in
    spark-7d3d*|phase-f-dgx-spark*|VTA*|vta*)
      die "host ${host} is not Spark B. This script is spark-b4ec only."
      ;;
    spark-b4ec*) ;;
    *)
      die "host ${host} is not spark-b4ec. Set SPARK_B_OK=1 only for tests."
      ;;
  esac
}

refuse_stock_nvidia() {
  local model_lc
  model_lc="$(printf '%s' "$MODEL" | tr '[:upper:]' '[:lower:]')"
  if [[ "$MODEL" == *"${STOCK_NVIDIA_PREFIX}"* && "$model_lc" != *abliterated* ]]; then
    die "refusing stock ${STOCK_NVIDIA_PREFIX} (Vince requires abliterated/uncensored weights). Use ${PREFERRED_MODEL}."
  fi
  if [[ "$model_lc" != *abliterated* ]]; then
    die "model path/id must contain 'abliterated'. Preferred: ${PREFERRED_MODEL}."
  fi
}

refuse_wrong_port() {
  if [[ "$SERVE_PORT" == "$ROLLBACK_PORT" ]]; then
    die "refusing to bind rollback port ${ROLLBACK_PORT}. Bake-off must use side port 18091."
  fi
  if [[ "$SERVE_PORT" != "18091" ]]; then
    die "SERVE_PORT must be 18091 (got ${SERVE_PORT}). Live GGUF stays on ${ROLLBACK_PORT}."
  fi
}

refuse_enforce_eager() {
  if [[ "${EXTRA_VLLM_ARGS:-}" == *"--enforce-eager"* ]]; then
    die "refusing --enforce-eager (CUDA graphs stay enabled for this bake-off)."
  fi
}

build_speculative_config() {
  printf '{"method":"mtp","num_speculative_tokens":%s}' "$NUM_SPECULATIVE_TOKENS"
}

build_vllm_args() {
  local spec
  spec="$(build_speculative_config)"
  VLLM_ARGS=(
    serve "$MODEL"
    --host "$SERVE_HOST"
    --port "$SERVE_PORT"
    --tensor-parallel-size "$TP_SIZE"
    --trust-remote-code
    --kv-cache-dtype "$KV_CACHE_DTYPE"
    --enable-prefix-caching
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION"
    --max-model-len "$MAX_MODEL_LEN"
    --max-num-batched-tokens "$MAX_NUM_BATCHED_TOKENS"
    --max-num-seqs "$MAX_NUM_SEQS"
    --load-format "$LOAD_FORMAT"
    --attention-backend "$ATTENTION_BACKEND"
    --reasoning-parser qwen3
    --speculative-config "$spec"
  )
}

print_cmd() {
  local engine="$1"
  if [[ "$engine" == "native" ]]; then
    printf 'DRY_RUN_CMD: VLLM_MARLIN_USE_ATOMIC_ADD=1 TORCH_MATMUL_PRECISION=high vllm'
    printf ' %q' "${VLLM_ARGS[@]}"
    printf '\n'
  else
    printf 'DRY_RUN_CMD: docker run --gpus all --network host --ipc host --shm-size=16g --name %q' "$CONTAINER_NAME"
    printf ' -e VLLM_MARLIN_USE_ATOMIC_ADD=1 -e TORCH_MATMUL_PRECISION=high'
    printf ' -v %q:%q:ro %q vllm' "$MODEL" "$MODEL" "$IMAGE"
    printf ' %q' "${VLLM_ARGS[@]}"
    printf '\n'
  fi
}

select_engine() {
  case "$ENGINE" in
    native) printf 'native\n' ;;
    docker) printf 'docker\n' ;;
    auto)
      if command -v vllm >/dev/null 2>&1; then
        printf 'native\n'
      elif command -v docker >/dev/null 2>&1; then
        printf 'docker\n'
      else
        printf 'native\n'
      fi
      ;;
    *) die "ENGINE must be auto, native, or docker (got ${ENGINE})" ;;
  esac
}

require_spark_b
refuse_stock_nvidia
refuse_wrong_port
refuse_enforce_eager
build_vllm_args

if [[ "$DRY_RUN" == "1" ]]; then
  log "guards ok: Spark B bake-off on :${SERVE_PORT}; rollback GGUF stays on :${ROLLBACK_PORT}"
  log "model: ${MODEL}"
  log "mtp: num_speculative_tokens=${NUM_SPECULATIVE_TOKENS} kv-cache-dtype=${KV_CACHE_DTYPE} prefix-caching=on enforce-eager=off"
  print_cmd "$(select_engine)"
  exit 0
fi

if [[ ! -e "$MODEL" ]]; then
  die "weights not found at ${MODEL}. Download on Spark B first (see docs/runbooks/spark-b-qwen36-nvfp4-bakeoff.md). This script does not download."
fi

engine="$(select_engine)"
log "leaving llama.cpp GGUF on :${ROLLBACK_PORT} alone; serving NVFP4+MTP on :${SERVE_PORT}"
export VLLM_MARLIN_USE_ATOMIC_ADD=1
export TORCH_MATMUL_PRECISION=high

if [[ "$engine" == "native" ]]; then
  command -v vllm >/dev/null 2>&1 || die "vllm not on PATH. Install Spark vLLM or set ENGINE=docker."
  exec vllm "${VLLM_ARGS[@]}"
fi

command -v docker >/dev/null 2>&1 || die "docker not found and native vllm is unavailable."
if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  die "container ${CONTAINER_NAME} already exists. Inspect it; this script will not stop :${ROLLBACK_PORT} or other containers."
fi
exec docker run --gpus all --network host --ipc host --shm-size=16g \
  --name "$CONTAINER_NAME" \
  -e VLLM_MARLIN_USE_ATOMIC_ADD=1 \
  -e TORCH_MATMUL_PRECISION=high \
  -v "${MODEL}:${MODEL}:ro" \
  "$IMAGE" \
  vllm "${VLLM_ARGS[@]}"
