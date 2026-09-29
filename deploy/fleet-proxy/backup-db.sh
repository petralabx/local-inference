#!/usr/bin/env bash
# Daily backup of the fleet database (litellm_fleet) to the S3 backup prefix.
#
# litellm-fleet-backup.service runs this as root once a day. Root is the only
# user that reaches the instance metadata service, so only root gets the
# instance profile's s3:PutObject on the backup prefix.
#
# Needs FLEET_BACKUP_S3_URI (s3://<bucket>/<prefix>) from
# /etc/litellm-fleet/backup.env, which render-env.sh writes.
#
# Before the upload, the script restores the dump into a scratch database
# (litellm_fleet_restore_check) and compares its table count with the dump.
# A dump that does not restore never reaches S3. The instance role cannot
# read S3, so this check runs on the archive before it leaves the host.
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
for tool in aws pg_dump pg_restore runuser createdb dropdb psql; do
  command -v "$tool" >/dev/null 2>&1 || { echo "backup-db.sh: $tool not found" >&2; exit 1; }
done

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${FLEET_BACKUP_S3_URI%/}/${DB_NAME}-${stamp}.dump"

region_args=()
if [ -n "${AWS_REGION:-}" ]; then
  region_args=(--region "$AWS_REGION")
fi

readonly CHECK_DB="${DB_NAME}_restore_check"

as_postgres() {
  runuser -u postgres -- "$@"
}

cleanup() {
  as_postgres dropdb --if-exists "$CHECK_DB" >/dev/null 2>&1 || true
  rm -rf "$workdir"
}

umask 077
workdir="$(mktemp -d "${TMPDIR:-/var/tmp}/litellm-fleet-backup.XXXXXX")"
trap cleanup EXIT
dump="$workdir/${DB_NAME}-${stamp}.dump"

# pg_dump runs as postgres (peer auth on the local socket). The dump goes to
# a root-only temporary file first, so a failed dump never reaches S3.
as_postgres pg_dump --format=custom "$DB_NAME" > "$dump"
# Refuse an unreadable or empty archive.
pg_restore --list "$dump" > "$workdir/toc"
want_tables="$(grep -c ' TABLE public ' "$workdir/toc" || true)"
if [ "$want_tables" -lt 1 ]; then
  echo "backup-db.sh: the dump holds no table" >&2
  exit 1
fi

# Restore check. pg_restore reads the root-only file on stdin, so postgres
# never needs read access to the work directory.
as_postgres dropdb --if-exists "$CHECK_DB"
as_postgres createdb "$CHECK_DB"
as_postgres pg_restore --exit-on-error --no-owner --no-privileges \
  --dbname "$CHECK_DB" < "$dump"
got_tables="$(as_postgres psql -X -A -t -d "$CHECK_DB" -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")"
if [ "$got_tables" != "$want_tables" ]; then
  echo "backup-db.sh: restore check failed: $got_tables tables restored, $want_tables in the dump" >&2
  exit 1
fi
as_postgres dropdb "$CHECK_DB"

aws s3 cp "${region_args[@]}" "$dump" "$target" --sse AES256 --only-show-errors

echo "backup-db.sh: restore check passed ($got_tables tables); uploaded ${DB_NAME} dump ($(wc -c < "$dump") bytes) to ${target}"
