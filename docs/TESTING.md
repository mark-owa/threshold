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
docker compose exec --user root backend python -m pip install -r requirements-dev.txt
make migrate
make test
make lint
make eval
```

The suite creates a dedicated `threshold_test` database on the configured server.
The first command installs test/lint tools in the disposable demo container because
the default Compose file builds the runtime-only `backend/Dockerfile`.
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

This runs `npm ci` and `npm run build`. Vite builds strip types without checking
them and do not exercise browser interactions. Real React type declarations and a
type-check CI gate are still pending; see [frontend/README](../frontend/README.md).

## AI evaluation

`make eval` runs the small deterministic fixture datasets.
`make eval-live` is opt-in and requires provider credentials and a compatible model.
Mock fixture results do not establish live-model accuracy or prompt-injection resistance.

## Deployment and demo checks

The current CI deployment job validates production Compose syntax.
It does not start the production stack or build `deploy/m8/Dockerfile`.
The separate capture workflow starts a disposable demo and checks recorded mock
flows with manual retry. Follow [DEMO](DEMO.md) for the walkthrough.

[VERIFICATION](VERIFICATION.md) links actual results, including the October 1 Python
audit failure. [HISTORY](HISTORY.md) retains the scope of earlier local checks.
