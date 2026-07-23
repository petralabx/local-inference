#!/usr/bin/env bash
#
# ui-responsive-matrix.sh — G3 responsive-integrity runner for the
# ui-ux-design-loop skill.
#
# Runs the Playwright E2E suite (or a scoped spec) across the desktop / tablet /
# mobile project matrix and supports per-viewport screenshot baselines via
# Playwright's built-in toHaveScreenshot(). No new dependency — this is a thin
# wrapper over `npx playwright test` that pins the matrix the loop cares about.
#
# Baselines live next to their specs under apps/vmc-web/e2e (Playwright default
# <spec>-snapshots/), committed to git, and diffed with a conservative
# maxDiffPixelRatio set in the spec. Regenerate intentionally with
# --update-snapshots (never blindly in the loop's fix step).
#
# Usage:
#   ui-responsive-matrix.sh [--spec <file>] [--projects "chromium tablet mobile-chrome"]
#                           [--update-snapshots] [--include-safari] [--no-bypass]
#                           [--selftest]
#
# Defaults are read from ui-loop manifest (viewports/appDir/baseUrlEnv) through
# ui-loop-config.mjs with fallback to VMC-compatible values when resolution fails.
#
# Exit codes: passes through Playwright's exit code; 64 on usage error.
#
# Self-locates the repo root: UI_LOOP_REPO_ROOT/VMC_REPO_ROOT -> git rev-parse -> pwd.

set -uo pipefail

usage() {
  cat <<'EOF'
usage:
  ui-responsive-matrix.sh [--spec <file>] [--projects "chromium tablet mobile-chrome"]
                          [--update-snapshots] [--include-safari] [--no-bypass]
                          [--selftest]
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

manifest_key_raw() {
  local resolver="$1" key="$2" raw
  raw="$(node "$resolver" --key "$key" 2>/dev/null)" || return 1
  printf '%s\n' "$raw" | awk '!/^PASS:/'
}

manifest_key_string() {
  local resolver="$1" key="$2" raw trimmed
  raw="$(manifest_key_raw "$resolver" "$key")" || return 1
  trimmed="$(printf '%s\n' "$raw" | awk 'NF {last=$0} END {print last}')"
  [[ -n "$trimmed" ]] || return 1
  printf '%s\n' "$trimmed"
}

manifest_key_array_words() {
  local resolver="$1" key="$2" raw
  raw="$(manifest_key_raw "$resolver" "$key")" || return 1
  printf '%s\n' "$raw" | node -e 'const fs=require("fs"); const txt=fs.readFileSync(0,"utf8").trim(); if(!txt) process.exit(1); const arr=JSON.parse(txt); if(!Array.isArray(arr) || arr.length===0 || arr.some(v=>typeof v!=="string" || !v.trim())) process.exit(1); process.stdout.write(arr.join(" "));' || return 1
}

load_manifest_defaults() {
  local root="$1"
  local default_projects="chromium tablet mobile-chrome"
  local default_app_dir="apps/vmc-web"
  local default_base_url_env="E2E_BASE_URL"
  local default_auth_bypass_env="VMC_LOCAL_AUTH_BYPASS"
  local resolver="$root/.cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs"

  CONFIG_PROJECTS="$default_projects"
  CONFIG_APP_DIR="$default_app_dir"
  CONFIG_BASE_URL_ENV="$default_base_url_env"
  CONFIG_AUTH_BYPASS_ENV="$default_auth_bypass_env"
  CONFIG_NOTES=()

  if [[ ! -f "$resolver" || ! -x "$(command -v node 2>/dev/null)" ]]; then
    CONFIG_NOTES+=("manifest unresolved; using VMC fallback defaults")
    return 0
  fi

  local val
  if val="$(manifest_key_array_words "$resolver" "viewports")"; then
    CONFIG_PROJECTS="$val"
  else
    CONFIG_NOTES+=("viewports unresolved; using '$default_projects'")
  fi

  if val="$(manifest_key_string "$resolver" "appDir")"; then
    CONFIG_APP_DIR="$val"
  else
    CONFIG_NOTES+=("appDir unresolved; using '$default_app_dir'")
  fi

  if val="$(manifest_key_string "$resolver" "baseUrlEnv")"; then
    CONFIG_BASE_URL_ENV="$val"
  else
    CONFIG_NOTES+=("baseUrlEnv unresolved; using '$default_base_url_env'")
  fi

  if val="$(manifest_key_string "$resolver" "authBypassEnv")"; then
    CONFIG_AUTH_BYPASS_ENV="$val"
  else
    CONFIG_NOTES+=("authBypassEnv unresolved; using '$default_auth_bypass_env'")
  fi
}

build_args() {
  # Args: <spec> <projects> <update> <include_safari>
  # Emits the playwright CLI args, one per line (safe for arrays with spaces).
  local spec="$1" projects="$2" update="$3" include_safari="$4"
  printf '%s\n' "test"
  if [[ -n "$spec" ]]; then
    printf '%s\n' "$spec"
  fi
  local p
  for p in $projects; do
    printf '%s\n' "--project=$p"
  done
  if [[ "$include_safari" == "1" ]]; then
    printf '%s\n' "--project=mobile-safari"
  fi
  if [[ "$update" == "1" ]]; then
    printf '%s\n' "--update-snapshots"
  fi
}

selftest() {
  local tmp got
  tmp="$(mktemp -d)"
  [[ "$(UI_LOOP_REPO_ROOT="$tmp" resolve_root)" == "$tmp" ]] \
    || { echo "selftest failed: resolve_root override" >&2; rm -rf "$tmp"; return 1; }
  got="$(build_args "e2e/ui-a11y.spec.ts" "chromium tablet" "1" "1" | tr '\n' '|')"
  [[ "$got" == "test|e2e/ui-a11y.spec.ts|--project=chromium|--project=tablet|--project=mobile-safari|--update-snapshots|" ]] \
    || { echo "selftest failed: build_args -> '$got'" >&2; rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
  echo "ui-responsive-matrix selftest passed"
  return 0
}

main() {
  local spec="" projects="" update="0" include_safari="0" bypass="1"

  if [[ "${1:-}" == "--selftest" ]]; then
    selftest
    return $?
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --spec) spec="${2:-}"; shift 2 ;;
      --projects) projects="${2:-}"; shift 2 ;;
      --update-snapshots) update="1"; shift ;;
      --include-safari) include_safari="1"; shift ;;
      --no-bypass) bypass="0"; shift ;;
      -h|--help) usage; return 0 ;;
      *) echo "error: unknown argument '$1'" >&2; usage; return 64 ;;
    esac
  done

  local root app base_url_val note
  root="$(resolve_root)"
  load_manifest_defaults "$root"
  if [[ -z "$projects" ]]; then
    projects="$CONFIG_PROJECTS"
  fi
  app="$root/$CONFIG_APP_DIR"
  if [[ ! -f "$app/playwright.config.ts" ]]; then
    echo "error: playwright config not found at $app/playwright.config.ts" >&2
    return 64
  fi

  local args=()
  mapfile -t args < <(build_args "$spec" "$projects" "$update" "$include_safari")

  echo "============================================================"
  echo "UI RESPONSIVE MATRIX (G3)"
  echo "============================================================"
  echo "projects : $projects$([[ "$include_safari" == "1" ]] && echo " mobile-safari")"
  echo "spec     : ${spec:-<all e2e>}"
  base_url_val="${!CONFIG_BASE_URL_ENV:-<unset>}"
  echo "base-url : $CONFIG_BASE_URL_ENV=$base_url_val"
  echo "bypass   : $CONFIG_AUTH_BYPASS_ENV=$bypass"
  for note in "${CONFIG_NOTES[@]}"; do
    echo "note     : $note"
  done
  echo "command  : npx playwright ${args[*]}"
  echo "------------------------------------------------------------"

  (
    cd "$app" || exit 64
    if [[ "$bypass" == "1" ]]; then
      env "$CONFIG_AUTH_BYPASS_ENV=1" npx playwright "${args[@]}"
    else
      npx playwright "${args[@]}"
    fi
  )
}

main "$@"
