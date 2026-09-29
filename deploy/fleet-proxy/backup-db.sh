#!/usr/bin/env bash
# Daily backup of the fleet database (litellm_fleet) to the S3 backup prefix.
#
# litellm-fleet-backup.service runs this as root once a day. Root is the only
# user that reaches the instance metadata service, so only root gets the
# instance profile's s3:PutObject on the backup prefix.
#
# Needs FLEET_BACKUP_S3_URI (s3://<bucket>/<prefix>) from
# /etc/litellm-fleet/backup.env, which render-env.sh writes.
set -euo pipefail

readonly DB_NAME="${FLEET_BACKUP_DB:-litellm_fleet}"

if [ "$(id -u)" -ne 0 ]; then
  echo "backup-db.sh: run as root" >&2
  exit 1
fi
case "${FLEET_BACKUP_S3_URI:-}" in
  s3://?*/?*) ;;
  *) echo "backup-db.sh: FLEET_BACKUP_S3_URI must be s3://<bucket>/<prefix>" >&2; exit 1 ;;
esac
for tool in aws pg_dump pg_restore runuser; do
  command -v "$tool" >/dev/null 2>&1 || { echo "backup-db.sh: $tool not found" >&2; exit 1; }
done

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${FLEET_BACKUP_S3_URI%/}/${DB_NAME}-${stamp}.dump"

region_args=()
if [ -n "${AWS_REGION:-}" ]; then
  region_args=(--region "$AWS_REGION")
fi

umask 077
workdir="$(mktemp -d "${TMPDIR:-/var/tmp}/litellm-fleet-backup.XXXXXX")"
trap 'rm -rf "$workdir"' EXIT
dump="$workdir/${DB_NAME}-${stamp}.dump"

# pg_dump runs as postgres (peer auth on the local socket). The dump goes to
# a root-only temporary file first, so a failed dump never reaches S3.
runuser -u postgres -- pg_dump --format=custom "$DB_NAME" > "$dump"
# Refuse an unreadable or empty archive.
pg_restore --list "$dump" > /dev/null
aws s3 cp "${region_args[@]}" "$dump" "$target" --sse AES256 --only-show-errors

echo "backup-db.sh: uploaded ${DB_NAME} dump ($(wc -c < "$dump") bytes) to ${target}"
