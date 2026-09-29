#!/usr/bin/env sh
set -eu

backup="${1:?usage: restore_drill.sh path/to/backup.dump}"
: "${POSTGRES_USER:=threshold}"
: "${RESTORE_DB:=threshold_restore_drill}"

[ -s "$backup" ] || { echo "backup missing or empty" >&2; exit 1; }

cleanup() {
  docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${RESTORE_DB}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
  docker compose -f docker-compose.prod.yml exec -T postgres \
    dropdb -U "$POSTGRES_USER" --if-exists "$RESTORE_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

cleanup

docker compose -f docker-compose.prod.yml exec -T postgres \
  createdb -U "$POSTGRES_USER" "$RESTORE_DB"

docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d "$RESTORE_DB" --no-owner --no-privileges < "$backup"

docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$RESTORE_DB" -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) AS migration_rows FROM alembic_version;" \
  -c "SELECT count(*) AS organizations FROM organizations;" \
  -c "SELECT count(*) AS outbox_messages FROM outbox_messages;" >/dev/null

echo "restore drill passed: $backup"
