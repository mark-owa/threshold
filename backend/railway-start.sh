#!/usr/bin/env bash
set -euo pipefail

case "${RAILWAY_SERVICE_NAME:-threshold-api}" in
  threshold-worker)
    exec celery -A app.workers.celery_app worker --loglevel=info
    ;;
  threshold-beat)
    exec celery -A app.workers.celery_app beat --loglevel=info --schedule /tmp/celerybeat-schedule
    ;;
  *)
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
esac
