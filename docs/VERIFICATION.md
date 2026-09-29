# Verification evidence

This is a ledger of what has and has not been checked, kept separate from the
project's claims. Entries are dated, say how the check was made, and say what it does
*not* establish. Nothing here is a hosted CI result.

## Status at a glance

| Question | Status |
|---|---|
| Full pytest suite against PostgreSQL 16 | **Not reproduced.** Reported once (see below) against a PostgreSQL-compatible emulator. |
| Docker Compose stack (backend, worker, beat, frontend, nginx) | **Never observed running** in the recorded evidence. |
| Hosted CI run | **None recorded.** A workflow is defined; no successful run has been observed. |
| Frontend production build with the real dependency tree | Reported once (Node 24) for the previous single-file dashboard; **not run since the restructure.** |
| Scheduled recovery through Redis, Beat, and a worker | Not confirmed end to end. |
| Live Shopify, Stripe, or secret-vault connections | Not exercised. |

## Evidence log

### 2026-09-29 — frontend restructure (later the same day)

`frontend/src/main.tsx` (915 lines, one `App()` with 34 `useState` calls, every API value
typed `any`) was split into `App.tsx`, `types.ts`, `api.ts`, `workspaceData.ts`,
`workspaceActions.ts`, `nav.ts`, and one file per view under `components/`.
Made without network access, so `npm ci`, the Vite build, and a browser were not available.

| Check | Result | What it establishes |
|---|---|---|
| `tsc --noEmit`, `strict: true`, over all of `src/` | 0 errors. | Names resolve, props match, and every API value is typed. Used hand-written stubs for `react`/`react-dom`, modeling change events as `@types/react` does (`e.target.value` is a `string`). **Not** a check against the real React types. |
| Four planted bugs (wrong prop type, misspelled API field, invalid decision literal, reading a response body without checking `ok`) | All four rejected. | The check is not vacuous, and the `parseResponse` union really does make an unchecked read a compile error. |
| Text diff of the 13 extracted view components against the original | Identical apart from two intended type annotations in `Billing`. | The JSX was moved, not rewritten. The sign-in screen differs only in its submit handler; the app shell is identical. |

Not established: that the app builds under Vite, that it renders, or that any screen
behaves as before. Someone should run `npm ci && npm run build` and click through each
tab. Deliberate behavior differences are listed in the change notes; the notable one is
that the sign-in form now resets after sign-out instead of retaining the typed values.

### 2026-09-29 — static checks after a refactor

Made without Docker, PostgreSQL, Redis, or installed dependencies, after these
changes: middleware ordering in `main.py`, per-check failure reasons in the refund
rule, splitting the workflow engine into `engine.py` / `steps.py` /
`refund_rules.py` / `types.py`, caching the AI provider, and a shared response helper
in the dashboard.

| Check | Result | What it establishes |
|---|---|---|
| `python -m compileall` over `app`, `alembic`, `scripts` | Clean. | Syntax only. Does not import the application or resolve names across modules. |
| Refund-rule equivalence | 12 of 12 cases matched. | A one-off script (not committed) re-implemented the old single boolean and the new per-check logic and compared them on zero, negative, non-whole-cent, over-balance, wrong-status, outside-window, NaN, over-refunded, and combined-failure inputs. It checks the logic in isolation, not the engine. |
| `tsc --noEmit` on `frontend/src/main.tsx` | 0 errors. | Used hand-written minimal type stubs for `react` and `react-dom` because `@types/react` was unavailable. It catches syntax errors and unresolved variables; it is **not** a real type-check of React usage and does not replace `npm run build`. |

None of this ran the pytest suite. The refactor above should be treated as untested
until `make test` passes on a machine with the full stack.

### 2026-09-16 — deterministic fixture checks

| Check | Result | What it establishes |
|---|---|---|
| Python syntax parsing | All 53 Python files parsed. | Syntax only; does not import or run the application. |
| Base deterministic classification fixtures | 12/12 matched. | Behavior on the included small fixture set. |
| Adversarially worded classification fixtures | 8/8 matched. | These eight keyword-classification examples, not prompt-injection resistance. |
| Refund extraction fixtures | 5/5 matched. | Order/amount extraction on the included five examples. |
| Local Markdown links | Seven checked, none broken. | The documentation's local file links resolved at the time. |

The fixture check ran the original evaluator functions against the deterministic
helper and enum modules, loaded directly to avoid the ORM-registration package. No
helper function was replaced. This was **not** a pytest run, provider-adapter test,
database test, HTTP test, or frontend test.

## Previously reported results

The original [REVIEW](../REVIEW.md) reports 53 passing tests, 88% statement coverage,
migration and seed checks, a frontend build, and browser interactions. That report used
PGlite through its PostgreSQL socket server rather than native PostgreSQL 16; its
local frontend build used Node 24. It explicitly did not run the Docker/nginx stack,
broker transport or crash recovery, or live AI APIs.

Those are **previously reported results**, kept for traceability. They have not been
reproduced since, the codebase has grown considerably after them (the SaaS milestones
and the changes logged above), and they must not be presented as current or as CI
results. A CI configuration exists; no successful hosted run has been observed.

## What the checks above do not tell you

They were made in environments without Docker, native PostgreSQL, Redis, or the
FastAPI/SQLAlchemy/Celery/pytest dependencies, and without access to the package
registries. That limits what could be checked; it does not show the application is
broken. It also means the full application, the Compose stack, the production
frontend build, browser interactions, and the demo recording remain unverified.

## Next runtime verification

On a Docker-capable machine with dependency access and a disposable database:

1. Follow the startup, migration, and seed commands in the [README](../README.md).
2. Run the pytest, lint, deterministic evaluation, and frontend build commands from
   [TESTING](TESTING.md). Record the actual runtime versions and output.
3. Walk the three core scenarios in [DEMO](DEMO.md), plus rejection and duplicate
   submission. Capture the actual results and any failures.
4. If claiming scheduled recovery, separately confirm Beat and worker delivery
   through Redis. A manual retry or a direct task-function call is insufficient.
5. Append the new evidence here with its date and environment. Keep the distinction
   between these checks, the original review, and any later production validation.

No live model calls are needed for the local mock demonstration.
