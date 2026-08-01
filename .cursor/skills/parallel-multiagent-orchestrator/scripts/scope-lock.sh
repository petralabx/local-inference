#!/usr/bin/env bash
# parallel-multiagent-orchestrator — scope-lock enforcement
#
# Usage: scope-lock.sh <domain> <patch-path> [<ownership-json>]
#   domain:          domain name (chat | swarm | todos | second-brain)
#   patch-path:      path to a git patch file (output of `git diff`)
#   ownership-json:  optional path to ownership manifest (default: eval/ownership.json)
#
# Exit codes:
#   0   patch is in-scope; candidate eligible for scoring
#   2   SCOPE_LOCK_VIOLATION forbidden: <path>  (touches a .forbidden glob)
#   3   SCOPE_LOCK_VIOLATION not_owned: <path>  (outside .owns globs)
#   64  usage error
#   66  ownership manifest missing
#   67  patch file missing or unreadable
#
# Mirrors the canonical scope-lock per
# .cursor/skills/vmc-autoresearch-core/reference.md §7.
#
# Glob semantics: uses bash extglob + `==` pattern matching. Supports '**'
# as a literal segment wildcard (approximated via shopt -s globstar where possible).

set -euo pipefail

DOMAIN="${1:-}"
PATCH="${2:-}"
MANIFEST="${3:-eval/ownership.json}"

if [[ -z "$DOMAIN" || -z "$PATCH" ]]; then
  echo "Usage: $0 <domain> <patch-path> [<ownership-json>]" >&2
  exit 64
fi

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: ownership manifest not found: $MANIFEST" >&2
  exit 66
fi

if [[ ! -r "$PATCH" ]]; then
  echo "ERROR: patch file not readable: $PATCH" >&2
  exit 67
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required for scope-lock enforcement" >&2
  exit 64
fi

# Cross-check: manifest declares this domain?
MANIFEST_DOMAIN=$(jq -r '.domain // empty' "$MANIFEST")
if [[ -n "$MANIFEST_DOMAIN" && "$MANIFEST_DOMAIN" != "$DOMAIN" ]]; then
  echo "ERROR: manifest domain='$MANIFEST_DOMAIN' but caller passed '$DOMAIN'" >&2
  exit 64
fi

# Enable recursive globbing + extglob for richer patterns.
shopt -s globstar extglob nullglob

mapfile -t OWNS      < <(jq -r '.owns[]              // empty' "$MANIFEST")
mapfile -t READONLY  < <(jq -r '.consumes_readonly[] // empty' "$MANIFEST")
mapfile -t FORBIDDEN < <(jq -r '.forbidden[]         // empty' "$MANIFEST")

# Extract touched files from the patch. Handle both `git diff` and `diff -u` styles.
TOUCHED=$(awk '
  /^diff --git / { print $3 " " $4; next }
  /^\+\+\+ b\// { sub(/^\+\+\+ b\//, ""); print $0 }
' "$PATCH" | tr ' ' '\n' | sed -e 's|^a/||' -e 's|^b/||' | awk 'NF && !seen[$0]++')

if [[ -z "$TOUCHED" ]]; then
  echo "ERROR: no files detected in patch $PATCH" >&2
  exit 67
fi

matches_any() {
  local path="$1"; shift
  local pat
  for pat in "$@"; do
    # Pattern matches on full path using bash extglob semantics.
    # shellcheck disable=SC2053
    if [[ $path == $pat ]]; then
      return 0
    fi
  done
  return 1
}

violations=0

while IFS= read -r f; do
  [[ -z "$f" ]] && continue

  if (( ${#FORBIDDEN[@]} > 0 )) && matches_any "$f" "${FORBIDDEN[@]}"; then
    echo "SCOPE_LOCK_VIOLATION forbidden: $f"
    violations=2
    break
  fi

  if (( ${#OWNS[@]} > 0 )) && matches_any "$f" "${OWNS[@]}"; then
    continue
  fi

  if (( ${#READONLY[@]} > 0 )) && matches_any "$f" "${READONLY[@]}"; then
    echo "SCOPE_LOCK_VIOLATION not_owned: $f (readonly-consume only)"
    violations=3
    break
  fi

  echo "SCOPE_LOCK_VIOLATION not_owned: $f"
  violations=3
  break
done <<< "$TOUCHED"

if (( violations > 0 )); then
  exit "$violations"
fi

echo "scope-lock OK: $(wc -l <<< "$TOUCHED") file(s) in scope for domain=$DOMAIN"
exit 0
