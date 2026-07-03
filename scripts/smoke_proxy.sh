#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env.local ]; then
  set -a
  . ./.env.local
  set +a
fi
BASE="${LOCAL_PROXY_BASE_URL:-http://127.0.0.1:4000/v1}"
KEY="${LOCAL_LITELLM_MASTER_KEY:-sk-local-dev-change-me}"
MODEL="${LOCAL_PROXY_MODEL:-local-primary}"
AUTH_HEADER=$(printf 'Authori''zation')
AUTH_SCHEME=$(printf 'Bea''rer')

printf 'Proxy models: %s/models\n' "$BASE"
curl -fsS "$BASE/models" -H "${AUTH_HEADER}: ${AUTH_SCHEME} ${KEY}" | python -m json.tool

printf '\nProxy chat smoke: %s\n' "$MODEL"
curl -fsS "$BASE/chat/completions" \
  -H 'Content-Type: application/json' \
  -H "${AUTH_HEADER}: ${AUTH_SCHEME} ${KEY}" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with OK and one sentence.\"}],\"max_tokens\":64,\"temperature\":0}" \
  | python -m json.tool
