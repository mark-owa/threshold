# Threshold M8 — Staging Handoff

This branch is reserved for staging/private-beta validation. Do not enable live customer execution until the M8 readiness gate reports zero blockers and the manual go/no-go review is complete.

## Target topology

- Frontend: Vercel preview/staging
- API: Railway persistent service
- Worker: Railway persistent service
- Beat: Railway persistent service
- Database: Railway PostgreSQL
- Queue/cache: Railway Redis

Only the API receives a public Railway domain. Postgres, Redis, Worker, and Beat stay private.

## Railway services

All three application services should use the repository `mark-owa/threshold` with root directory `/backend`.

### API

Pre-deploy command:

```bash
alembic upgrade head
```

Start command when Railway builds from the Dockerfile:

```bash
/bin/sh -c 'exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'
```

Health check:

```text
/health/ready
```

Generate a public domain for the API only.

### Worker

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

No public domain.

### Beat

```bash
celery -A app.workers.celery_app beat --loglevel=info --schedule /tmp/celerybeat-schedule
```

No public domain.

## Shared environment variables

Use Railway reference variables for database and Redis values. Never paste secrets into source files.

```text
APP_ENV=staging
DATABASE_URL=postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
AI_PROVIDER=mock
BETA_ALLOW_MOCK_AI=true
JWT_ISSUER=threshold
JWT_AUDIENCE=threshold-api
TRUST_PROXY_HEADERS=true
```

Set `PUBLIC_APP_URL` and `CORS_ORIGINS` to the staging frontend HTTPS URL once it is known.

Generate separate strong values for:

```text
SECRET_KEY
WEBHOOK_SIGNING_SECRET
```

Do not send those values through chat, commit them to GitHub, or include them in screenshots.

## Keep these disabled/unset initially

Do not connect real-money or merchant credentials during the first infrastructure boot:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
SHOPIFY_CLIENT_ID
SHOPIFY_CLIENT_SECRET
BILLING_STRIPE_SECRET_REF
BILLING_STRIPE_WEBHOOK_SECRET_REF
OAUTH_SECRET_SINK_URL
```

`live_execution_enabled` must remain false.

## First staging proof

After API, Worker, Beat, PostgreSQL and Redis are healthy:

1. `GET /health/live` returns 200.
2. `GET /health/ready` reports Postgres and Redis healthy.
3. Alembic is at head.
4. Celery worker responds to inspection/ping.
5. Run the complete pytest suite.
6. Run the staging smoke script.
7. Run the M8 beta-readiness gate.
8. Record all remaining blockers rather than enabling live execution.

## Second staging proof

Only after the base runtime passes:

1. Connect a Shopify development store.
2. Connect Stripe test mode.
3. Configure a real secret vault/token sink.
4. Deliver a signed Shopify webhook.
5. Execute a Stripe test refund.
6. Force an ambiguous provider outcome and reconcile it.
7. Kill a worker during an action and prove stale-lease recovery.
8. Perform a PostgreSQL backup/restore drill.
9. Trigger and verify an operational alert.
10. Run the readiness gate again.

Private beta remains NO-GO until blocker count is zero and a human owner explicitly enables live execution.
