#!/usr/bin/env sh
set -eu

backup="${1:?usage: verify_postgres_backup.sh path/to/backup.dump}"
[ -s "$backup" ] || { echo "backup missing or empty" >&2; exit 1; }

if command -v pg_restore >/dev/null 2>&1; then
  pg_restore --list "$backup" >/dev/null
elif command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.prod.yml exec -T postgres     pg_restore --list < "$backup" >/dev/null
else
  echo "pg_restore (or Docker compose) is required to verify the backup" >&2
  exit 127
fi

echo "backup catalog verified: $backup"
