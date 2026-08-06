#!/usr/bin/env bash
# Scoped MC identity check and checkout for petralabx/local-inference agents.
# Rejects stamps unless meta.actor.repo matches this repo (decision-3 guard).
set -euo pipefail

MODE="checkout"
TASK_ID=""
case "${1:-}" in
  --self-check)
    MODE="self-check"
    ;;
  TASK-[0-9]*)
    TASK_ID="$1"
    ;;
  *)
    printf 'usage: %s --self-check | TASK-NNN\n' "$(basename "$0")" >&2
    exit 2
    ;;
esac
if [[ $# -ne 1 || ( "$MODE" == "checkout" && ! "$TASK_ID" =~ ^TASK-[0-9]+$ ) ]]; then
  printf 'usage: %s --self-check | TASK-NNN\n' "$(basename "$0")" >&2
  exit 2
fi

EXPECTED_BASE_URL="https://mc.plxcustomer.io"
EXPECTED_REPO="petralabx/local-inference"
EXPECTED_OPERATOR="cos@petrasoap.com"
MC_BASE_URL="${MC_BASE_URL:-$EXPECTED_BASE_URL}"
MC_BASE_URL="${MC_BASE_URL%/}"
MC_REPO="${MC_REPO:-$EXPECTED_REPO}"
MC_OPERATOR_EMAIL="${MC_OPERATOR_EMAIL:-$EXPECTED_OPERATOR}"
MC_RUNTIME="${MC_RUNTIME:-cursor-cloud}"

if [[ "$MC_BASE_URL" != "$EXPECTED_BASE_URL" ]]; then
  printf 'refusing MC request: MC_BASE_URL must be %s\n' "$EXPECTED_BASE_URL" >&2
  exit 1
fi

if [[ "$MC_REPO" != "$EXPECTED_REPO" || "$MC_OPERATOR_EMAIL" != "$EXPECTED_OPERATOR" ]]; then
  printf 'refusing MC request: identity must be repo=%s operator=%s\n' \
    "$EXPECTED_REPO" "$EXPECTED_OPERATOR" >&2
  exit 1
fi

case "$MC_RUNTIME" in
  local)
    EXPECTED_SERVICE_PRINCIPAL="${MC_MCP_PRINCIPAL_ID:-}"
    case "$EXPECTED_SERVICE_PRINCIPAL" in
      sp_mcp_claude_code|sp_mcp_codex|sp_mcp_grok|sp_mcp_hermes|sp_mcp_swarm)
        ;;
      *)
        printf 'refusing MC request: unsupported MC_MCP_PRINCIPAL_ID for local runtime\n' >&2
        exit 1
        ;;
    esac
    ;;
  cursor-cloud)
    if [[ -n "${MC_MCP_PRINCIPAL_ID:-}" && "$MC_MCP_PRINCIPAL_ID" != "sp_mcp_cursor" ]]; then
      printf 'refusing MC request: cursor-cloud requires sp_mcp_cursor\n' >&2
      exit 1
    fi
    EXPECTED_SERVICE_PRINCIPAL="sp_mcp_cursor"
    ;;
  *)
    printf 'refusing MC request: MC_RUNTIME must be local or cursor-cloud\n' >&2
    exit 1
    ;;
esac

if [[ -z "${PLX_MC_MCP_API_KEY:-}" && -z "${MC_MCP_API_KEY:-}" && "$MC_RUNTIME" == "cursor-cloud" ]]; then
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

API_KEY="${MC_MCP_API_KEY:-${PLX_MC_MCP_API_KEY:-}}"
if [[ -z "$API_KEY" ]]; then
  if [[ "$MC_RUNTIME" == "local" ]]; then
    printf 'MISSING: set MC_MCP_API_KEY in the local agent environment\n' >&2
  else
    printf 'MISSING: set PLX_MC_MCP_API_KEY (or hydrate from prod/ec2-secrets)\n' >&2
  fi
  exit 1
fi

mc_request() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local args=(-fsS -H @- "${MC_BASE_URL}${path}")
  if [[ "$method" == "POST" ]]; then
    args=(-fsS -X POST -H @- --data "$data" "${MC_BASE_URL}${path}")
  fi
  printf 'x-api-key: %s\nx-mc-operator-email: %s\nx-mc-repo: %s\nx-mc-runtime: %s\ncontent-type: application/json\n' \
    "$API_KEY" "$MC_OPERATOR_EMAIL" "$MC_REPO" "$MC_RUNTIME" |
    curl "${args[@]}"
}

self="$(mc_request GET /api/cursor/self-check)"
echo "$self" | jq -e \
  --arg repo "$MC_REPO" \
  --arg operator "$MC_OPERATOR_EMAIL" \
  --arg runtime "$MC_RUNTIME" \
  --arg principal "$EXPECTED_SERVICE_PRINCIPAL" \
  '.data.ok == true
    and .meta.actor.repo == $repo
    and .meta.actor.operatorEmail == $operator
    and .meta.actor.runtime == $runtime
    and .meta.actor.servicePrincipalId == $principal' >/dev/null \
  || {
    printf 'self-check identity mismatch:\n%s\n' \
      "$(echo "$self" | jq '{
        actorRepo: .meta.actor.repo,
        operatorEmail: .meta.actor.operatorEmail,
        runtime: .meta.actor.runtime,
        servicePrincipalId: .meta.actor.servicePrincipalId
      }')" >&2
    exit 1
  }

if [[ "$MODE" == "self-check" ]]; then
  echo "$self" | jq '{
    ok: .data.ok,
    actorRepo: .meta.actor.repo,
    operatorEmail: .meta.actor.operatorEmail,
    runtime: .meta.actor.runtime,
    servicePrincipalId: .meta.actor.servicePrincipalId
  }'
  exit 0
fi

checkout="$(mc_request POST /api/cursor/checkout "$(jq -n --arg id "$TASK_ID" '{taskId:$id}')")"

echo "$checkout" | jq -e \
  --arg repo "$MC_REPO" \
  --arg tid "$TASK_ID" \
  --arg operator "$MC_OPERATOR_EMAIL" \
  --arg runtime "$MC_RUNTIME" \
  --arg principal "$EXPECTED_SERVICE_PRINCIPAL" \
  '.data.taskId == $tid
    and .meta.actor.repo == $repo
    and .meta.actor.operatorEmail == $operator
    and .meta.actor.runtime == $runtime
    and .meta.actor.servicePrincipalId == $principal
    and (.data.checkoutId|type=="string")
    and (.data.checkoutId|startswith("dsp_"))' \
  >/dev/null \
  || {
    printf 'checkout handshake failed:\n%s\n' "$(echo "$checkout" | jq '{taskId:.data.taskId, checkoutId:.data.checkoutId, actorRepo:.meta.actor.repo}')" >&2
    exit 1
  }

echo "$checkout" | jq -r '.data.prBodyLine'
echo "$checkout" | jq '{checkoutId:.data.checkoutId, taskId:.data.taskId, actorRepo:.meta.actor.repo, prBodyLine:.data.prBodyLine}'
