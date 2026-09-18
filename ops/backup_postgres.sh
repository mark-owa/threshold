#!/usr/bin/env sh
set -eu

: "${BACKUP_DIR:=./backups}"
mkdir -p "$BACKUP_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="$BACKUP_DIR/threshold-$ts.dump"

DB_URL="${DATABASE_PUBLIC_URL:-${DATABASE_URL:-}}"
if [ -n "$DB_URL" ]; then
  command -v pg_dump >/dev/null 2>&1 || {
    echo "pg_dump is required when DATABASE_URL/DATABASE_PUBLIC_URL is set" >&2
    exit 127
  }
  DB_URL="$(printf '%s' "$DB_URL" | sed 's#^postgresql+psycopg://#postgresql://#')"
  pg_dump "$DB_URL" --format=custom --no-owner --file="$out"
else
  : "${POSTGRES_USER:=threshold}"
  : "${POSTGRES_DB:=threshold}"
  command -v docker >/dev/null 2>&1 || {
    echo "Set DATABASE_URL/DATABASE_PUBLIC_URL or install Docker for compose mode" >&2
    exit 127
  }
  docker compose -f docker-compose.prod.yml exec -T postgres     pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$out"
fi

[ -s "$out" ] || { echo "backup is empty" >&2; exit 1; }
echo "$out"
