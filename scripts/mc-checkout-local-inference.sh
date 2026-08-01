#!/usr/bin/env bash
# Scoped MC checkout for petralabx/local-inference Cloud Agents.
# Rejects stamps unless meta.actor.repo matches this repo (decision-3 guard).
set -euo pipefail

TASK_ID="${1:-}"
if [[ -z "$TASK_ID" ]]; then
  printf 'usage: %s TASK-NNN\n' "$(basename "$0")" >&2
  exit 2
fi

MC_BASE_URL="${MC_BASE_URL:-https://mc.plxcustomer.io}"
MC_REPO="${MC_REPO:-petralabx/local-inference}"
MC_OPERATOR_EMAIL="${MC_OPERATOR_EMAIL:-cos@petrasoap.com}"
MC_RUNTIME="${MC_RUNTIME:-cursor-cloud}"

if [[ -z "${PLX_MC_MCP_API_KEY:-}" && -z "${MC_MCP_API_KEY:-}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    # shellcheck disable=SC1091
    KEY_OUT="$(
      python3 - <<'PY' 2>/dev/null || true
import json, os, sys
try:
    import boto3
except Exception:
    sys.exit(0)
region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
sm = boto3.client("secretsmanager", region_name=region)
raw = sm.get_secret_value(SecretId="prod/ec2-secrets")["SecretString"]
d = json.loads(raw)
print(d.get("PLX_MC_MCP_API_KEY") or d.get("MC_MCP_API_KEY") or "")
PY
    )"
    if [[ -n "$KEY_OUT" ]]; then
      PLX_MC_MCP_API_KEY="$KEY_OUT"
      export PLX_MC_MCP_API_KEY
    fi
  fi
fi

API_KEY="${PLX_MC_MCP_API_KEY:-${MC_MCP_API_KEY:-}}"
if [[ -z "$API_KEY" ]]; then
  printf 'MISSING: set PLX_MC_MCP_API_KEY (or hydrate from prod/ec2-secrets)\n' >&2
  exit 1
fi

HDR=(
  -H "x-api-key: ${API_KEY}"
  -H "x-mc-operator-email: ${MC_OPERATOR_EMAIL}"
  -H "x-mc-repo: ${MC_REPO}"
  -H "x-mc-runtime: ${MC_RUNTIME}"
  -H "content-type: application/json"
)

self="$(curl -fsS "${HDR[@]}" "${MC_BASE_URL%/}/api/cursor/self-check")"
echo "$self" | jq -e --arg repo "$MC_REPO" \
  '.data.ok == true and .meta.actor.repo == $repo' >/dev/null \
  || {
    printf 'self-check actor.repo mismatch; want %s got %s\n' \
      "$MC_REPO" "$(echo "$self" | jq -r '.meta.actor.repo // empty')" >&2
    exit 1
  }

checkout="$(curl -fsS -X POST "${HDR[@]}" "${MC_BASE_URL%/}/api/cursor/checkout" \
  --data "$(jq -n --arg id "$TASK_ID" '{taskId:$id}')")"

echo "$checkout" | jq -e --arg repo "$MC_REPO" --arg tid "$TASK_ID" \
  '.data.taskId == $tid and .meta.actor.repo == $repo and (.data.checkoutId|type=="string") and (.data.checkoutId|startswith("dsp_"))' \
  >/dev/null \
  || {
    printf 'checkout handshake failed:\n%s\n' "$(echo "$checkout" | jq '{taskId:.data.taskId, checkoutId:.data.checkoutId, actorRepo:.meta.actor.repo}')" >&2
    exit 1
  }

echo "$checkout" | jq -r '.data.prBodyLine'
echo "$checkout" | jq '{checkoutId:.data.checkoutId, taskId:.data.taskId, actorRepo:.meta.actor.repo, prBodyLine:.data.prBodyLine}'
