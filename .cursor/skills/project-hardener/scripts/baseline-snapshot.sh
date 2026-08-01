#!/usr/bin/env bash
#
# baseline-snapshot.sh — capture a pre-harden quality baseline manifest.
#
# Usage:
#   baseline-snapshot.sh --out <path> \
#     --tests-cmd "<cmd>" --e2e-cmd "<cmd>" --lint-cmd "<cmd>" --typecheck-cmd "<cmd>"
#   baseline-snapshot.sh --selftest
#
# Output format is a shell env file that can be sourced by regression-diff.sh.

set -uo pipefail

usage() {
  cat <<'EOF'
usage:
  baseline-snapshot.sh --out <path> \
    --tests-cmd "<cmd>" --e2e-cmd "<cmd>" --lint-cmd "<cmd>" --typecheck-cmd "<cmd>"
  baseline-snapshot.sh --selftest
EOF
}

resolve_root() {
  if [[ -n "${VMC_REPO_ROOT:-}" && -d "${VMC_REPO_ROOT:-}" ]]; then
    printf '%s\n' "$VMC_REPO_ROOT"
    return 0
  fi
  if git_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    printf '%s\n' "$git_root"
    return 0
  fi
  pwd
}

run_check() {
  # Args: <label> <command>
  local label="$1"
  local cmd="$2"
  bash -lc "$cmd" >/dev/null 2>&1
  local code=$?
  printf '%s_EXIT=%s\n' "$label" "$code"
  if [[ "$code" -eq 0 ]]; then
    printf '%s_PASS=1\n' "$label"
  else
    printf '%s_PASS=0\n' "$label"
  fi
}

write_manifest() {
  local out="$1"
  local root="$2"
  local tests_cmd="$3"
  local e2e_cmd="$4"
  local lint_cmd="$5"
  local typecheck_cmd="$6"
  local generated_at
  generated_at="$(TZ=America/New_York date '+%Y-%m-%d %I:%M:%S %p ET')"

  local tests_status e2e_status lint_status typecheck_status
  tests_status="$(run_check "TESTS" "$tests_cmd")"
  e2e_status="$(run_check "E2E" "$e2e_cmd")"
  lint_status="$(run_check "LINT" "$lint_cmd")"
  typecheck_status="$(run_check "TYPECHECK" "$typecheck_cmd")"

  local tests_pass e2e_pass lint_pass typecheck_pass failure_count
  # shellcheck disable=SC2034
  eval "$tests_status"
  # shellcheck disable=SC2034
  eval "$e2e_status"
  # shellcheck disable=SC2034
  eval "$lint_status"
  # shellcheck disable=SC2034
  eval "$typecheck_status"
  failure_count=$(( (1 - TESTS_PASS) + (1 - E2E_PASS) + (1 - LINT_PASS) + (1 - TYPECHECK_PASS) ))

  cat >"$out" <<EOF
SNAPSHOT_KIND=baseline
SNAPSHOT_VERSION=1
SNAPSHOT_GENERATED_AT_ET=$(printf '%q' "$generated_at")
SNAPSHOT_ROOT=$(printf '%q' "$root")
TESTS_CMD=$(printf '%q' "$tests_cmd")
E2E_CMD=$(printf '%q' "$e2e_cmd")
LINT_CMD=$(printf '%q' "$lint_cmd")
TYPECHECK_CMD=$(printf '%q' "$typecheck_cmd")
$tests_status
$e2e_status
$lint_status
$typecheck_status
FAILURE_COUNT=$failure_count
EOF
}

selftest() {
  local tmp_dir script out_file
  tmp_dir="$(mktemp -d)"
  script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/baseline-snapshot.sh"
  out_file="$tmp_dir/baseline.env"

  bash "$script" \
    --out "$out_file" \
    --tests-cmd "true" \
    --e2e-cmd "false" \
    --lint-cmd "true" \
    --typecheck-cmd "true" >/dev/null
  local code=$?
  if [[ "$code" -ne 0 ]]; then
    echo "selftest failed: snapshot command exited $code" >&2
    return 1
  fi

  # shellcheck disable=SC1090
  source "$out_file"
  [[ "${SNAPSHOT_KIND:-}" == "baseline" ]] || { echo "selftest failed: SNAPSHOT_KIND" >&2; return 1; }
  [[ "${TESTS_PASS:-}" == "1" ]] || { echo "selftest failed: TESTS_PASS" >&2; return 1; }
  [[ "${E2E_PASS:-}" == "0" ]] || { echo "selftest failed: E2E_PASS" >&2; return 1; }
  [[ "${FAILURE_COUNT:-}" == "1" ]] || { echo "selftest failed: FAILURE_COUNT" >&2; return 1; }

  rm -rf "$tmp_dir"
  echo "baseline-snapshot selftest passed"
  return 0
}

main() {
  local out="" tests_cmd="" e2e_cmd="" lint_cmd="" typecheck_cmd=""

  if [[ "${1:-}" == "--selftest" ]]; then
    selftest
    return $?
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --out) out="${2:-}"; shift 2 ;;
      --tests-cmd) tests_cmd="${2:-}"; shift 2 ;;
      --e2e-cmd) e2e_cmd="${2:-}"; shift 2 ;;
      --lint-cmd) lint_cmd="${2:-}"; shift 2 ;;
      --typecheck-cmd) typecheck_cmd="${2:-}"; shift 2 ;;
      -h|--help) usage; return 0 ;;
      *)
        echo "error: unknown argument '$1'" >&2
        usage
        return 64
        ;;
    esac
  done

  if [[ -z "$out" || -z "$tests_cmd" || -z "$e2e_cmd" || -z "$lint_cmd" || -z "$typecheck_cmd" ]]; then
    usage
    return 64
  fi

  local root parent
  root="$(resolve_root)"
  parent="$(dirname "$out")"
  mkdir -p "$parent"
  write_manifest "$out" "$root" "$tests_cmd" "$e2e_cmd" "$lint_cmd" "$typecheck_cmd"
  echo "baseline snapshot written: $out"
  return 0
}

main "$@"
