#!/usr/bin/env sh
set -eu

[ -f .env ] || { echo "missing .env" >&2; exit 1; }

set -a
# shellcheck disable=SC1091
. ./.env
set +a

fail() { echo "preflight: $*" >&2; exit 1; }

[ "${APP_ENV:-}" = "production" ] || fail "APP_ENV must be production"
[ "${#SECRET_KEY}" -ge 32 ] || fail "SECRET_KEY must be at least 32 characters"
[ "${#WEBHOOK_SIGNING_SECRET}" -ge 32 ] || fail "WEBHOOK_SIGNING_SECRET must be at least 32 characters"
case "${PUBLIC_APP_URL:-}" in
  https://*) ;;
  *) fail "PUBLIC_APP_URL must use https://" ;;
esac
case ",${CORS_ORIGINS:-}," in
  *,*,) ;;
esac
[ "${CORS_ORIGINS:-}" != "*" ] || fail "wildcard CORS is forbidden"
[ -n "${POSTGRES_PASSWORD:-}" ] || fail "POSTGRES_PASSWORD is required"
[ "${POSTGRES_PASSWORD:-}" != "threshold_dev_password" ] || fail "development database password is forbidden"

docker compose -f docker-compose.prod.yml config --quiet

echo "production preflight passed"
