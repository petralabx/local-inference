#!/usr/bin/env bash
# Boot-durable variant of the Qwen3-32B-AWQ backend.
# Uses a NAMED container with --restart=unless-stopped so Docker Desktop
# auto-restarts it after a reboot/crash (as long as Docker Desktop itself
# starts at login, which is its default).
#
# Idempotent: removes any prior 'vllm-local-primary' container first.
# Differences vs start_dell_vllm_qwen3_32b_awq.sh: named + detached + restart
# policy (not --rm, not foreground).
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"
mkdir -p "$HOME/.cache/huggingface"

if ! command -v docker >/dev/null 2>&1; then
  echo 'ERROR: docker not found. Install Docker Desktop + WSL2 + GPU support first.' >&2
  exit 2
fi

NAME="vllm-local-primary"

# Replace any existing instance so this is safe to re-run.
docker rm -f "$NAME" >/dev/null 2>&1 || true

exec docker run -d --name "$NAME" --restart=unless-stopped --gpus all -p 8000:8000 \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
  vllm/vllm-openai:v0.10.2 \
  --model Qwen/Qwen3-32B-AWQ \
  --quantization awq \
  --gpu-memory-utilization 0.85 \
  --max-model-len 32768 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --port 8000 --host 0.0.0.0
