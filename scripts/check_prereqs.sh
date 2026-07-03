#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

printf '== local-inference prereq check ==\n'
printf 'PWD=%s\n' "$PWD"
printf 'HOST=%s\n' "$(hostname 2>/dev/null || printf unknown)"
printf '\n-- network --\n'
(ipconfig 2>/dev/null || true) | grep -E 'IPv4 Address|Default Gateway|Ethernet adapter|Wireless LAN adapter' | head -80 || true

printf '\n-- gpu --\n'
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=index,name,memory.total,memory.free,driver_version,compute_cap --format=csv,noheader,nounits || nvidia-smi
else
  printf 'MISSING: nvidia-smi not found\n'
fi

printf '\n-- docker --\n'
if command -v docker >/dev/null 2>&1; then
  docker --version
  docker info --format 'Server={{.ServerVersion}} OSType={{.OSType}}' 2>/dev/null || docker info 2>&1 | sed -n '1,60p'
else
  printf 'MISSING: docker not found. Install Docker Desktop + WSL2 + GPU support, then reopen shell.\n'
fi

printf '\n-- python/venv --\n'
python --version 2>&1 || true
if [ -x .venv/Scripts/python.exe ]; then
  .venv/Scripts/python.exe --version
  .venv/Scripts/python.exe -m pip show litellm >/dev/null 2>&1 && printf 'LiteLLM installed in .venv\n' || printf 'LiteLLM not installed in .venv\n'
else
  printf '.venv not created yet\n'
fi

printf '\n-- ports --\n'
python - <<'PY'
import socket
for port in [4000,8000,8001]:
    s=socket.socket(); s.settimeout(.5)
    try:
        s.connect(('127.0.0.1', port)); print(f'{port}: open')
    except Exception as e:
        print(f'{port}: closed ({e.__class__.__name__})')
    finally:
        s.close()
PY
