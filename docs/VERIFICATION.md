# Verification evidence

Updated on **2026-10-01** against canonical source and dated CI/capture evidence.
Results below describe particular commits and environments.

## Source import checks

Repeated locally using Python 3.12 and the pinned development dependencies:

| Check | Result | Scope |
| --- | --- | --- |
| `ruff check .` | Passed | Full backend, including retained regression files. |
| `mypy app` | Passed | 52 application source files. |
| Unit and loopback HTTP tests | 68 passed | `tests/unit` and `test_n8n_http_delivery.py`; no database or installed n8n runtime. |
| `npm run build` | Passed | Real React types, `tsc --noEmit`, then Vite; no browser interactions. |
| `npm audit --audit-level=high` | Passed | No reported frontend findings at import time. |
| n8n template harness | 16 passed | Workflow structure/JavaScript, signatures and acknowledgment guards. |
| Deterministic evaluation | 12/12, 8/8, 5/5 | Mock classification, adversarial wording, and extraction fixtures. |
| Alembic revision graph | One head: `e8b0c234f6a8` | Retains the existing billing timestamp defaults migration. |
| Python dependency audit | Failed | 13 findings in unchanged PyJWT 2.13.0. |

PostgreSQL and Docker are unavailable locally. The candidate
[GitHub Actions run at `98bfeee`](https://github.com/mark-owa/threshold/actions/runs/36803688853)
applied all nine migrations on PostgreSQL 16 and passed **162 tests**, with
**72.29% statement coverage** (70% required). That includes the bridge persistence
tests and retained workflow, provider, billing, and security regressions. Backend
lint/type checks, frontend audit/type/build/template checks, and production Compose
syntax validation passed. The Python audit failed on the same 13 PyJWT findings;
the following AI evaluation step was skipped. Evaluation was repeated locally.

The subsequent documentation changes do not alter that tested application source.
The import tests do not prove live n8n/HubSpot delivery. The separate browser capture below verifies the stated mock flows.

## Hosted CI

| Evidence | Result | Scope |
| --- | --- | --- |
| [2026-09-29, `12bf94a`](https://github.com/mark-owa/threshold/actions/runs/36611807246) | Passed | Backend lint, migrations, compilation, PostgreSQL-backed tests with a 70% coverage floor, Python audit, deterministic evaluation, frontend audit/build, and production Compose syntax. |
| [2026-10-01, `99d6d03`](https://github.com/mark-owa/threshold/actions/runs/36797036742) | Failed | Backend lint, migrations, compilation, and tests passed. Frontend install/audit/build and Compose syntax passed. Python dependency audit failed; the later AI evaluation step was skipped. |

The October 1 audit reported **13 known vulnerabilities in PyJWT 2.13.0**.
Its output lists fixes for some findings and no fix version for one finding.
Dependency remediation requires a separate change and a new audit; no finding is
suppressed by this documentation update.

The workflow uses Python 3.12, PostgreSQL 16, Redis 7, and Node 22.
It runs the API/workflow test suite with native PostgreSQL services, rather than
PGlite. This supersedes earlier statements that no hosted CI or native PostgreSQL
test evidence existed.

Tests exercise task functions and mocked provider behavior. A passing job does not
prove real Celery broker delivery, live API credentials, or production payment safety.
The earlier frontend jobs ran Vite without a TypeScript check. The imported
workflow now checks TypeScript before Vite and also runs the n8n template harness.
The regular CI workflow does not run browser interaction tests. The separate capture workflow verifies the stated mock UI flows.
The deployment job validates Compose syntax; it does not start the production stack.
The current workflow has no M8 image-build job.

## Current dashboard capture

The [successful capture run](https://github.com/mark-owa/threshold/actions/runs/36811368664) recorded canonical source `94cca1901628ee219359872ed28df0799ffebbf4` on
**2026-10-01**, using a fresh Docker Compose database and production React build.
Chromium signed in as the seeded reviewer, restored the session after reload,
completed a $65 mock refund, approved the $89.99 request, and manually recovered
a simulated timeout. API assertions verified final state, retained failed steps,
and the same action ID in failure/recovery audit events. No browser or API errors
were recorded.

Four screenshots and an approval GIF are under `docs/assets/current-demo/`.
[JSON evidence](assets/current-demo/capture-evidence.json) records the source,
environment, run URL, execution IDs, approval ID, and action/audit IDs.
Worker and Beat were absent. These checks do not establish broker transport,
worker crash recovery, live provider safety, or a real n8n/HubSpot round trip.

## Historical September demo

The [capture run](https://github.com/mark-owa/threshold/actions/runs/35411976554)
completed successfully on **2026-09-19**, at source commit
`6f0f36a5db6d4f7b8c83f0bf67d1e7e7a967db87`.

The committed [capture evidence](assets/demo/capture-evidence.json) identifies:

- Docker Compose with PostgreSQL, Redis, FastAPI, nginx, and the production React build;
- the mock provider and manual recovery, with Worker and Beat not running;
- an automatic refund, approval pause and completion, and reuse of the same action
  during failure/retry recovery;
- the checked execution, approval, and action identifiers.

Four screenshots and an approval GIF are committed under `docs/assets/demo/`.
They show that recorded version, not every view in the later dashboard.
The historical capture workflow also generated an MP4 artifact, but a permanent full-video
link is not committed. Artifact availability is time-limited.

These captures establish the recorded mock flows. They do not establish scheduled
retry delivery, worker restart recovery, or live payments.

## Historical reports

[History](HISTORY.md) summarizes the original PGlite review, deterministic fixture
checks, and later static frontend checks. Historical test counts and stub-based
type checks are not current runtime guarantees.

[Staging milestones](history/STAGING_MILESTONES.md) retain September deployment and
interruption-drill reports. They refer to a separate M8 runtime archive and build
overlays. Service health, credentials, and those drills were not rerun during this
documentation review; historical reports must not be treated as current live status.

## Remaining verification

| Area | What remains |
| --- | --- |
| Dependency audit | Resolve reported PyJWT findings and obtain a new passing audit. |
| Broader UI coverage | Exercise registration, workspace switching, roles, expiry, and action forms beyond the captured mock flows. |
| Browser behavior | Exercise routed navigation, session expiry, tenant changes, and action forms. |
| M8 packaging | Build the separate M8 image in CI and compare its patched runtime with canonical source. |
| Durable delivery | Exercise persisted intake, outbox publication, worker interruptions, duplicate delivery, and dead-letter recovery together. |
| Ambiguous provider outcomes | Prove timeout-after-provider-commit, reconciliation, and safe continuation against a test provider. |
| External accounts | Validate Shopify development-store, Stripe test-mode, and credential-vault lifecycles. |
| Operations | Complete an isolated backup/restore drill, tested alert delivery, and incident ownership. |

Use [TESTING](TESTING.md) for local commands and [DEMO](DEMO.md) for the walkthrough.
Record new results with a date, source commit, environment, and accessible evidence.
