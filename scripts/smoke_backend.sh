#!/usr/bin/env bash
set -euo pipefail
BASE="${LOCAL_BACKEND_BASE_URL:-http://127.0.0.1:8000/v1}"
MODEL="${LOCAL_PRIMARY_MODEL:-Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8}"

printf 'Backend models: %s/models\n' "$BASE"
curl -fsS "$BASE/models" | python -m json.tool

printf '\nBackend chat smoke: %s\n' "$MODEL"
curl -fsS "$BASE/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with OK and one sentence.\"}],\"max_tokens\":64,\"temperature\":0}" \
  | python -m json.tool
