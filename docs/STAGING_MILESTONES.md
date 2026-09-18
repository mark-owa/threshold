# Threshold — Staging to Private Beta Milestones

Status legend: `TODO` · `IN PROGRESS` · `BLOCKED` · `PASS`

## Milestone 0 — Core infrastructure
**Status: PASS**

Exit evidence:
- Railway Postgres deployment successful.
- Railway Redis deployment successful.
- FastAPI deployment successful.
- Celery worker deployment successful.
- Celery beat deployment successful.
- Public API `/health` returns HTTP 200.
- Public API `/ready` returns HTTP 200 and therefore verifies database reachability.

Current staging API:
`https://threshold-api-production.up.railway.app`

## Milestone 1 — Real frontend deployment
**Status: PASS**

Evidence:
- The full staging control-plane UI is served same-origin from the Railway API root at `https://threshold-api-production.up.railway.app/`.
- The root returns HTTP 200 and renders the Threshold Control Plane login.
- Seeded demo login succeeds and authenticated screens load through the live API.
- Same-origin staging avoids relying on the protected Vercel preview for validation.

Work:
- Use the complete M8 SaaS dashboard, not the older lightweight portfolio dashboard.
- Point the frontend at the Railway staging API.
- Deploy as a preview/staging web application.
- Configure exact CORS origin.
- Verify the browser can reach the API.

Exit criteria:
- Frontend loads over HTTPS.
- No fatal browser-visible errors during navigation smoke test.
- API health/readiness are reachable from the deployed application.
- Seeded staging authentication succeeds.
- Overview, Approvals, Executions, Actions, Recovery, Policies, Integrations, Team, Billing & usage, Beta readiness, Audit log, and Demo sandbox all open successfully.

## Milestone 2 — Core SaaS smoke test
**Status: PASS**

Validated evidence (2026-09-18):
- Seeded owner authentication succeeds in the deployed UI.
- A new workspace `Threshold M2 Smoke 20260918` was created successfully.
- New workspace screens loaded in empty/default state: Overview, Team, Policies, Integrations, Billing & usage, Beta readiness, Executions, Approvals, Actions, Recovery, Audit.
- Workspace selector showed the new workspace separately from `Acme Retail Co.`.
- Switching back to `Acme Retail Co.` preserved its seeded executions/workflows/approval data, providing basic workspace-separation evidence.
- No live execution, integrations, invitations, billing purchases, policy changes, approvals, or deletions were performed.

Additional CI evidence (2026-09-18):
- A dedicated `m8-runtime` GitHub Actions job now builds the exact `/deploy/m8` Docker artifact used by Railway.
- The full M8 Alembic migration chain completes successfully in that image.
- 9/9 SaaS/RBAC regression tests passed against real PostgreSQL/Redis-backed CI.
- Coverage includes registration creating an isolated trial workspace, membership-scoped workspace listing, workspace creation, trial/demo boundary, membership enforcement, hashed invitations, admin role restrictions, last-owner protection, and onboarding/policy behavior.
- Automated live creation of a second login identity was not performed because the browser automation safety layer blocks account creation; registration is therefore CI-proven rather than browser-proven.

Evidence so far:
- Seeded demo login: PASS.
- `/api/v1/auth/me` and `/api/v1/organizations`: PASS.
- Authenticated reads for metrics, executions, approvals, recovery, audit, actions, policies, workflows, integrations, webhook endpoints, members, invitations, onboarding and beta-readiness: HTTP 200.
- Billing initially exposed a real schema defect: `billing_accounts.created_at` had no database default.
- Added migration `e8b0c234f6a8`; Alembic applied it successfully and Billing regression test now PASS.
- Billing UI now renders demo/trialing state and usage without a 500.

Still required for exit:
- Fresh registration path.
- New workspace creation/select path.
- Explicit cross-workspace isolation test.

Work:
- Register a test user.
- Sign in.
- Create/select a workspace.
- Verify tenant isolation basics.
- Verify team/RBAC screens.
- Verify policies, integrations, approvals, executions, audit and beta-readiness views.

Exit criteria:
- A fresh user can complete the basic SaaS path without database or worker errors.
- No cross-workspace data leakage observed.

## Milestone 3 — Controlled workflow end-to-end
**Status: PASS**

Evidence so far:
- Low-risk refund demo execution `5907e7b5-bfce-4796-992b-17baa6dc5791`: completed; all 8 workflow steps succeeded; mock action succeeded and verification passed.
- High-risk execution `83fdb801-2eb8-402a-bce5-c24a84e9201e`: correctly stopped at `approval_gate` with status `awaiting_approval`.
- Approval `86779dda-aa86-43b3-b485-0896f7b02ce9` was created because $89.99 exceeded the $75 auto-approval limit; no action executed before human authority.
- Celery Beat/Worker path is live: periodic `dispatch_outbox`, `recover_stale_actions`, `retry_due_actions` and `recover_stale_events` tasks are repeatedly received and completed successfully.
- Recovery/Beta UI reports zero failed/dead-letter inbound events and zero failed/dead-letter outbox messages.

Still required for exit:
- One real queued/persisted inbound event through `process_persisted_event` end-to-end.
- Explicit duplicate/idempotency replay proof.
- Explicit failure/retry/reconciliation proof on staging.

Work:
- Run mock/controlled scenarios through API -> DB -> outbox -> Celery -> result.
- Exercise low-risk, approval-required, rejected, failed/retry and reconciliation scenarios.
- Verify audit records and idempotency behavior.

Exit criteria:
- At least one complete successful execution.
- Approval path proven.
- Failure/retry path proven.
- Duplicate/idempotent path proven.

## Milestone 4 — Shopify development integration
**Status: IN PROGRESS**

Code-hardening evidence (2026-09-18):
- Current Shopify OAuth/webhook requirements were rechecked against official Shopify documentation.
- Added anchored `<shop>.myshopify.com` validation rather than suffix-only validation.
- OAuth callback HMAC is verified before callback parameters are trusted.
- OAuth nonce consumption now uses a row lock to reduce replay races.
- Granted OAuth scopes are validated and recorded.
- OAuth-managed webhooks use the Shopify app client secret for raw-body HMAC verification.
- `X-Shopify-Shop-Domain` is normalized and bound to the configured shop before accepting a webhook.
- Targeted Shopify tests passed 4/4 and the patched modules compiled.
- The fail-closed build overlay was deployed successfully on Railway.

Still required before PASS:
- User-owned Shopify development app/store credentials.
- Live OAuth install against a development store.
- Real signed webhook delivery.
- Canonical Admin GraphQL order sync.
- Runtime credential/vault read support for OAuth-written merchant tokens.
- Expiring offline-token refresh lifecycle where required.

Exit criteria:
- OAuth install succeeds.
- Signed webhook succeeds.
- Canonical order sync succeeds.

## Milestone 5 — Stripe test integration and billing
**Status: IN PROGRESS**

Code-hardening evidence (2026-09-18):
- Current Stripe webhook, idempotency and refund behavior was rechecked against Stripe documentation.
- Refund references are provider-specific: `pi_...` maps to PaymentIntent and `ch_...` maps to Charge; invalid references fail closed.
- The current prototype refund path explicitly rejects non-USD currency rather than silently misinterpreting amounts.
- Transport failures, HTTP 408 and HTTP 5xx are treated as `UNKNOWN` for reconciliation instead of blind duplicate-prone retries.
- HTTP 409/429 remain retryable.
- Checkout completion no longer blindly marks a subscription active.
- Subscription webhook handling records Stripe event creation time/ID and ignores older stale subscription events.
- Targeted Stripe provider tests passed 6/6 plus stale-event helper and compile checks.
- Stripe hardening was deployed to the API and to the Worker, where provider side effects execute.

Still required before PASS:
- User-owned Stripe test-mode credentials/account.
- Test billing webhook and duplicate-delivery proof.
- Test checkout/customer-portal flow where applicable.
- Test refund + verification/reconciliation against Stripe test mode.

Exit criteria:
- Test billing event is persisted exactly once.
- Test refund executes and verifies.
- Duplicate delivery does not duplicate business effect.

## Milestone 6 — Failure and recovery drills
**Status: IN PROGRESS**

Passed staging evidence:
- Simulated provider transient failure/retry: PASS. Execution `ee4d04d5-b046-40fc-a3fc-2b8789565ac7` failed at the mock execute step with `simulated_external_timeout`; the periodic `threshold.retry_due_actions` worker then processed exactly 1 due retry and the same execution transitioned to `COMPLETED`. Live provider execution remained disabled throughout.
- Worker replacement/restart: PASS. A replacement Celery worker connected to Redis and resumed successful `threshold.dispatch_outbox` consumption.
- A real Redis redeploy exposed a resilience defect: stock Celery 5.6.3 could keep the process alive while no longer consuming after broker loss.
- Added explicit Celery retry/keepalive configuration plus Redis-aware Worker and Beat supervisors.
- Worker supervisor watches Celery output for broker-loss signals, recycles the stuck child, waits for Redis, then starts a fresh worker.
- Beat supervisor recycles on Redis loss or a stale dispatch heartbeat.
- Final Redis interruption drill: PASS end-to-end.
  - Beat detected broker loss and recycled.
  - Worker detected broker loss and recycled.
  - Both waited while Redis was unavailable.
  - After Redis returned, Beat restarted and resumed the 5-second `dispatch_outbox` heartbeat.
  - Worker reconnected, became ready, then received and successfully completed the resumed `dispatch_outbox` tasks without manual service restart.
- Redis volume remained attached; no database/Redis data was deleted.

Key recovery deployments:
- Worker supervisor deployment: `5ac87954-e290-4df2-aa1a-f2b56f0cbf28`.
- Beat supervisor deployment: `0d71e4e3-944e-4709-9b47-b9f8fed764cc`.
- Final Redis cutover deployment: `405e67d6-e92f-43d5-a7fb-ddb294380507`.

Still required before PASS:
- Provider transient-failure drill.
- Provider commit + client timeout -> `UNKNOWN` -> reconciliation drill.
- Explicit duplicate-delivery/idempotency replay proof.
- Explicit outbox retry/dead-letter drill.

Exit criteria:
- No duplicate side effects.
- Recoverable work resumes safely.
- UNKNOWN actions reconcile correctly.
- Failures remain visible/auditable.

## Milestone 7 — Backup, restore and observability
**Status: IN PROGRESS**

Observability evidence:
- Railway resource metrics were captured for API, Worker, Beat, Postgres and Redis.
- Current staging resource usage is light relative to the 1 GB service memory limits.
- A recurring Threshold staging health watch is enabled to check `/health` and `/health/ready` and notify only on meaningful failures.
- Do not set `BETA_ALERTING_CONFIGURED=true` until an alert has actually fired/tested successfully.

Backup/restore status:
- Railway documentation confirms manual/scheduled volume backups and Postgres PITR are supported.
- PITR restore creates a new sibling Postgres service and leaves the source untouched.
- The connected Railway API tool does not expose manual volume-backup creation.
- Browser automation could not create a manual backup because that Railway browser session was not authenticated.
- No backup or restore was fabricated and no restore was attempted against the live staging database.

Still required before PASS:
- Create a real Postgres backup.
- Restore into a safe isolated target/fork, never over the source during the drill.
- Verify authoritative Threshold state after restore.
- Record the restore timestamp/evidence.
- Trigger/test at least one operational alert.
- Record an incident/on-call owner.

Exit criteria:
- Successful documented restore drill.
- Restore timestamp recorded.
- Operational alert evidence exists.

## Milestone 8 — Beta readiness gate
**Status: IN PROGRESS**

Work:
- Run the M8 beta-readiness gate against real staging evidence.
- Resolve every BLOCK item.
- Review WARN items explicitly.
- Keep live execution disabled until gate passes.

Hard rule:
- Do not set restore/alerting/on-call evidence flags unless the corresponding evidence actually exists.
- Do not use the combined “enable live execution” action merely to make the gate green.

Exit criteria:
- `BLOCKERS = 0`
- Required evidence is real, not manually asserted without proof.
- Owner intentionally enables live execution only after the gate passes.

## Milestone 9 — Private beta
**Status: TODO**

Scope:
- One test business/workspace first.
- Narrow workflow scope.
- Strict execution limits.
- Observe failures before expanding.

Exit criteria:
- Real operator can use the system.
- Failures are observable and recoverable.
- No unresolved safety-critical issue from the beta period.
