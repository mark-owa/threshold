#!/usr/bin/env sh
set -eu

backup="${1:?usage: verify_postgres_backup.sh path/to/backup.dump}"
[ -s "$backup" ] || { echo "backup missing or empty" >&2; exit 1; }

docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_restore --list < "$backup" >/dev/null

echo "backup catalog verified: $backup"
