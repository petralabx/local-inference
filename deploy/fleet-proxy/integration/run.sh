#!/usr/bin/env bash
# Integration test for the fleet proxy deployment (agent fleet spec P1).
#
#   bash deploy/fleet-proxy/integration/run.sh
#
# Needs Docker on a Linux build host. Never run it on a trading host.
# It starts one disposable Ubuntu 24.04 container with systemd and
# PostgreSQL, installs the fleet proxy in it by the README steps, and runs
# in-host.sh. Stubs stand in for the AWS CLI and tailscale, and the keys are
# dummy values. The container has network only for the install and the first
# start (pip, Prisma engines). run.sh then disconnects it, so no request can
# reach a model provider; the openai/ aliases go to a fake upstream on
# 127.0.0.1. The container is removed at the end (FLEET_IT_KEEP=1 keeps it).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
image="fleet-proxy-it:local"
name="fleet-proxy-it-$$"

cleanup() {
  if [ "${FLEET_IT_KEEP:-0}" = 1 ]; then
    echo "run.sh: kept container $name"
  else
    docker rm -f "$name" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "run.sh: host $(hostname), repo $repo, $(git -C "$repo" rev-parse --short HEAD 2>/dev/null || echo 'no git')"
docker build -q -t "$image" "$here" >/dev/null
# systemd as PID 1 needs a private cgroup namespace and the privileges to
# set up the unit sandboxes (PrivateTmp, ProtectSystem).
docker run -d --name "$name" --hostname fleet-proxy-it --privileged --cgroupns=private \
  --tmpfs /run --tmpfs /run/lock -v "$repo:/src:ro" "$image" >/dev/null
for _ in $(seq 1 60); do
  state="$(docker exec "$name" systemctl is-system-running 2>/dev/null || true)"
  case "$state" in running|degraded) break ;; esac
  sleep 1
done
echo "run.sh: container $name, systemd state: $state"

rc=0
docker exec "$name" bash /src/deploy/fleet-proxy/integration/in-host.sh install || rc=$?
if [ "$rc" -ne 0 ]; then
  echo "run.sh: install phase failed (exit $rc)"
  exit "$rc"
fi
docker network disconnect bridge "$name"
echo "run.sh: network disconnected"
docker exec "$name" bash /src/deploy/fleet-proxy/integration/in-host.sh checks || rc=$?
echo "run.sh: exit $rc"
exit "$rc"
