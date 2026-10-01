# Current scope

Threshold is a refund workflow prototype with an operator dashboard. The local
demo uses fictional orders, deterministic mock AI, mock payments, and database
notification records.

| Area | Implemented behavior | Verification boundary |
| --- | --- | --- |
| Workspaces | Registration, memberships, role checks, invitations, tenant-scoped data. | PostgreSQL regression tests; no email verification or invitation delivery. |
| Refunds | Extraction, policy/risk checks, review, action records, verification, retries. | Mock demo and provider contract tests; no production payment proof. |
| Delivery | Signed webhooks, transactional outbox, worker leases, dead-letter recovery, reconciliation. | Tests exercise persistence and task functions; complete broker/crash drills remain pending. |
| Providers | Shopify, Stripe, and generic REST adapters; secret references and live-execution gate. | Test doubles and validation tools; real-account lifecycle evidence remains pending. |
| Commercial | Trial/plan entitlements, usage counters, Stripe checkout/portal and signed billing events. | Regression tests and configuration scaffolding; no customer revenue claim. |
| n8n/HubSpot | Signed CRM intake and final-outcome callbacks to an existing ticket. | Persistence, loopback HTTP, and template checks; installed n8n/HubSpot round trip remains pending. |
| Dashboard | Routed pages, typed API client, organization-scoped queries, approval and recovery forms. | Type/build checks and dated browser captures; no comprehensive UI test suite. |

Current CI evidence is in [Verification](VERIFICATION.md). Historical milestone
reports are under [history](history/README.md); an old list of deferred features
does not describe current implementation.

## Remaining work

Complete provider-account, worker
interruption, backup/restore, and alert-delivery drills; consolidate the M8 snapshot
deployment with canonical source. Refresh tokens, password reset, API-key issuance,
approval expiry, a general workflow continuation engine, and immutable audit storage
are not implemented.
