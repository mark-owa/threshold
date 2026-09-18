#!/usr/bin/env sh
set -eu

backup="${1:?usage: restore_drill.sh path/to/backup.dump}"
: "${RESTORE_DB:=threshold_restore_drill}"
[ -s "$backup" ] || { echo "backup missing or empty" >&2; exit 1; }

case "$RESTORE_DB" in
  *[!A-Za-z0-9_]*|'') echo "RESTORE_DB must contain only letters, numbers, and underscores" >&2; exit 64 ;;
esac

DB_URL="${DATABASE_PUBLIC_URL:-${DATABASE_URL:-}}"
if [ -n "$DB_URL" ]; then
  for bin in psql pg_restore python3; do
    command -v "$bin" >/dev/null 2>&1 || { echo "$bin is required for remote restore drill" >&2; exit 127; }
  done
  DB_URL="$(printf '%s' "$DB_URL" | sed 's#^postgresql+psycopg://#postgresql://#')"

  db_url_for() {
    python3 - "$DB_URL" "$1" <<'PY'
import sys
from urllib.parse import quote, urlsplit, urlunsplit
url, db = sys.argv[1], sys.argv[2]
p = urlsplit(url)
print(urlunsplit((p.scheme, p.netloc, "/" + quote(db, safe=""), p.query, p.fragment)))
PY
  }

  ADMIN_URL="$(db_url_for postgres)"
  RESTORE_URL="$(db_url_for "$RESTORE_DB")"

  cleanup_remote() {
    psql "$ADMIN_URL" -v ON_ERROR_STOP=1       -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${RESTORE_DB}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
    psql "$ADMIN_URL" -v ON_ERROR_STOP=1       -c "DROP DATABASE IF EXISTS \"${RESTORE_DB}\";" >/dev/null 2>&1 || true
  }
  trap cleanup_remote EXIT INT TERM
  cleanup_remote

  psql "$ADMIN_URL" -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"${RESTORE_DB}\";" >/dev/null
  pg_restore --dbname="$RESTORE_URL" --no-owner --no-privileges --exit-on-error "$backup"
  psql "$RESTORE_URL" -v ON_ERROR_STOP=1     -c "SELECT count(*) AS migration_rows FROM alembic_version;"     -c "SELECT count(*) AS organizations FROM organizations;"     -c "SELECT count(*) AS outbox_messages FROM outbox_messages;" >/dev/null
else
  : "${POSTGRES_USER:=threshold}"
  command -v docker >/dev/null 2>&1 || {
    echo "Set DATABASE_URL/DATABASE_PUBLIC_URL or install Docker for compose mode" >&2
    exit 127
  }

  cleanup_compose() {
    docker compose -f docker-compose.prod.yml exec -T postgres       psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1       -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${RESTORE_DB}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
    docker compose -f docker-compose.prod.yml exec -T postgres       dropdb -U "$POSTGRES_USER" --if-exists "$RESTORE_DB" >/dev/null 2>&1 || true
  }
  trap cleanup_compose EXIT INT TERM
  cleanup_compose

  docker compose -f docker-compose.prod.yml exec -T postgres createdb -U "$POSTGRES_USER" "$RESTORE_DB"
  docker compose -f docker-compose.prod.yml exec -T postgres     pg_restore -U "$POSTGRES_USER" -d "$RESTORE_DB" --no-owner --no-privileges < "$backup"
  docker compose -f docker-compose.prod.yml exec -T postgres     psql -U "$POSTGRES_USER" -d "$RESTORE_DB" -v ON_ERROR_STOP=1     -c "SELECT count(*) AS migration_rows FROM alembic_version;"     -c "SELECT count(*) AS organizations FROM organizations;"     -c "SELECT count(*) AS outbox_messages FROM outbox_messages;" >/dev/null
fi

echo "restore drill passed: $backup"
