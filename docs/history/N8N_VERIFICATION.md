> Historical report. Statements, test counts, environment limits, and next steps
> describe the milestone or review recorded below. Current implementation and
> evidence are in [Scope](../SCOPE.md) and [Verification](../VERIFICATION.md).

# Historical frontend + n8n merge verification — 30 September 2026

These are reported checks bundled with the September 30 source archive. Current
GitHub import checks and native PostgreSQL evidence are recorded in
[VERIFICATION](../VERIFICATION.md). The old environment limitations and counts below
describe that earlier packaging review.

| Check | Result | Evidence boundary |
| --- | --- | --- |
| Full `pytest -q --tb=short` | 96 passed, 0 assertion failures, 41 setup errors | Every setup error is a PostgreSQL connection error; full suite is NOT green |
| Real local HTTP callback tests | 3 passed (included in 96) | Success acknowledgment, HTTP 429/Retry-After and permanent HTTP 401; real TCP/HTTP test receiver, not n8n |
| n8n JavaScript/structure harness | 16 passed | Validates template code/links, HMAC, tenant/final-state guards, stage mapping and acknowledgments; not an n8n runtime |
| Ruff | Passed | Full backend, no disabled rules |
| Mypy | Passed, 52 files | Full application typecheck; fresh cache |
| TypeScript | Passed | `npm run typecheck` |
| Frontend production build | Passed | `npm run build`, 1,998 modules |
| Frontend preservation | Passed | All 73 original frontend source/config files byte-identical |
| API path compatibility | Passed | 45 frontend API path references match FastAPI OpenAPI paths; no claim about every response schema |
| Alembic offline SQL | Passed | All eight migrations generate PostgreSQL SQL; not applied to a database here |
| Python compilation | Passed | Application, migrations, scripts and tests |
| AI boundary evaluation | Passed | Classification 12/12, adversarial 8/8, extraction 5/5; mock heuristic evaluation |
| Docker Compose runtime | Not run | Docker unavailable; YAML structure checked separately |
| Browser interaction | Blocked | agent-browser daemon failed to start twice; no authenticated navigation claim |
| Real n8n / HubSpot | Not run | No account credentials or runtime configured; workflows remain inactive |

## PostgreSQL-dependent verification still required

A PostgreSQL server is unavailable in this environment. Installation failed on
system permission operations. SQLite was not substituted. The 41 affected tests
remain in the project, including 10 n8n bridge cases. They cover real persistence,
duplicate/conflicting events, missing/invalid headers, ordinary webhook support,
organization/portal isolation, final-outcome deduplication and approval rejection.
The existing lifecycle suite also covers approval/modified approval, retries and
provider boundaries. These cases were collected but could not execute here.

The unit dispatcher tests prove branching with test doubles, including Retry-After,
retry limits and stale lease success/failure guards. They do not prove PostgreSQL
locking under concurrency. The new unique publisher tokens also have a regression
check for successive invocations sharing the same absent Celery task ID.

Run from the extracted Threshold folder after starting Docker and migrating:

```powershell
docker compose exec backend pytest -q
docker compose exec backend ruff check .
docker compose exec backend mypy --no-incremental app
docker compose exec backend python -m scripts.evaluate_ai
node scripts/check_n8n_templates.cjs
Push-Location frontend
npm ci
npm run typecheck
npm run build
Pop-Location
```

Before claiming the complete architecture works in your environment, import the
inactive templates, configure credentials/portal/stages, and observe signed intake
through the real worker to the final CRM acknowledgment. Test worker interruption,
lost acknowledgment, transient CRM failure, permanent credential failure and
stale-lease recovery. Requeue outcomes rather than replaying a completed refund.

## Remaining functional limitations

- One pre-existing, dedicated HubSpot ticket per request; no ticket creation/contact lookup.
- Manual intake template; configure your external trigger separately.
- One bridge endpoint per organization assumed for CRM event deduplication.
- Only verified completion and cancellation generate outcomes; no intermediate status stream.
- At-least-once delivery; no durable receiver inbox or exactly-once CRM claim.
- Numeric Retry-After supported and capped at an hour; HTTP-date and jitter not implemented.
- Existing completed events are not backfilled when a destination is enabled.
- Outbound bridge configuration is environment-driven; the UI shows intake and recovery,
  not a verified n8n connection status.
- Dependency vulnerability audits and deployed load/crash tests were not run here.
- One existing Starlette/httpx deprecation warning occurs; no warning was suppressed.
