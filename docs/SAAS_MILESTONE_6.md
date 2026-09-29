# SaaS Milestone 6 — Commercialization

Milestone 6 adds the commercial control plane around Threshold's ecommerce execution engine.

## Implemented

- 14-day tenant trial lifecycle.
- Plan catalog: Trial, Starter, Business, Enterprise.
- Server-side entitlement checks for workflow executions and external actions.
- Monthly usage counters for workflow executions and external actions.
- Stripe-hosted subscription Checkout creation (Starter/Business) behind server-side credentials.
- Stripe Billing Portal handoff for existing billing customers.
- Signed Stripe billing webhook verification using the raw body, timestamp tolerance, and v1 HMAC signature.
- Subscription/customer/price/status synchronization back into the tenant billing record.
- Shopify standalone OAuth install URL with short-lived signed state.
- Shopify OAuth callback validation and server-to-server access-token exchange.
- Fail-closed OAuth token persistence: the callback refuses to exchange/store merchant credentials unless a secret-vault sink is configured. Raw merchant access tokens are never written to the Threshold database.
- Billing & Usage UI with plan, trial, quota consumption, checkout, billing portal, and Shopify install controls.

## Commercial safety boundaries

Threshold does not unlock a paid plan because a browser returned from Checkout. Plan state is synchronized only from a verified Stripe webhook.

Shopify OAuth does not write access tokens into `integration_configs`. The database receives only a credential reference after the configured secret-vault sink confirms receipt.

## Still required before private beta

- Configure real Stripe test/live secret and webhook secret references.
- Create Stripe Starter and Business Price IDs.
- Configure the Stripe webhook endpoint and event selection.
- Create/configure the Shopify app and redirect URL.
- Provide a production secret-vault sink (for example a KMS/Vault-backed service) for dynamic Shopify merchant tokens.
- Run full Postgres/Redis/Celery integration tests and real Stripe/Shopify sandbox flows.
- Add idempotent Stripe webhook event storage before accepting high-volume billing traffic.
- Add email delivery for invites and billing notifications.
