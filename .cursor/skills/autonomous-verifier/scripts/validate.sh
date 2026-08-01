#!/usr/bin/env bash
set -euo pipefail

echo "[autonomous-verifier] Starting reliability validation"

# Resolve the repo under test (the current project), not the skill's home repo.
# Override with VMC_REPO_ROOT; otherwise use the git work tree; fall back to cwd.
if [[ -n "${VMC_REPO_ROOT:-}" && -d "${VMC_REPO_ROOT}" ]]; then
  REPO_ROOT="${VMC_REPO_ROOT}"
elif REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  REPO_ROOT="$(pwd)"
fi

run_npm() {
  local label="$1"
  local cmd="$2"
  local cwd="$3"
  if command -v npm >/dev/null 2>&1; then
    echo "[autonomous-verifier] ${label}"
    (cd "$cwd" && bash -lc "$cmd")
  else
    echo "[autonomous-verifier] npm unavailable; cannot run ${label}" >&2
    exit 1
  fi
}

run_package_checks() {
  local label="$1"
  local package_dir="$2"
  local contracts_script="$3"

  if [[ ! -f "${package_dir}/package.json" ]]; then
    echo "[autonomous-verifier] ${label}: package.json missing at ${package_dir}" >&2
    exit 1
  fi

  run_npm "${label}: lint" "npm run lint" "$package_dir"
  run_npm "${label}: typecheck" "npm run typecheck" "$package_dir"
  run_npm "${label}: test" "npm test" "$package_dir"

  if (cd "$package_dir" && node -e 'const scripts = require("./package.json").scripts || {}; process.exit(Object.prototype.hasOwnProperty.call(scripts, process.argv[1]) ? 0 : 1)' "${contracts_script}"); then
    run_npm "${label}: ${contracts_script}" "npm run ${contracts_script}" "$package_dir"
  else
    echo "[autonomous-verifier] ${label}: ${contracts_script} script not defined" >&2
    exit 1
  fi
}

if [[ -f "${REPO_ROOT}/apps/vmc-web/package.json" ]]; then
  run_package_checks "vmc-web" "${REPO_ROOT}/apps/vmc-web" "test:contracts"
elif [[ -f "${REPO_ROOT}/package.json" ]]; then
  run_package_checks "repo-root" "${REPO_ROOT}" "test:contract"
else
  echo "[autonomous-verifier] No supported package.json found; cannot validate" >&2
  exit 1
fi

if [[ -f "${REPO_ROOT}/scripts/assert-staging-context.sh" ]]; then
  if [[ -f "${HOME}/.secrets-env.staging" ]]; then
    # shellcheck disable=SC1091
    source "${HOME}/.secrets-env.staging"
    (cd "${REPO_ROOT}" && bash scripts/assert-staging-context.sh)
    echo "[autonomous-verifier] Staging context check passed"
  else
    echo "[autonomous-verifier] ~/.secrets-env.staging not found; skipping staging assertion"
  fi
else
  echo "[autonomous-verifier] scripts/assert-staging-context.sh not found; skipping staging assertion"
fi

echo "[autonomous-verifier] Validation complete"
