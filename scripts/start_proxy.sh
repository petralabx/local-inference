#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Windows Git Bash: LiteLLM banner uses Unicode; avoid cp1252 startup crash.
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
export NO_COLOR=1

set -a
[ ! -f .env.local ] || . ./.env.local
set +a

HOST_BIND="${LITELLM_HOST:-0.0.0.0}"
PORT="${LITELLM_PORT:-4000}"
KEY="${LOCAL_LITELLM_MASTER_KEY:-sk-local-dev-change-me}"

printf 'Starting LiteLLM proxy on %s:%s\n' "$HOST_BIND" "$PORT"
printf 'Client base URLs: http://127.0.0.1:%s/v1 or http://100.103.33.54:%s/v1\n' "$PORT" "$PORT"

export LITELLM_MASTER_KEY="$KEY"
exec .venv/Scripts/litellm.exe --config litellm/config.yaml --host "$HOST_BIND" --port "$PORT"
