#!/usr/bin/env bash
#
# ui-conformance-scan.sh — G1 design-system conformance gate for the
# ui-ux-design-loop skill.
#
# Reuses the repo's canonical token checker (scripts/check-vmc-theme-tokens.py)
# but enforces a STRICTER, loop-scoped rule: ZERO raw-color findings in the
# files this loop changed. The global ratchet inside check-vmc-theme-tokens.py
# (MAX_ALLOWED_VIOLATIONS) is the team-wide CI baseline and is left untouched —
# this gate only judges the loop's own diff so a UI loop never adds new drift.
#
# It also runs an advisory shared-component-usage heuristic (raw <button>/<a>
# controls that often should use ActionButton / shared nav primitives). That is
# a WARN by default and only fails under --strict-components.
#
# Usage:
#   ui-conformance-scan.sh [--base <ref>] [--staged] [--files "<f1 f2 ...>"]
#                          [--strict-components] [--selftest]
#
# Default change set: git diff --name-only <base>...HEAD  (base = origin/main).
#
# Exit codes:
#   0 — no raw-color findings in scoped files (and components OK when --strict-components)
#   1 — raw-color findings in scoped files, or component violations under --strict-components
#   64 — usage error
#
# Self-locates the repo root: UI_LOOP_REPO_ROOT/VMC_REPO_ROOT -> git rev-parse -> pwd.

set -uo pipefail

usage() {
  cat <<'EOF'
usage:
  ui-conformance-scan.sh [--base <ref>] [--staged] [--files "<f1 f2 ...>"]
                         [--strict-components] [--selftest]
EOF
}

resolve_root() {
  if [[ -n "${UI_LOOP_REPO_ROOT:-}" && -d "${UI_LOOP_REPO_ROOT:-}" ]]; then
    printf '%s\n' "$UI_LOOP_REPO_ROOT"
    return 0
  fi
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

TOKEN_CHECK_COMMAND="python3"
TOKEN_CHECK_ARGS=("scripts/check-vmc-theme-tokens.py")
TOKEN_CHECK_FILE_GLOBS=("apps/vmc-web/src/*.ts" "apps/vmc-web/src/*.tsx")
COMPONENT_HINTS=("ActionButton" "PageHeader" "vmc-pill")

resolve_key_from_manifest() {
  local root="$1" key="$2"
  local resolver="$root/.cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs"
  [[ -f "$resolver" ]] || return 1
  command -v node >/dev/null 2>&1 || return 1
  local out value
  out="$(UI_LOOP_REPO_ROOT="$root" node "$resolver" --key "$key" 2>/dev/null)" || return 1
  value="$(printf '%s\n' "$out" | awk 'NF { line=$0 } END { print line }')"
  [[ -n "$value" ]] || return 1
  printf '%s\n' "$value"
}

resolve_array_from_manifest() {
  local root="$1" key="$2" out_var="$3"
  # shellcheck disable=SC2034
  local -n out_ref="$out_var"
  out_ref=()
  local idx=0 value
  while value="$(resolve_key_from_manifest "$root" "${key}.${idx}")"; do
    out_ref+=("$value")
    idx=$((idx + 1))
  done
  [[ "${#out_ref[@]}" -gt 0 ]]
}

load_manifest_overrides() {
  local root="$1"
  local cmd
  if cmd="$(resolve_key_from_manifest "$root" "tokenCheck.command")"; then
    TOKEN_CHECK_COMMAND="$cmd"
  fi
  local token_args=()
  if resolve_array_from_manifest "$root" "tokenCheck.args" token_args; then
    TOKEN_CHECK_ARGS=("${token_args[@]}")
  fi
  local file_globs=()
  if resolve_array_from_manifest "$root" "tokenCheck.fileGlobs" file_globs; then
    TOKEN_CHECK_FILE_GLOBS=("${file_globs[@]}")
  fi
  local component_map=()
  if resolve_array_from_manifest "$root" "componentMap" component_map; then
    COMPONENT_HINTS=("${component_map[@]}")
  fi
}

matches_token_file_glob() {
  local path="$1" glob
  for glob in "${TOKEN_CHECK_FILE_GLOBS[@]}"; do
    if [[ "$path" == $glob ]]; then
      return 0
    fi
  done
  return 1
}

# Print the VMC TS/TSX files in the change set, one per line.
collect_changed_files() {
  local root="$1" base="$2" staged="$3" explicit="$4"
  local raw=()
  if [[ -n "$explicit" ]]; then
    # shellcheck disable=SC2206
    raw=($explicit)
  elif [[ "$staged" == "1" ]]; then
    mapfile -t raw < <(git -C "$root" diff --name-only --cached 2>/dev/null)
  else
    mapfile -t raw < <(git -C "$root" diff --name-only "${base}...HEAD" 2>/dev/null)
    if [[ "${#raw[@]}" -eq 0 ]]; then
      # Fall back to uncommitted working-tree changes when the range is empty.
      mapfile -t raw < <(git -C "$root" diff --name-only 2>/dev/null)
    fi
  fi
  local f
  for f in "${raw[@]}"; do
    [[ -z "$f" ]] && continue
    if matches_token_file_glob "$f"; then
      printf '%s\n' "$f"
    fi
  done
}

run_gate() {
  local root="$1" base="$2" staged="$3" explicit="$4" strict_components="$5"
  if ! command -v "$TOKEN_CHECK_COMMAND" >/dev/null 2>&1; then
    echo "error: token checker command not found: $TOKEN_CHECK_COMMAND" >&2
    return 64
  fi
  if [[ "${#TOKEN_CHECK_ARGS[@]}" -gt 0 && "${TOKEN_CHECK_ARGS[0]}" == *"/"* && ! -f "$root/${TOKEN_CHECK_ARGS[0]}" ]]; then
    echo "error: token checker script not found at $root/${TOKEN_CHECK_ARGS[0]}" >&2
    return 64
  fi

  local files=()
  mapfile -t files < <(collect_changed_files "$root" "$base" "$staged" "$explicit")

  echo "============================================================"
  echo "UI CONFORMANCE SCAN (G1) — loop-scoped, zero new drift"
  echo "============================================================"
  echo "Scoped VMC TS files: ${#files[@]}"

  if [[ "${#files[@]}" -eq 0 ]]; then
    echo "No scoped VMC TypeScript changes — G1 PASS (nothing to check)."
    return 0
  fi
  printf '  %s\n' "${files[@]}"

  # 1) Hard gate: raw-color findings in scoped files (reuse canonical checker).
  local checker_out findings checker_cmd=()
  checker_cmd=("$TOKEN_CHECK_COMMAND" "${TOKEN_CHECK_ARGS[@]}" "${files[@]}")
  checker_out="$(cd "$root" && "${checker_cmd[@]}" 2>&1)"
  findings="$(printf '%s\n' "$checker_out" | sed -n 's/^Findings:[[:space:]]*\([0-9][0-9]*\).*/\1/p' | awk 'NR==1 { print; exit }')"
  findings="${findings:-0}"

  echo "------------------------------------------------------------"
  echo "Token findings in scoped files: $findings"
  if [[ "$findings" -gt 0 ]]; then
    printf '%s\n' "$checker_out" | sed -n '/^  /p'
  fi

  # 2) Advisory: raw control primitives that often should use shared components.
  local comp_hits
  comp_hits="$(cd "$root" && grep -nE '<(button|a)[[:space:]>]' "${files[@]}" 2>/dev/null \
    | grep -vE 'data-ui-inert' | wc -l | tr -d ' ')"
  comp_hits="${comp_hits:-0}"
  echo "Raw <button>/<a> occurrences in scoped files (advisory): $comp_hits"
  if [[ "$comp_hits" -gt 0 ]]; then
    local hint_list
    hint_list="$(printf '%s, ' "${COMPONENT_HINTS[@]}")"
    hint_list="${hint_list%, }"
    echo "  hint: prefer shared primitives (${hint_list});"
    echo "  annotate intentionally-raw controls and re-check. See reference.md."
  fi

  local rc=0
  if [[ "$findings" -gt 0 ]]; then
    echo ""
    echo "Result: FAIL — $findings raw-color finding(s) in loop-changed files (target: 0)."
    rc=1
  elif [[ "$strict_components" == "1" && "$comp_hits" -gt 0 ]]; then
    echo ""
    echo "Result: FAIL (--strict-components) — $comp_hits raw control(s) in scoped files."
    rc=1
  else
    echo ""
    echo "Result: PASS — no new design-token drift in loop-changed files."
  fi
  return "$rc"
}

selftest() {
  local tmp root_out
  tmp="$(mktemp -d)"
  # A self-locating sanity check that does not require the full VMC toolchain.
  root_out="$(VMC_REPO_ROOT="$tmp" resolve_root)"
  [[ "$root_out" == "$tmp" ]] || { echo "selftest failed: resolve_root override" >&2; rm -rf "$tmp"; return 1; }
  # collect_changed_files must emit only apps/vmc-web/src TS files from an explicit list.
  local got
  got="$(collect_changed_files "$tmp" "origin/main" "0" \
    "apps/vmc-web/src/components/vmc/x.tsx README.md src/other.ts apps/vmc-web/src/lib/y.ts" \
    | tr '\n' ',')"
  [[ "$got" == "apps/vmc-web/src/components/vmc/x.tsx,apps/vmc-web/src/lib/y.ts," ]] \
    || { echo "selftest failed: file filter -> '$got'" >&2; rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
  echo "ui-conformance-scan selftest passed"
  return 0
}

main() {
  local base="origin/main" staged="0" explicit="" strict_components="0"
  local root
  root="$(resolve_root)"
  load_manifest_overrides "$root"

  if [[ "${1:-}" == "--selftest" ]]; then
    selftest
    return $?
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --base) base="${2:-}"; shift 2 ;;
      --staged) staged="1"; shift ;;
      --files) explicit="${2:-}"; shift 2 ;;
      --strict-components) strict_components="1"; shift ;;
      -h|--help) usage; return 0 ;;
      *) echo "error: unknown argument '$1'" >&2; usage; return 64 ;;
    esac
  done

  run_gate "$root" "$base" "$staged" "$explicit" "$strict_components"
}

main "$@"
