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
**Status: IN PROGRESS**

Work:
- Use the complete M8 SaaS dashboard, not the older lightweight portfolio dashboard.
- Point the frontend at the Railway staging API.
- Deploy as a preview/staging web application.
- Configure exact CORS origin.
- Verify the browser can reach the API.

Exit criteria:
- Frontend loads over HTTPS.
- No fatal browser console errors.
- API health is reachable from the deployed origin.
- Authentication UI is functional.

## Milestone 2 — Core SaaS smoke test
**Status: TODO**

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
**Status: TODO**

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
**Status: TODO**

Requires user-owned Shopify development credentials/store.

Work:
- Validate current OAuth callback/HMAC behavior against current Shopify rules.
- Install into a development store.
- Validate nonce consumption and granted scopes.
- Receive and verify a real webhook.
- Fetch canonical order data through Admin GraphQL.

Exit criteria:
- OAuth install succeeds.
- Signed webhook succeeds.
- Canonical order sync succeeds.

## Milestone 5 — Stripe test integration and billing
**Status: TODO**

Requires user-owned Stripe test credentials.

Work:
- Configure Stripe test-mode secrets.
- Verify billing webhook signature and event dedupe.
- Run test checkout/customer-portal flow where applicable.
- Run a test refund with correct provider reference semantics.

Exit criteria:
- Test billing event is persisted exactly once.
- Test refund executes and verifies.
- Duplicate delivery does not duplicate business effect.

## Milestone 6 — Failure and recovery drills
**Status: TODO**

Work:
- Worker restart/crash.
- Redis interruption/recovery.
- Provider transient failure.
- Provider commit + client timeout -> UNKNOWN -> reconciliation.
- Stale retry / duplicate delivery.
- Outbox retry and dead-letter path.

Exit criteria:
- No duplicate side effects.
- Recoverable work resumes safely.
- UNKNOWN actions reconcile correctly.
- Failures remain visible/auditable.

## Milestone 7 — Backup, restore and observability
**Status: TODO**

Work:
- Create staging database backup.
- Restore into a safe staging target/drill.
- Verify authoritative state after restore.
- Configure useful application/worker availability alerts.
- Record incident owner and restore evidence.

Exit criteria:
- Successful documented restore drill.
- Restore timestamp recorded.
- Operational alerts/evidence exist.

## Milestone 8 — Beta readiness gate
**Status: TODO**

Work:
- Run the M8 beta-readiness gate against real staging evidence.
- Resolve every BLOCK item.
- Review WARN items explicitly.
- Keep live execution disabled until gate passes.

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
