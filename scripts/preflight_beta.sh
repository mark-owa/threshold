#!/usr/bin/env bash
set -euo pipefail

ORG_ID="${1:-${BETA_ORG_ID:-}}"
if [[ -z "$ORG_ID" ]]; then
  echo "Usage: scripts/preflight_beta.sh <organization-uuid> (or set BETA_ORG_ID)" >&2
  exit 64
fi

./scripts/preflight_prod.sh

docker compose -f docker-compose.prod.yml exec -T backend \
  python -m scripts.beta_readiness --org-id "$ORG_ID"

echo "Private-beta preflight passed for $ORG_ID"
