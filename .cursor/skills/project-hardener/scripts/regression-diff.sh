#!/usr/bin/env bash
#
# regression-diff.sh — compare current quality manifest vs baseline manifest.
#
# Usage:
#   regression-diff.sh --baseline <baseline.env> --current <current.env>
#   regression-diff.sh --selftest
#
# Exit codes:
#   0: no regressions
#   2: regression detected
#   64: usage error

set -uo pipefail

usage() {
  cat <<'EOF'
usage:
  regression-diff.sh --baseline <baseline.env> --current <current.env>
  regression-diff.sh --selftest
EOF
}

load_snapshot() {
  # Args: <path> <prefix>
  local path="$1"
  local prefix="$2"
  # shellcheck disable=SC1090
  source "$path"
  local key
  for key in TESTS_PASS E2E_PASS LINT_PASS TYPECHECK_PASS FAILURE_COUNT; do
    eval "${prefix}_${key}=\"\${$key:-}\""
  done
}

check_transition() {
  # Args: <name> <baseline-pass> <current-pass>
  local name="$1"
  local baseline_pass="$2"
  local current_pass="$3"
  if [[ "$baseline_pass" == "1" && "$current_pass" != "1" ]]; then
    echo "REGRESSION: ${name} transitioned pass -> fail"
    return 1
  fi
  return 0
}

selftest() {
  local tmp_dir script base cur good
  tmp_dir="$(mktemp -d)"
  script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/regression-diff.sh"
  base="$tmp_dir/base.env"
  cur="$tmp_dir/current.env"
  good="$tmp_dir/good.env"

  cat >"$base" <<'EOF'
TESTS_PASS=1
E2E_PASS=1
LINT_PASS=1
TYPECHECK_PASS=1
FAILURE_COUNT=0
EOF

  cat >"$cur" <<'EOF'
TESTS_PASS=1
E2E_PASS=0
LINT_PASS=1
TYPECHECK_PASS=1
FAILURE_COUNT=1
EOF

  cat >"$good" <<'EOF'
TESTS_PASS=1
E2E_PASS=1
LINT_PASS=1
TYPECHECK_PASS=1
FAILURE_COUNT=0
EOF

  bash "$script" --baseline "$base" --current "$cur" >/dev/null 2>&1
  local code=$?
  [[ "$code" -eq 2 ]] || { echo "selftest failed: expected regression exit 2, got $code" >&2; rm -rf "$tmp_dir"; return 1; }

  bash "$script" --baseline "$base" --current "$good" >/dev/null 2>&1
  code=$?
  [[ "$code" -eq 0 ]] || { echo "selftest failed: expected clean exit 0, got $code" >&2; rm -rf "$tmp_dir"; return 1; }

  rm -rf "$tmp_dir"
  echo "regression-diff selftest passed"
  return 0
}

main() {
  local baseline="" current=""

  if [[ "${1:-}" == "--selftest" ]]; then
    selftest
    return $?
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --baseline) baseline="${2:-}"; shift 2 ;;
      --current) current="${2:-}"; shift 2 ;;
      -h|--help) usage; return 0 ;;
      *)
        echo "error: unknown argument '$1'" >&2
        usage
        return 64
        ;;
    esac
  done

  if [[ -z "$baseline" || -z "$current" || ! -f "$baseline" || ! -f "$current" ]]; then
    usage
    return 64
  fi

  load_snapshot "$baseline" "BASE"
  load_snapshot "$current" "CUR"

  local regressions=0
  check_transition "TESTS" "${BASE_TESTS_PASS:-}" "${CUR_TESTS_PASS:-}" || regressions=$((regressions + 1))
  check_transition "E2E" "${BASE_E2E_PASS:-}" "${CUR_E2E_PASS:-}" || regressions=$((regressions + 1))
  check_transition "LINT" "${BASE_LINT_PASS:-}" "${CUR_LINT_PASS:-}" || regressions=$((regressions + 1))
  check_transition "TYPECHECK" "${BASE_TYPECHECK_PASS:-}" "${CUR_TYPECHECK_PASS:-}" || regressions=$((regressions + 1))

  if [[ "${CUR_FAILURE_COUNT:-0}" -gt "${BASE_FAILURE_COUNT:-0}" ]]; then
    echo "REGRESSION: FAILURE_COUNT increased ${BASE_FAILURE_COUNT:-0} -> ${CUR_FAILURE_COUNT:-0}"
    regressions=$((regressions + 1))
  fi

  if [[ "$regressions" -gt 0 ]]; then
    echo "regression-diff: FAIL ($regressions regression signal(s))"
    return 2
  fi

  echo "regression-diff: OK (no regressions)"
  return 0
}

main "$@"
