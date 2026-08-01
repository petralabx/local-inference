#!/usr/bin/env bash
# Idempotent Linux/Cloud Agent venv bootstrap for LiteLLM tooling.
# Dell Windows hosts continue to use .venv/Scripts; do not call this there.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS* || "$(uname -s)" == CYGWIN* ]]; then
  printf 'setup_linux_venv.sh is for Linux/Cloud Agents. Use Windows .venv/Scripts on Dell.\n' >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  printf 'MISSING: %s not found\n' "$PYTHON_BIN" >&2
  exit 1
fi

# Cloud base images often lack ensurepip; install the distro venv package once.
if ! "$PYTHON_BIN" -c 'import ensurepip' >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    PY_MINOR="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "python${PY_MINOR}-venv" python3-pip
  else
    printf 'MISSING: ensurepip (install python3-venv / equivalent)\n' >&2
    exit 1
  fi
fi

if [[ ! -x .venv/bin/python ]]; then
  rm -rf .venv
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt

printf 'Linux venv ready: %s\n' "$(.venv/bin/python -c 'import sys; print(sys.executable)')"
.venv/bin/python -m pip show litellm | sed -n '1,3p'
