#!/usr/bin/env bash
#
# pilots-run.sh — run the five guided-project-discovery pilot scenarios.
#
# Three fixtures must validate and two must be rejected. Asserting the expected
# exit code in both directions is the point: a validator that only ever sees
# well-formed input cannot be distinguished from one that passes everything.
#
# Usage:
#   pilots-run.sh
#
# Exit 0 when all five scenarios behave as expected, 1 otherwise.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PILOTS="${SCRIPT_DIR}/../examples/pilots"

pass=0
fail=0

# run_case <label> <validator> <fixture> <expected-exit> [expected-substring ...]
run_case() {
  local label="$1" validator="$2" fixture="$3" expected="$4"
  shift 4

  # Problems accumulate as lines rather than array elements: bash 3.2 — still the
  # system bash on macOS, which scripts/sync-skills.sh installs to — treats
  # ${#arr[@]} on an empty array as an unbound variable under `set -u`.
  local out rc problems=""
  out="$(bash "${SCRIPT_DIR}/${validator}" "${PILOTS}/${fixture}" 2>&1)"
  rc=$?

  [[ "$rc" -eq "$expected" ]] || problems+="expected exit ${expected}, got ${rc}"$'\n'

  local needle
  for needle in "$@"; do
    grep -qF -- "$needle" <<<"$out" || problems+="expected output to mention: ${needle}"$'\n'
  done

  if [[ -z "$problems" ]]; then
    echo "PASS  ${label}"
    pass=$((pass + 1))
  else
    echo "FAIL  ${label}"
    printf '%s' "$problems" | sed 's/^/        /'
    printf '%s\n' "$out" | sed 's/^/        | /'
    fail=$((fail + 1))
  fi
}

echo "guided-project-discovery — pilot scenarios"
echo

run_case "1 sufficient context short-circuits the interview" \
  discovery-validate.sh 01-sufficient-context.DISCOVERY.md 0 \
  "OK: DISCOVERY.md valid"

run_case "2 interrupted session resumes from lens_cursor" \
  discovery-validate.sh 02-interrupted-resume.DISCOVERY.md 0 \
  "status interviewing"

run_case "3 conflicting required approvers resolved by a human disposition" \
  review-validate.sh 03-conflicting-reviewers.round-1.md 0 \
  "verdict approved-for-research+plan"

run_case "4 plan approval is rejected when it claims execution authority" \
  review-validate.sh 04-execution-not-authorized.round-1.md 1 \
  "a review round never authorizes execution" \
  "must carry Scope Limit: does-not-authorize-execution"

run_case "5 approvals bound to a superseded candidate or authority revision are stale" \
  review-validate.sh 05-stale-approval.round-3.md 1 \
  "A1 is stale" \
  "A2 is stale" \
  "has no non-stale approval"

echo
echo "selftests"
echo

for validator in discovery-validate.sh review-validate.sh; do
  if out="$(bash "${SCRIPT_DIR}/${validator}" --selftest 2>&1)"; then
    echo "PASS  ${validator} --selftest"
    pass=$((pass + 1))
  else
    echo "FAIL  ${validator} --selftest"
    printf '        | %s\n' "$out"
    fail=$((fail + 1))
  fi
done

echo
echo "${pass} passed, ${fail} failed"
[[ "$fail" -eq 0 ]]
