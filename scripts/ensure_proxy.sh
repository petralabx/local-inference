#!/usr/bin/env bash
# ensure_proxy.sh - idempotent watchdog for the LiteLLM proxy on :4000.
#
# Exits 0 immediately when the proxy already answers /health/liveliness.
# Otherwise starts it detached via start_proxy.sh and logs the recovery.
#
# Registered as the Windows Scheduled Task "LocalInferenceProxyWatchdog"
# (at logon + every 5 minutes). The older "LocalInferenceProxy" task only
# fired at logon, so a mid-session crash left the whole local model lane
# dead until the next login -- which is exactly what happened between
# 2026-07-27 and 2026-07-31.
set -uo pipefail
cd "$(dirname "$0")/.."

PORT="${LITELLM_PORT:-4000}"
HEALTH="http://127.0.0.1:${PORT}/health/liveliness"
WD_LOG="${LITELLM_WATCHDOG_LOG:-/tmp/litellm_watchdog.log}"
LOCKDIR="/tmp/.litellm_watchdog.lock.d"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$WD_LOG"; }

# Serialize: never race two starts against the same port. mkdir is atomic;
# flock is NOT available in Git Bash on Windows, so do not reintroduce it.
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  # Reap a lock left behind by a killed run (older than 5 minutes).
  if [ -d "$LOCKDIR" ] && [ -z "$(find "$LOCKDIR" -maxdepth 0 -newermt '-5 minutes' 2>/dev/null)" ]; then
    log "removing stale lock $LOCKDIR"
    rmdir "$LOCKDIR" 2>/dev/null || true
  fi
  mkdir "$LOCKDIR" 2>/dev/null || exit 0
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT INT TERM

if curl -fsS -m 5 -o /dev/null "$HEALTH" 2>/dev/null; then
  exit 0
fi

log "proxy DOWN on :${PORT} - starting"
nohup ./scripts/start_proxy.sh >>/tmp/litellm_proxy.log 2>&1 &
disown 2>/dev/null || true

for _ in $(seq 1 30); do
  sleep 2
  if curl -fsS -m 5 -o /dev/null "$HEALTH" 2>/dev/null; then
    log "proxy RECOVERED on :${PORT}"
    exit 0
  fi
done

log "proxy FAILED to come up on :${PORT} after 60s - see /tmp/litellm_proxy.log"
exit 1
