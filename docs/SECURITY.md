# Security and trust boundaries

Threshold treats model output, inbound webhooks, user input, provider responses, and external execution outcomes as untrusted until deterministic checks verify them. AI may propose actions; policy, authorization, approval, and provider verification determine whether an action is allowed and whether it actually completed.

## Authentication and tenancy

Passwords are bcrypt hashed. Access tokens are short lived JWTs and require issuer, audience, issued-at, not-before, JTI, expiry, subject, and token type claims. Organization membership and role checks scope workspace resources. UUID identifiers reduce trivial sequential enumeration but do not replace authorization.

## HTTP boundary

The API applies request IDs, structured request/failure logging, configurable Redis-backed rate limits, request-size limits, restrictive CORS, anti-framing/content-sniffing/referrer/permissions headers, and HSTS in staging/production. Authentication responses are `Cache-Control: no-store`.

Rate limiting deliberately fails open if Redis is unavailable so a cache outage does not become a total application outage. Alerting should therefore monitor Redis/readiness and rate-limit availability. Proxy client-IP trust is disabled by default and should be enabled only behind a trusted proxy that overwrites `X-Real-IP`.

## Webhooks and OAuth

Tenant webhooks and Shopify deliveries use provider signatures. Stripe Billing webhooks additionally persist a unique provider/event receipt in the same transaction as the protected business state; exact redeliveries become no-ops and event-id reuse with different bytes is rejected.

Shopify OAuth uses signed, expiring state plus a persisted, single-use nonce. Merchant access tokens are handed to an external secret sink and only a credential reference is stored in the application database.

## Secrets and outbound calls

Integration credentials are resolved from deployment secrets or an external vault/sink by reference. Configurable outbound integration hosts are allowlisted. Production startup rejects weak core signing secrets, wildcard CORS, and an HTTP public application URL.

## Durable execution

Transactional outbox rows separate database commits from worker delivery. External action attempts retain idempotency and verification context. Ambiguous provider outcomes enter `UNKNOWN` and require reconciliation instead of blind retry. Dead-letter/recovery tooling distinguishes replayable events from unsafe external side effects.

## Deployment

The backend production image installs only runtime dependencies and runs as a non-root user. Compose services use read-only filesystems where practical and `no-new-privileges`. Nginx limits body size and adds baseline security headers. TLS is expected at the production ingress/load balancer; the included Compose file is not itself an internet-grade TLS terminator.

CI runs lint, migrations, tests with coverage enforcement, dependency audits, frontend build, and production Compose syntax validation. Backup scripts provide dump creation, catalog verification, and an isolated restore drill. These mechanisms still require an operator to schedule, monitor, and periodically prove them.
