# Threshold

Threshold is a local business-operations simulation with a FastAPI backend and a
React dashboard. Its reference workflow takes a refund request, extracts an order
and amount, checks deterministic policy, and either records a mock refund or pauses
for human review. No real money moves and no email is sent.

## The business problem

A refund request involves more than extracting a number from a message. An operator
must check the order, apply policy, decide when review is required, and understand
what happened if processing fails. Threshold makes those decisions and outcomes
inspectable in one local demonstration.

The reference case is a fictional retail operation. It demonstrates an approach to
controlled automation; it is not a customer deployment or evidence of measured savings.

![Architecture overview: dashboard, API and workflow engine, PostgreSQL, and optional queued workers](docs/assets/architecture-overview.svg)

**Start here:** [Business case](docs/CASE_STUDY.md) ·
[Three-minute demo guide](docs/DEMO.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Verification evidence](docs/VERIFICATION.md)

The demo guide uses the actual dashboard. Screenshots and a recorded walkthrough
are not yet included; the diagram above is an architecture illustration.

## What it demonstrates

- Ordered workflow steps with persisted inputs, outputs, timing, and failures.
- A narrow AI boundary: classification and structured extraction, with a deterministic
  mock provider by default. OpenAI and Anthropic adapters are optional.
- Refund eligibility and amount thresholds kept in ordinary Python and policy data.
- Authenticated, tenant-scoped inspection and reviewer-only approval/retry actions.
- Event deduplication, canonical refund keys, scheduled retries, a simple circuit
  breaker, and dead-letter records.
- PostgreSQL migrations, regression tests, structured request logs, and a small
  labeled evaluation dataset.

Customer, lead, support, and invoice inquiries use smaller classify-and-notify
workflows. Notifications are local database records; those flows do not implement
CRM updates, lead qualification, or a helpdesk integration.

## Run locally

Requires Docker with Compose and Make. From the extracted repository root:

```bash
cp .env.example .env
make up
make migrate
make seed
```

Open the dashboard at **http://localhost:5173** and sign in with:

- `owner@acme-demo.example.com` / `demo1234`
- `reviewer@acme-demo.example.com` / `demo1234`

Use a fresh disposable demo database; legacy demo logins/refund keys are not data-migrated.

These are public demo credentials for local use. API documentation is at
http://localhost:8000/docs. `/health` checks the API process; `/ready` checks the
database connection. `make seed-history` adds examples across all five categories.

Try **Low-risk refund**, **High-risk refund**, and **Failure + retry**. A
**Policy-failing refund** enters the approval queue; use Reject to demonstrate
cancellation. A reviewer may override the automatic policy gate, but the action
still requires an existing order and a positive amount no greater than its total.
Missing amounts require review and modification; they are never inferred as zero.

Failure + retry creates a fresh mock order so an earlier successful refund cannot
hide the simulated timeout. It records a failed workflow and a scheduled action;
use Retry for immediate recovery or let Celery Beat check due actions each minute.
Repeated ordinary demos reuse an existing successful refund for the same order and
amount, while retaining a separate event/execution record.

### API example

Log in first and copy the returned `access_token` into `TOKEN`:

```bash
curl -s http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@acme-demo.example.com","password":"demo1234"}'

TOKEN='<returned access_token>'
curl -s http://localhost:8000/api/v1/demo/orgs/acme-demo/events \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"idempotency_key":"example-001","payload":{"text":"Refund order #ORD-1002 for $65.00"}}'
```

## Verify

```bash
make test             # PostgreSQL-backed API and workflow tests
make lint             # existing Ruff checks
make eval             # deterministic classification/extraction evaluation
make frontend-build   # requires local Node.js 22.12+ and npm
```

For just the primitive tests without Docker, use Python 3.12+:

```bash
python -m venv .venv
# Activate .venv using your shell's activation command.
python -m pip install -r backend/requirements-dev.txt
make unit-test
```

See [TESTING](docs/TESTING.md) for test isolation and verification boundaries.
See [VERIFICATION](docs/VERIFICATION.md) for the distinction between the bundled
review's reported results and checks repeated during this documentation pass.
The backend image includes development tools because this Compose setup is a local
portfolio/demo environment. `make down` stops containers; PostgreSQL data remains
in its named volume.

### Windows / PowerShell without Make

With Docker Desktop running and Docker Compose available, open PowerShell in this
repository's root and use the equivalent commands:

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_demo_org
```

Copy the example only on first setup; preserve an existing `.env`. The same dashboard
URL and demo logins above apply. For checks, run
`docker compose exec backend pytest -v --cov=app --cov-report=term-missing`
and `docker compose exec backend python -m scripts.evaluate_ai`.

## Repository map

| Path | Purpose |
|---|---|
| `backend/app/api/` | Login, operations, decisions, and demo routes |
| `backend/app/workflows/` | Existing workflow engine and deterministic primitives |
| `backend/app/ai/` | Provider adapters and prompt resolution |
| `backend/app/models/` | SQLAlchemy models |
| `backend/app/workers/` | Celery ingestion and retry tasks |
| `backend/alembic/` | Database migrations |
| `backend/scripts/`, `backend/evals/` | Demo fixtures and evaluation data |
| `backend/tests/` | Unit and API/workflow regression tests |
| `frontend/` | Single-component operator dashboard |
| `docs/` | Architecture, API, decisions, and limitations |

## Scope and limitations

This is a portfolio prototype, not a production payment or automation service.

- Actions and notifications are mocks. Refund keys deduplicate an order/amount pair;
  this is not a payment ledger and does not track cumulative partial refunds.
- Approval resume and action retry target the reference refund workflow. They are
  not a generic continuation engine for arbitrary workflow definitions.
- No signed webhook receiver, API-key issuance, refresh-token flow, rate limiting,
  automatic approval expiry, or immutable audit storage is implemented.
- Ingestion is serialized per organization for simple duplicate handling. High-load
  concurrency and crash-safe delivery to external systems are not established.
- Redis queue persistence and crash recovery are not guaranteed by the demo Compose
  configuration. Requests lost before database processing need resubmission.
- Live model calls need credentials and a provider-compatible model configuration.
  Small mock evaluations do not establish accuracy on real customer requests.
- The dashboard uses in-memory sessions and selects the first organization. Hours
  saved assume 15 minutes per automatically completed workflow; they are illustrative.

[Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) ·
[Reliability](docs/RELIABILITY.md) · [Security](docs/SECURITY.md)

## Related freelance work

This project is relevant to scoped Python backend work: validating incoming records,
connecting an internal dashboard to an API, implementing approval steps, and debugging
duplicate processing or failed automation. Its provider boundary also illustrates
how structured extraction can feed deterministic rules.

A real payment, CRM, or email integration would be a separate implementation with
its own authentication, delivery, and verification requirements.

Need help with a similar internal process? In your enquiry, include the current
workflow, a redacted sample input, the expected result, and what should require
human approval.

MIT license; see [LICENSE](LICENSE).
