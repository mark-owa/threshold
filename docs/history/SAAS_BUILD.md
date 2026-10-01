> Historical report. Statements, test counts, environment limits, and next steps
> describe the milestone or review recorded below. Current implementation and
> evidence are in [Scope](../SCOPE.md) and [Verification](../VERIFICATION.md).

# Threshold SaaS Build — Milestone 2

Threshold is being evolved in-place from the portfolio demo into a tenant-aware business SaaS. The original deterministic workflow engine and isolated demo sandbox remain intact.

## Milestone 1 retained

- Customer registration creates an isolated **trial** workspace and owner membership.
- Authenticated users can list, create, and switch workspaces.
- Shared tenant authorization helpers protect organization-owned data.
- The seeded Acme environment remains a **demo** workspace.
- `/api/v1/demo/*` scenarios are fenced to demo workspaces.
- The React operator shell exposes Overview, Approvals, Executions, Policies, Integrations, Audit, workspace switching, and the isolated demo sandbox.

## Implemented in Milestone 2

### Team invitations and role management

- Added persistent `organization_invitations` with a migration.
- Invitation bearer tokens are high-entropy and only a SHA-256 hash is persisted.
- Invitations expire after seven days and can be revoked before acceptance.
- `POST /api/v1/auth/join` supports both a new invited user and an existing account that supplies its password.
- Owners/admins can invite reviewers/viewers; only owners can invite admins.
- Owners can promote existing members to owner.
- Admins cannot modify owner/admin roles.
- Last-owner protection prevents a workspace from being left without an owner.
- Team invite, revoke, role-change, and removal events append control-plane audit entries.
- The frontend now has a Team surface for members, invitations, roles, and manual one-time token delivery.

Email delivery is intentionally not claimed yet: the raw invitation token is returned once to the authorized inviter for manual delivery until a mail provider is connected.

### Product onboarding

`GET /api/v1/workspace/onboarding` derives setup progress from live tenant state rather than a cosmetic checkbox list:

1. workspace created;
2. deterministic refund policy configured;
3. second team member/reviewer added;
4. provider integration connected.

The dashboard renders this as an onboarding checklist and routes the operator to the relevant configuration surface.

### Editable deterministic refund policy

- Added `PUT /api/v1/workspace/refund-policy` for owners/admins.
- The editor controls the two rules the existing engine already enforces:
  - `refund_window_days`;
  - `max_auto_refund_usd`.
- Values are validated server-side and stored in the existing `Policy.structured_rules` JSON.
- The workflow engine therefore reads these saved customer values during its existing `KNOWLEDGE_LOOKUP`, `BUSINESS_RULE`, and `RISK_ASSESSMENT` stages.
- Policy creation/update appends an audit entry.
- Reviewers/viewers can inspect policy but cannot mutate it.

This is deliberately not a free-form AI policy prompt. The authorization boundary remains deterministic.

## Still not production-ready

- Email verification, password reset, refresh-token/session rotation, and HTTP-only cookie sessions.
- Automated invitation email delivery.
- Real Shopify/Stripe/Slack credentials or OAuth.
- Secret-manager/KMS backed credential storage.
- A real customer workflow/template installation path for trial tenants.
- Transactional outbox, provider reconciliation, and durable action-attempt history.
- Billing and usage entitlements.
- Production observability/SLO alerting.

## Next build slice — Milestone 3

1. Integration credential boundary with secrets referenced rather than returned to the browser.
2. First real provider adapter, starting with Stripe-style refund execution semantics.
3. Provider-side idempotency and post-timeout reconciliation.
4. Installable refund workflow for customer/trial workspaces.
5. Action-intent / action-attempt persistence groundwork for durable execution.

## Verification in this environment

- Python syntax compilation: passed for backend application, migrations, and tests.
- Existing dependency-light regression subset: **27/27 passed** (`test_engine_logic`, `test_ai_provider_boundary`, `unit/test_primitives`).
- Frontend TSX TypeScript transpile/parser check: passed.
- Model metadata import recognizes the new invitation table.
- New Milestone 2 API regression tests were added for invitation hashing/authorization, last-owner protection, refund-policy persistence, and onboarding state.
- Full API tests still cannot execute in this runner because runtime dependencies/services such as `bcrypt`, `psycopg`, Celery, Docker/PostgreSQL are unavailable here.
- Full Vite production build remains unavailable because the pinned npm dependency tree is not installed in the runner.

Run Docker/CI verification with the declared dependencies before any deployment.

## Milestone 4 — durable delivery and recovery

Milestone 4 adds signed durable webhook ingress, a PostgreSQL transactional outbox, worker leases, dead-letter/recovery state, asynchronous live action execution, and an operator recovery console. See `docs/SAAS_MILESTONE_4.md`.
