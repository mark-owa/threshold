# SaaS Milestone 5 — Shopify + Stripe ecommerce vertical

Threshold now has provider-specific ecommerce boundaries rather than treating every live action as generic REST.

## Implemented

- Shopify Admin GraphQL configuration using a deployment secret reference.
- Shopify HMAC webhook verification (`X-Shopify-Hmac-SHA256`) and webhook-ID deduplication.
- Durable Shopify order-event handoff through the transactional outbox.
- Shopify order/customer cache hydration, including original total, refunded total, remaining refundable amount, currency, external order id, and payment transaction reference.
- Manual Shopify order sync for an operator/reviewer.
- Stripe refund provider with smallest-currency-unit amounts and Stripe idempotency keys.
- Stripe refund retrieval for verification/reconciliation when a refund id is known.
- Shopify `refundCreate` adapter using the current Admin GraphQL idempotency directive and a parent SALE/CAPTURE transaction.
- Explicit `refund_enabled` selection to stop two connected providers from both being eligible to execute the same refund.
- Workflow eligibility now checks remaining refundable balance, not only original order total.

## Deliberate boundary

This milestone uses credential references suitable for a controlled/private merchant deployment. It does **not** yet implement public Shopify App Store OAuth or dynamic vault writes. That belongs in the onboarding/commercialization milestone so access tokens can be issued/revoked per merchant without ever storing plaintext credentials.

## Production caveats

Live provider calls require exact hosts in `INTEGRATION_ALLOWED_HOSTS`. A real deployment still needs end-to-end validation against a Shopify development store and Stripe test account before live funds are enabled.
