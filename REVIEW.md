# Portfolio review

## Verdict: READY WITH MINOR LIMITATIONS

Ready to present as a local, mocked operations-workflow portfolio prototype.
The existing architecture and project scope are preserved. This verdict does not
claim production readiness, real payment processing, or verified broker durability.

## Fixed

- Clean startup: installed the validation extra required by `EmailStr`; replaced
  reserved `.test` demo login addresses with valid example-domain addresses.
- Docker verification commands: included the development dependencies required by
  the existing test/lint targets. Pinned the installed frontend versions and added
  an npm lockfile; aligned the container/CI Node major version with Vite requirements.
- Refund safety: missing amounts cannot auto-execute; action parameters must name
  an existing tenant order and a positive, finite amount in cents within its total.
  Modified approvals pass the same action validation. Monetary extraction handles
  grouped thousands and negative signs without silently truncating invalid tokens.
- Duplicate effects: canonical decimal refund keys avoid treating `65` and `65.0`
  as different amounts; ingestion serializes duplicate submissions per organization.
- Approval handling: rejected workflows receive a completion timestamp; hidden
  modifications on ordinary approvals are rejected; the compatibility endpoint
  reuses the canonical decision handler. Reused actions keep their original link.
- Recovery: preserve the demo failure flag and failed workflow context, schedule
  initial failures for the existing retry task, honor manual retry force, and clear
  stale retry/error state on success. Disabled integrations are respected and
  successful retries reset circuit state. Exhausted actions clear their schedules.
- Demo reliability: the failure scenario gets an independent mock order, preventing
  an earlier successful ordinary refund from swallowing the intended failure.
- Observability: step ordering uses start timestamps, audit rows use event-time
  timestamps, ingestion stores request correlation, and demo events no longer claim
  a verified webhook signature. Automation metrics exclude human-reviewed completions.
- Boundary/configuration failures: reject unsupported event sources/provider names,
  handle bcrypt overlength inputs, preserve database URL escapes/options, avoid
  exposing database exceptions in readiness responses, and support a model override
  for the existing live-provider adapters.
- Seed scripts: use a valid event source and tolerate prompts seeded before the org.
- Dashboard: handle request failures, recover from expired sessions during refresh,
  correct scenario/estimate labels, and improve crowded labels on narrow screens.

## Cleaned

Removed the obsolete `engine.txt` copy, empty migration README, unused imports,
dead seed helpers, and vacuous method-existence assertions. Shared deterministic
mock classification/extraction and retry-delay logic replace duplicate copies.
Applied the existing Ruff conventions without splitting the workflow engine.

Rewrote inaccurate/speculative documentation, repaired the authenticated quickstart,
corrected nginx documentation routing, and tightened ignore rules for local
configuration, databases, Celery schedule files, caches, and generated frontend files.
The archive excludes bytecode, caches, dependencies, builds, logs, and test data.
The secrets review found demo placeholders and fictional fixtures, not live keys.

## Verified

| Check | Result |
|---|---|
| Python test suite | 53 passed; 88% statement coverage |
| Ruff lint / format | Passed |
| Installed Python dependency consistency | Passed (`pip check`) |
| Alembic upgrade, downgrade to base, re-upgrade | Passed |
| Model/schema comparison | No pending migration operations |
| Seeding | Prompt-first, repeat org seed, and operational history passed |
| Deterministic evaluation | 12/12 base, 8/8 adversarial wording, 5/5 extraction |
| Frontend | Locked npm install and Vite production build passed |
| Browser | Login, all six scenarios, approval/rejection, manual retry, desktop/mobile layout, and network-failure handling checked |
| Archive/doc audit | Source syntax, JSON, local Markdown links, and generated-file exclusions checked |

The database checks used **PGlite's WebAssembly PostgreSQL engine through its socket
server**, with Python 3.12 and the actual FastAPI/SQLAlchemy application. It supports
the types and SQL needed by these tests, but is not a native PostgreSQL 16 service
and does not establish native concurrency semantics. Its database handling differs;
tests were run on a clean instance before adding operational demo history.

The browser checks used local Chromium, the actual API, and the Vite development
server at desktop and 390-pixel mobile widths. The Docker/nginx image itself was
not run. Node 24 was available for local builds; the configured Node 22 container/CI
runtime was not executed here. Two upstream test-client deprecation warnings remain.

## Intentionally left unchanged

- Synchronous SQLAlchemy, PostgreSQL schema, Celery setup, and the existing runner.
- Refund-specific approval/retry continuations, rather than a general workflow engine.
- Single-component React dashboard and its existing layout and local state.
- Mock effects and unused schema fields reserved by the original project.
- Simple rule-based classification and the small evaluation datasets.

No new application framework, integration, business feature, or service was added.
Temporary review tooling is not included as an application dependency.

## Remaining limitations

- Native Docker/PostgreSQL/Redis/Celery broker transport and crash recovery were not
  exercised. Retry-task logic was invoked directly in tests. Concurrent delivery
  guarantees still need native testing before any operational deployment.
- Live AI APIs were not called. Select a provider-compatible model and supply your
  own credentials if evaluating them. The dataset is too small to support broad
  accuracy or security claims.
- Refund idempotency covers an order/amount pair; there is no cumulative partial
  refund ledger or customer-ownership verification. All payment effects are mocks.
- Approval resume is specific to the reference refund sequence. Failure before an
  action exists has no action to retry. Database outages can prevent failure/audit
  records from being persisted. There is no general replay or recovery mechanism.
- API-key management, signed webhooks, refresh tokens, rate limits, approval expiry,
  and immutable audit storage remain unimplemented and are documented accordingly.
- Frontend sessions remain in memory; it selects the first organization. Vite builds
  do not constitute a TypeScript type-check gate. Savings and AI costs are estimates.
- Use a fresh disposable demo database for this reviewed archive. Legacy seeded
  `.test` logins and pre-review refund-key strings are not data-migrated by Alembic.
