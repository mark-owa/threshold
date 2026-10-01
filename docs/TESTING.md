# Testing

## Database-free primitives

With Python 3.12+ and `backend/requirements-dev.txt` installed in a virtual environment:

```bash
make unit-test
```

This checks normalization, deterministic classification/extraction, retry delays,
and other dependency-light helpers. It does not run the complete API/workflow suite.

## API and workflow regression suite

Start the local demo with a disposable PostgreSQL database, then run:

```bash
make migrate
make test
make lint
make eval
```

The suite creates a dedicated `threshold_test` database on the configured server.
Local Compose builds `backend/Dockerfile.dev`, which includes test/lint tools.
Use a development/test account with permission to create it. Fixtures isolate tests
with transactions, including routes that call `commit()`.

CI separately applies migrations and runs tests against PostgreSQL 16 with Redis 7.
The workflow enforces a 70% coverage floor and runs dependency audits.
Test coverage includes tenant/role checks, workflow and approval behavior,
duplicate handling, retry/recovery logic, and mocked provider contracts.
Direct task-function tests do not prove Celery transport or crash recovery.

## Frontend

```bash
make frontend-build
```

This runs `npm ci` and `npm run build`: `tsc --noEmit` with the real React types,
then Vite. It does not exercise browser interactions. See
[frontend/README](../frontend/README.md).

Run `node scripts/check_n8n_templates.cjs` for template structure/JavaScript checks.
`pytest -q tests/unit tests/test_n8n_http_delivery.py` from `backend/` checks helpers
and real loopback HTTP delivery without PostgreSQL. `tests/test_n8n_bridge.py` needs
PostgreSQL and covers intake signatures, tenant binding, conflicting events, and
final outcome persistence.

## AI evaluation

`make eval` runs the small deterministic fixture datasets.
`make eval-live` is opt-in and requires provider credentials and a compatible model.
Mock fixture results do not establish live-model accuracy or prompt-injection resistance.

## Deployment and demo checks

The current CI deployment job validates production Compose syntax.
It does not start the production stack or build `deploy/m8/Dockerfile`.
The [capture tooling](../tooling/capture/README.md) starts a disposable demo and
checks sign-in, session reload, automatic refund, human approval, and manual retry
through the current browser UI. It publishes media only after its API assertions
pass. Worker and Beat are absent. Follow [DEMO](DEMO.md) for the walkthrough.

[VERIFICATION](VERIFICATION.md) links dated results, including the PyJWT 2.15.1
upgrade, passing dependency audit, and 177-test PostgreSQL run. [HISTORY](HISTORY.md) retains the scope of earlier local checks.
