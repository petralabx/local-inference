#!/usr/bin/env bash
# Executable close-out gate for local-inference agent PRs.
#
# Exists because prose rules did not hold: the actor.repo handshake was already
# required and was skipped anyway on PR #11, and mc_complete_task returned ok
# 19 seconds before the compliance gate BLOCKED. A successful complete() call
# is NOT evidence that the gate passed — only the gate's own conclusion is.
#
# Checks, in order:
#   1. checkout scope   — MC actor.repo must equal this repo's slug
#   2. PR stamps        — one well-formed MC-Checkout per referenced TASK
#   3. task evidence    — summary + rollback present on every referenced task
#   4. gate conclusion  — GitHub `compliance` check must be success
#
# Usage:
#   bash scripts/mc-pr-preflight.sh              # verify PR for current branch
#   bash scripts/mc-pr-preflight.sh --pr 11
#   bash scripts/mc-pr-preflight.sh --wait       # poll until checks conclude
set -uo pipefail

MC_BASE_URL="${MC_BASE_URL:-https://mc.plxcustomer.io}"
MC_REPO="${MC_REPO:-petralabx/local-inference}"
MC_OPERATOR_EMAIL="${MC_OPERATOR_EMAIL:-cos@petrasoap.com}"
MC_RUNTIME="${MC_RUNTIME:-cursor-cloud}"
WAIT_SECS="${WAIT_SECS:-300}"

PR_NUM=""
DO_WAIT=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pr) PR_NUM="${2:-}"; shift 2 ;;
    --wait) DO_WAIT=1; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

FAILED=0
pass() { printf '  PASS  %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; FAILED=1; }
info() { printf '  ..    %s\n' "$1"; }

resolve_key() {
  local k="${PLX_MC_MCP_API_KEY:-${MC_MCP_API_KEY:-}}"
  if [[ -z "$k" ]]; then
    k="$(python3 - <<'PY' 2>/dev/null || true
import json, os, sys
try:
    import boto3
except Exception:
    sys.exit(0)
region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
sm = boto3.client("secretsmanager", region_name=region)
d = json.loads(sm.get_secret_value(SecretId="prod/ec2-secrets")["SecretString"])
print(d.get("PLX_MC_MCP_API_KEY") or d.get("MC_MCP_API_KEY") or "")
PY
)"
  fi
  printf '%s' "$k"
}

API_KEY="$(resolve_key)"
if [[ -z "$API_KEY" ]]; then
  printf 'MISSING: PLX_MC_MCP_API_KEY (hydrate from prod/ec2-secrets)\n' >&2
  exit 1
fi
HDR=(
  -H "x-api-key: ${API_KEY}"
  -H "x-mc-operator-email: ${MC_OPERATOR_EMAIL}"
  -H "x-mc-repo: ${MC_REPO}"
  -H "x-mc-runtime: ${MC_RUNTIME}"
  -H "content-type: application/json"
)

printf '== 1. checkout scope ==\n'
self="$(curl -fsS "${HDR[@]}" "${MC_BASE_URL%/}/api/cursor/self-check" 2>/dev/null)"
actual_repo="$(printf '%s' "$self" | jq -r '.meta.actor.repo // empty')"
if [[ "$actual_repo" == "$MC_REPO" ]]; then
  pass "actor.repo == ${MC_REPO}"
else
  fail "actor.repo is '${actual_repo:-<none>}', want '${MC_REPO}' — a stamp minted here is wrong-scope and the gate will BLOCK with decision 3"
fi

printf '== 2. PR stamps ==\n'
if [[ -z "$PR_NUM" ]]; then
  # `gh pr view --repo` ignores local branch context, so resolve by head branch.
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  if [[ -n "$branch" && "$branch" != "HEAD" ]]; then
    PR_NUM="$(gh pr list --repo "$MC_REPO" --head "$branch" --state all \
      --json number --jq '.[0].number // empty' 2>/dev/null || true)"
  fi
fi
if [[ -z "$PR_NUM" ]]; then
  info "no PR for this branch yet — stamp and gate checks deferred until it exists"
  [[ "$FAILED" -eq 0 ]] && exit 0 || exit 1
fi

body="$(gh pr view "$PR_NUM" --repo "$MC_REPO" --json body --jq '.body' 2>/dev/null)"
mapfile -t STAMPS < <(printf '%s' "$body" | grep -oE 'MC-Checkout: dsp_[A-Za-z0-9]+' | sed 's/.* //' | sort -u)
mapfile -t TASKS  < <(printf '%s' "$body" | grep -oE 'TASK-[0-9]+' | sort -u)

if [[ "${#STAMPS[@]}" -eq 0 ]]; then
  fail "PR #${PR_NUM} has no 'MC-Checkout: dsp_…' stamp — an agent PR without one is blocked"
else
  pass "PR #${PR_NUM} carries ${#STAMPS[@]} stamp(s): ${STAMPS[*]}"
fi
if [[ "${#TASKS[@]}" -eq 0 ]]; then
  fail "PR #${PR_NUM} references no TASK-* id"
elif [[ "${#STAMPS[@]}" -lt "${#TASKS[@]}" ]]; then
  fail "one stamp required per task: ${#TASKS[@]} task(s) (${TASKS[*]}) but only ${#STAMPS[@]} stamp(s)"
else
  pass "stamp/task parity: ${#STAMPS[@]} stamp(s) for ${#TASKS[@]} task(s)"
fi

printf '== 3. task evidence ==\n'
for t in "${TASKS[@]:-}"; do
  [[ -z "$t" ]] && continue
  ctx="$(curl -fsS "${HDR[@]}" "${MC_BASE_URL%/}/api/cursor/context?taskIds=${t}&depth=full" 2>/dev/null)"
  read -r has_sum has_rb stage < <(printf '%s' "$ctx" | jq -r \
    '.data.tasks[0] | [((.evidence.summary // "")|length > 0), ((.evidence.rollback // "")|length > 0), (.stage // "unknown")] | @tsv')
  if [[ "$has_sum" == "true" && "$has_rb" == "true" ]]; then
    pass "${t} evidence complete (summary + rollback), stage=${stage}"
  else
    fail "${t} evidence incomplete (summary=${has_sum} rollback=${has_rb}) — run mc_complete_task / /api/cursor/complete"
  fi
done

printf '== 4. compliance gate conclusion ==\n'
deadline=$(( $(date +%s) + WAIT_SECS ))
while :; do
  rollup="$(gh pr view "$PR_NUM" --repo "$MC_REPO" --json statusCheckRollup \
    --jq '.statusCheckRollup[] | select(.name=="compliance") | [.status,(.conclusion//"")] | @tsv' 2>/dev/null | head -1)"
  status="$(printf '%s' "$rollup" | cut -f1)"
  concl="$(printf '%s' "$rollup" | cut -f2)"
  if [[ -z "$status" ]]; then
    info "compliance check not reported yet"
  elif [[ "$status" != "COMPLETED" ]]; then
    info "compliance ${status}…"
  else
    break
  fi
  if [[ "$DO_WAIT" -eq 0 || "$(date +%s)" -ge "$deadline" ]]; then break; fi
  sleep 10
done

if [[ "${concl:-}" == "SUCCESS" ]]; then
  pass "compliance = SUCCESS"
elif [[ -z "${concl:-}" ]]; then
  fail "compliance has not concluded — do NOT claim the PR is ready (re-run with --wait)"
else
  fail "compliance = ${concl} — fix the stamp/evidence and push again; never edit .github/workflows/*compliance*"
fi

printf '\n'
if [[ "$FAILED" -eq 0 ]]; then
  printf 'PREFLIGHT OK — PR #%s satisfies the MC compliance gate.\n' "$PR_NUM"
  exit 0
fi
printf 'PREFLIGHT FAILED — PR #%s is NOT ready. Do not report this work as done.\n' "$PR_NUM" >&2
exit 1
