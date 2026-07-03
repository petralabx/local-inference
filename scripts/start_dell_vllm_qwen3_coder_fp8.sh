#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"
mkdir -p "$HOME/.cache/huggingface"

if ! command -v docker >/dev/null 2>&1; then
  echo 'ERROR: docker not found. Install Docker Desktop + WSL2 + GPU support first.' >&2
  exit 2
fi

exec docker run --rm --gpus all -p 8000:8000 \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
  vllm/vllm-openai:v0.10.2 \
  --model Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8 \
  --gpu-memory-utilization 0.85 \
  --max-model-len 32768 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --port 8000 --host 0.0.0.0
