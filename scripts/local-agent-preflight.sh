#!/usr/bin/env bash
# Non-mutating readiness check for local agent work on petralabx/local-inference.
set -uo pipefail

EXPECTED_REPO="petralabx/local-inference"
EXPECTED_OPERATOR="cos@petrasoap.com"
MODE="${1:---offline}"
FAILURES=0

if [[ $# -gt 1 || ( "$MODE" != "--offline" && "$MODE" != "--online" ) ]]; then
  printf 'usage: %s [--offline|--online]\n' "$(basename "$0")" >&2
  exit 2
fi

pass() {
  printf 'PASS: %s\n' "$1"
}

warn() {
  printf 'WARN: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  FAILURES=$((FAILURES + 1))
}

is_expected_remote() {
  local url="$1"
  [[ "$url" =~ ^https://([^/@]+@)?github\.com/petralabx/local-inference(\.git)?$ ||
    "$url" =~ ^git@github\.com:petralabx/local-inference(\.git)?$ ||
    "$url" =~ ^ssh://git@github\.com/petralabx/local-inference(\.git)?$ ]]
}

for tool in git gh node jq curl; do
  if command -v "$tool" >/dev/null 2>&1; then
    pass "$tool is available"
  else
    fail "$tool is required"
  fi
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$REPO_ROOT" ]]; then
  pass "running inside a Git repository"
else
  fail "run this command from the local-inference checkout"
fi

ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
if is_expected_remote "$ORIGIN_URL"; then
  pass "origin fetch URL targets $EXPECTED_REPO"
else
  fail "origin fetch URL must target $EXPECTED_REPO"
fi

mapfile -t PUSH_URLS < <(git remote get-url --push --all origin 2>/dev/null || true)
if [[ ${#PUSH_URLS[@]} -ne 1 ]]; then
  fail "origin must have exactly one push URL"
elif is_expected_remote "${PUSH_URLS[0]}"; then
  pass "origin push URL targets $EXPECTED_REPO"
else
  fail "origin push URL must target $EXPECTED_REPO"
fi

resolve_python() {
  local candidate
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    if [[ -x "$PYTHON_BIN" ]] || command -v "$PYTHON_BIN" >/dev/null 2>&1; then
      printf '%s\n' "$PYTHON_BIN"
      return 0
    fi
    return 1
  fi
  for candidate in \
    "$REPO_ROOT/.venv/Scripts/python.exe" \
    "$REPO_ROOT/.venv/bin/python" \
    python3 \
    python; do
    if [[ -x "$candidate" ]] || command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if PYTHON_CMD="$(resolve_python)"; then
  pass "Python is available for repository validation"
else
  fail "Python 3 is required for repository validation"
fi

BRANCH="$(git branch --show-current 2>/dev/null || true)"
if [[ "$BRANCH" == cursor/* ]]; then
  pass "current branch uses the required cursor/* namespace"
elif [[ "$MODE" == "--online" ]]; then
  fail "create a cursor/* feature branch before the online check"
else
  warn "create a cursor/* feature branch before governed work"
fi

API_KEY="${MC_MCP_API_KEY:-${PLX_MC_MCP_API_KEY:-}}"
if [[ -n "$API_KEY" ]]; then
  pass "MC credential is present (value not displayed)"
elif [[ "$MODE" == "--online" ]]; then
  fail "MC_MCP_API_KEY is required for the online check"
else
  warn "MC_MCP_API_KEY is not set; offline checks continue"
fi

if [[ "${MC_OPERATOR_EMAIL:-}" == "$EXPECTED_OPERATOR" ]]; then
  pass "MC operator identity is scoped"
elif [[ "$MODE" == "--online" ]]; then
  fail "set MC_OPERATOR_EMAIL=$EXPECTED_OPERATOR"
else
  warn "set MC_OPERATOR_EMAIL=$EXPECTED_OPERATOR before the online check"
fi

if [[ "${MC_REPO:-}" == "$EXPECTED_REPO" ]]; then
  pass "MC repository identity is scoped"
elif [[ "$MODE" == "--online" ]]; then
  fail "set MC_REPO=$EXPECTED_REPO"
else
  warn "set MC_REPO=$EXPECTED_REPO before the online check"
fi

if [[ "${MC_RUNTIME:-}" == "local" ]]; then
  pass "MC runtime is local"
elif [[ "$MODE" == "--online" ]]; then
  fail "set MC_RUNTIME=local"
else
  warn "set MC_RUNTIME=local before the online check"
fi

if [[ "$MODE" == "--online" && $FAILURES -eq 0 ]]; then
  MC_CHECKOUT_SCRIPT="${MC_CHECKOUT_SCRIPT:-$REPO_ROOT/scripts/mc-checkout-local-inference.sh}"
  if "$MC_CHECKOUT_SCRIPT" --self-check >/dev/null 2>&1; then
    pass "MC self-check confirms the canonical repository scope"
  else
    fail "MC self-check failed"
  fi

  PUSH_PERMISSION="$(gh api "repos/$EXPECTED_REPO" --jq '.permissions.push' 2>/dev/null || true)"
  if [[ "$PUSH_PERMISSION" == "true" ]]; then
    pass "GitHub identity has canonical repository push permission"
  else
    fail "GitHub identity lacks canonical repository push permission"
  fi

  if git push --dry-run -u origin "$BRANCH" >/dev/null 2>&1; then
    pass "dry-run feature-branch push passed without changing the remote"
  else
    fail "dry-run feature-branch push failed"
  fi
fi

if [[ $FAILURES -gt 0 ]]; then
  printf 'NOT READY: %d check(s) failed\n' "$FAILURES" >&2
  exit 1
fi

if [[ "$MODE" == "--online" ]]; then
  printf 'READY: local agent can begin governed work\n'
else
  printf 'READY: offline structure checks passed; run again with --online after local secrets are provisioned\n'
fi
