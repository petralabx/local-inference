#!/usr/bin/env bash
#
# scope-check.sh — enforce a phase's scope-lock on its changed files.
#
# Usage: scope-check.sh "<owns globs>" "<forbidden globs>" <file> [<file> ...]
#   owns globs:      space-separated globs the phase MAY write (at least one match required)
#   forbidden globs: space-separated globs that AUTO-REJECT if matched (may be empty "")
#
# A file is a violation if it matches any forbidden glob, or matches no owns glob.
# Globs use shell matching; ** is treated like * (matches across directories).
#
# Exit 0: all files in scope.  Exit 2: one or more violations.  Exit 64: usage.

set -uo pipefail

if [[ $# -lt 3 ]]; then
  echo "usage: scope-check.sh \"<owns globs>\" \"<forbidden globs>\" <file> [<file> ...]" >&2
  exit 64
fi

owns_raw="$1"; forbidden_raw="$2"; shift 2
read -r -a owns <<< "$owns_raw"
read -r -a forbidden <<< "$forbidden_raw"

# Normalize a glob for [[ == ]] matching: ** -> * ( * already spans '/' in [[ ]] ).
norm() { printf '%s' "${1//\*\*/\*}"; }

violations=0
for f in "$@"; do
  [[ -z "$f" ]] && continue

  hit_forbidden=0
  for g in "${forbidden[@]}"; do
    [[ -z "$g" ]] && continue
    # shellcheck disable=SC2053
    if [[ "$f" == $(norm "$g") ]]; then hit_forbidden=1; break; fi
  done
  if [[ "$hit_forbidden" -eq 1 ]]; then
    echo "SCOPE_VIOLATION forbidden: $f"
    violations=$((violations+1))
    continue
  fi

  in_owns=0
  for g in "${owns[@]}"; do
    [[ -z "$g" ]] && continue
    # shellcheck disable=SC2053
    if [[ "$f" == $(norm "$g") ]]; then in_owns=1; break; fi
  done
  if [[ "$in_owns" -eq 0 ]]; then
    echo "SCOPE_VIOLATION not_owned: $f"
    violations=$((violations+1))
  fi
done

if [[ "$violations" -gt 0 ]]; then
  echo "scope-check: $violations violation(s)"
  exit 2
fi
echo "scope-check: OK ($# file(s) in scope)"
exit 0
