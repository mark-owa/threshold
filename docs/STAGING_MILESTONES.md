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
- No fatal browser console errors.
- API health is reachable from the deployed origin.
- Authentication UI is functional.

## Milestone 2 — Core SaaS smoke test
**Status: IN PROGRESS**

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
**Status: IN PROGRESS**

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
