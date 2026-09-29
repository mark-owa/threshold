# Threshold SaaS Milestone 3 — Live execution boundary

Milestone 3 replaces the prototype's hard-wired mock payment behavior with a provider boundary that can execute a real refund-style HTTP contract while preserving the demo sandbox.

## What changed

- Demo workspaces may use `mock_payments`; trial/live workspaces do not silently fall back to mocks.
- Live workspaces can configure a `generic_rest` refund integration.
- Provider hosts must be explicitly allowlisted with `INTEGRATION_ALLOWED_HOSTS`.
- Integration secrets are not stored in `integration_configs`. Threshold stores a `credential_ref` and resolves the value from `THRESHOLD_INTEGRATION_SECRET__<REF>`. A vault/KMS adapter can replace that resolver later without changing provider configuration.
- Every provider interaction is persisted as an `action_attempt` without authentication headers or secret values.
- The same durable action idempotency key is sent to the provider on retries.
- A successful provider response is not enough: live execution requires verification/reconciliation.
- Transport ambiguity produces `ActionStatus.UNKNOWN`. Unknown actions cannot be blindly retried; an operator must reconcile first.
- Reconciliation that proves the provider never created the action moves it to `RETRYING`; reconciliation that finds the action marks it verified/succeeded.
- Operators can inspect the action ledger and explicitly reconcile unknown actions.

## Expected live provider contract

Configured endpoints:

- `POST refund_path` receives `{order_number, amount_usd}` and the `Idempotency-Key` header.
- `GET verify_path_template` verifies a known provider operation id.
- `GET reconcile_path_template` looks up an operation by Threshold idempotency key.

The generic adapter is intentionally narrow. A Stripe/Shopify-specific adapter should implement the same `RefundProvider` interface rather than putting provider-specific rules into the workflow engine.

## Still not production-complete

- No managed secret vault/KMS implementation yet; the current boundary uses injected environment secrets.
- No OAuth connector flow yet.
- No transactional outbox yet.
- No signed inbound provider webhook ingestion yet.
- No provider-specific Stripe/Shopify implementation yet.
- Full API/database integration tests require the complete dependency stack and PostgreSQL.
