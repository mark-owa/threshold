# Implemented scope and deferred work

## Implemented

- PostgreSQL models/migrations, local Compose, and CI.
- Authentication, workspaces, memberships, roles, and invitations.
- Refund policy/approval, mock execution, action records, retries, and reconciliation.
- Signed webhook intake, transactional outbox, and recovery tooling.
- Shopify/Stripe/generic REST adapters and commercial billing scaffolding.
- Routed React dashboard with typed API calls and organization-scoped queries.
- Optional signed n8n final-outcome bridge and inactive HubSpot templates.
- Regression tests, deterministic evaluations, and historical demo captures.

## Deferred or incompletely verified

Refresh tokens, API-key issuance, general workflow continuation, approval expiry,
immutable audit storage, current dashboard recordings, real provider/n8n round trips,
complete interruption/restore/alert drills, and consolidation of the historical M8
runtime with canonical source.

[VERIFICATION](VERIFICATION.md) distinguishes implemented code from observed behavior.
