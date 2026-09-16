# Verification evidence

Documentation pass: **2026-09-16**, starting from the Threshold directory in
`Four_Projects_verified_bundle(4).zip`.

## Checks repeated in this session

| Check | Result | What it establishes |
|---|---|---|
| Python syntax parsing | All 53 Python files parsed. | Syntax only; does not import or run the application. |
| Base deterministic classification fixtures | 12/12 matched. | Behavior on the included small fixture set. |
| Adversarially worded classification fixtures | 8/8 matched. | These eight keyword-classification examples, not prompt-injection resistance. |
| Refund extraction fixtures | 5/5 matched. | Order/amount extraction on the included five examples. |
| Original local Markdown links | Seven checked, none broken. | The supplied documentation's local file links resolved. |
| Documentation package validation | See `PORTFOLIO_STATUS.md` for the final packaging checks. | Presentation consistency and preservation of the supplied application files. |

The fixture check ran the original evaluator functions against the original
deterministic helper and enum modules. The modules were loaded directly to avoid
the ORM-registration package, which imports unavailable SQLAlchemy. No helper
function was replaced. This was **not** a pytest run, provider-adapter test,
database test, HTTP test, or frontend test.

## Results reported in the supplied archive

The original [REVIEW](../REVIEW.md) reports 53 passing tests, 88% statement coverage,
migration and seed checks, a frontend build, and browser interactions. That report
used PGlite through its PostgreSQL socket server rather than native PostgreSQL 16;
its local frontend build used Node 24. It explicitly did not run the Docker/nginx
stack, broker transport/crash recovery, or live AI APIs.

Those are **previously reported results**, preserved for traceability. They were
not reproduced during this documentation pass and must not be presented as new
CI results. The archive contains a CI configuration; no successful GitHub run has
been observed for this package.

## Current runtime boundary

The current workspace has no Docker, native PostgreSQL, Redis, or the required
FastAPI/SQLAlchemy/Celery/pytest dependencies. Bounded access checks to the Python
and npm package registries timed out. No dependency installation, substitute
application, or fabricated runtime was used to claim an end-to-end demonstration.

Therefore the full application, native Compose stack, frontend production build,
browser interactions, screenshots, and video remain unverified or uncaptured here.
These environment limitations do not establish that the application is broken.

## Next runtime verification

On a Docker-capable machine with dependency access and a disposable database:

1. Follow the existing startup, migration, and seed commands.
2. Run the existing pytest, lint, deterministic evaluation, and frontend build
   commands from [TESTING](TESTING.md). Record the actual runtime versions and output.
3. Walk the three core scenarios in [DEMO](DEMO.md), plus rejection and duplicate
   submission. Capture the actual results and any remaining failures.
4. If claiming scheduled recovery, separately confirm Beat and worker delivery
   through Redis. A manual retry or direct task-function call is insufficient.
5. Append new evidence with its date and environment. Preserve the distinction
   between these checks, the original review, and any later production validation.

No live model calls are needed for the local mock demonstration.
