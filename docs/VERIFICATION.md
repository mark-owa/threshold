# Verification evidence

Evidence reviewed on **2026-10-01** against source commit
[`99d6d03`](https://github.com/mark-owa/threshold/commit/99d6d033e41c66722172e59da59bb83d1d2d379c).
Results below describe particular commits and environments.

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
The frontend job runs Vite; it does not run a TypeScript type-check or browser test.
The deployment job validates Compose syntax; it does not start the production stack.
The current workflow has no M8 image-build job.

## Recorded demo

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
The capture workflow also generates an MP4 artifact, but a permanent full-video
link is not committed. Artifact availability is time-limited.

These captures establish the recorded mock flows. They do not establish scheduled
retry delivery, worker restart recovery, or live payments.

## Historical reports

[History](HISTORY.md) summarizes the original PGlite review, deterministic fixture
checks, and later static frontend checks. Historical test counts and stub-based
type checks are not current runtime guarantees.

[Staging milestones](STAGING_MILESTONES.md) retain September deployment and
interruption-drill reports. They refer to a separate M8 runtime archive and build
overlays. Service health, credentials, and those drills were not rerun during this
documentation review; historical reports must not be treated as current live status.

## Remaining verification

| Area | What remains |
| --- | --- |
| Dependency audit | Resolve reported PyJWT findings and obtain a new passing audit. |
| Current UI | Capture the current dashboard and exercise registration, approvals, retry, and workspace views in a browser. |
| Type safety | Install the real React types and add a TypeScript type-check gate. |
| M8 packaging | Build the separate M8 image in CI and compare its patched runtime with canonical source. |
| Durable delivery | Exercise persisted intake, outbox publication, worker interruptions, duplicate delivery, and dead-letter recovery together. |
| Ambiguous provider outcomes | Prove timeout-after-provider-commit, reconciliation, and safe continuation against a test provider. |
| External accounts | Validate Shopify development-store, Stripe test-mode, and credential-vault lifecycles. |
| Operations | Complete an isolated backup/restore drill, tested alert delivery, and incident ownership. |

Use [TESTING](TESTING.md) for local commands and [DEMO](DEMO.md) for the walkthrough.
Record new results with a date, source commit, environment, and accessible evidence.
