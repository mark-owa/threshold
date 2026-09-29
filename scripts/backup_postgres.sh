#!/usr/bin/env sh
set -eu

: "${POSTGRES_USER:=threshold}"
: "${POSTGRES_DB:=threshold}"
: "${BACKUP_DIR:=./backups}"

mkdir -p "$BACKUP_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="$BACKUP_DIR/threshold-$ts.dump"

# Run from the host against the compose Postgres service. Custom format allows
# pg_restore --list verification before any destructive restore operation.
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$out"

[ -s "$out" ] || { echo "backup is empty" >&2; exit 1; }
echo "$out"
