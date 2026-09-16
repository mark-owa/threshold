# Implemented scope and deferred work

## Implemented

- PostgreSQL models/migrations and local Compose setup.
- Login, current user, tenant membership, and reviewer permission checks.
- Synchronous and queued authenticated demo ingestion.
- Reference refund workflow with policy/risk gating, approval, mock execution,
  verification, event/action deduplication, retries, and circuit state.
- Four smaller classify-and-notify demo workflows.
- Provider adapters, prompt versions, step/usage records, request logging, and metrics.
- React operator dashboard, seed scripts, tests, and small labeled evaluations.

## Deferred, not represented as working features

Signed webhooks and API-key management; refresh tokens; user/organization management;
real payment, email, CRM, and Slack connectors; rate limiting; general workflow
continuations; approval expiry/escalation; robust queue crash recovery; immutable
audit storage; comprehensive live-model evaluation; recorded demo/screenshots.

These are scope boundaries, not requirements to expand this portfolio project.
