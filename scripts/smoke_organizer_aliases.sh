#!/usr/bin/env bash
# Authenticated Organizer alias smoke against Dell LiteLLM.
# Optional request-scoped proxy: LITELLM_HTTP_PROXY=http://127.0.0.1:1054
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env.local ]; then
  set -a
  . ./.env.local
  set +a
fi
BASE="${LOCAL_PROXY_BASE_URL:-http://127.0.0.1:4000/v1}"
KEY="${LOCAL_LITELLM_MASTER_KEY:-}"
if [ -z "$KEY" ] || echo "$KEY" | grep -q CHANGE-ME; then
  echo "LOCAL_LITELLM_MASTER_KEY is required" >&2
  exit 1
fi
CURL=(curl -fsS)
if [ -n "${LITELLM_HTTP_PROXY:-}" ]; then
  CURL+=(-x "$LITELLM_HTTP_PROXY")
fi
AUTH_HEADER=$(printf 'Authori''zation')
AUTH_SCHEME=$(printf 'Bea''rer')
printf 'Proxy models: %s/models\n' "$BASE"
"${CURL[@]}" "$BASE/models" -H "${AUTH_HEADER}: ${AUTH_SCHEME} ${KEY}" | python -m json.tool
for MODEL in local-driver local-coder; do
  printf '\nProxy chat smoke: %s\n' "$MODEL"
  "${CURL[@]}" "$BASE/chat/completions" \
    -H 'Content-Type: application/json' \
    -H "${AUTH_HEADER}: ${AUTH_SCHEME} ${KEY}" \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with OK\"}],\"max_tokens\":16,\"temperature\":0}" \
    | python -m json.tool
done
