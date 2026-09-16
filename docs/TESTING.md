# Verification

## Fast primitives

With Python 3.12+ and `backend/requirements-dev.txt` installed:

```bash
make unit-test
```

Checks normalization, keyword classification, conservative money extraction, and
bounded retry delay. No database or Redis service is needed for this command.

## Full API/workflow suite

```bash
make up
make migrate
make test
make lint
make eval
```

The suite creates a dedicated `threshold_test` database on the configured server.
Use only a development/test database account with permission to create that database.
Tests use an outer transaction per case, including routes that call `commit()`.
CI separately applies migrations before testing against PostgreSQL 16 and Redis 7.

Regression coverage exercises automatic refunds, missing/invalid amounts, approval
and modification/rejection, duplicate events/actions, tenant/reviewer checks,
scheduled retry task logic, dead-letter limits, disabled integrations, and circuit
state. Task-function tests do not establish broker delivery reliability.

## Frontend and AI

`make frontend-build` runs a locked npm install and Vite production build. A build
is not a browser interaction test or TypeScript type-check gate.

`make eval` runs the small deterministic datasets. `make eval-live` is opt-in and
needs provider credentials and a compatible model. Mock accuracy does not establish
live-model accuracy, prompt-injection resistance, or production readiness.

See `REVIEW.md` at the repository root for the checks actually performed during
this review, including environment-specific verification limits.

See [VERIFICATION](VERIFICATION.md) for the separate evidence ledger added during
the portfolio documentation pass. Its deterministic fixture checks are not a
replacement for this PostgreSQL-backed pytest suite or a browser walkthrough.
