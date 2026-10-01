> Historical report. Statements, test counts, environment limits, and next steps
> describe the milestone or review recorded below. Current implementation and
> evidence are in [Scope](../SCOPE.md) and [Verification](../VERIFICATION.md).

# Threshold SaaS Milestone 4 — Production Durability & Recovery

Milestone 4 moves Threshold's live execution path from "queue a task and hope the handoff survives" to an explicit durable-delivery model.

## What changed

### Transactional outbox

Inbound webhook acceptance and live outbound action intents create `outbox_messages` inside the same PostgreSQL transaction as the durable business record. Celery Beat publishes committed outbox rows to the broker. Publishing is at-least-once; consumers are idempotent.

Outbox states:

- `pending`
- `processing`
- `sent`
- `failed`
- `dead_letter`

A publisher crash after broker delivery but before `sent` may redeliver the task. That is intentional and safe because event processing is keyed by `incoming_event_id` and action execution is keyed by the durable `ActionExecution` plus provider idempotency key.

### Signed inbound webhooks

Tenant webhook endpoints are stored in `webhook_endpoints` with a secret **reference**, not a raw secret.

Expected headers:

- `X-Threshold-Event-Id`
- `X-Threshold-Timestamp`
- `X-Threshold-Signature`

Signature input is `timestamp + "." + raw_body` using HMAC-SHA256. Timestamp skew is bounded to reduce replay risk. Provider event IDs are incorporated into the tenant-scoped idempotency key.

Deployment secret example:

```env
THRESHOLD_WEBHOOK_SECRET__SHOPIFY_WEBHOOK=<secret>
```

### Durable inbound processing

Webhook requests commit `IncomingEvent` first. Worker processing happens later through the outbox.

`IncomingEvent` now tracks:

- processing attempts
- processing lease start
- next retry time
- completion time
- last error
- dead-letter state

A live processing lease prevents duplicate Celery deliveries from racing to create the same workflow execution.

### Durable live action execution

Demo `mock_payments` remains synchronous for the portfolio sandbox. Customer/live providers now use:

```text
workflow transaction
  -> ActionExecution(PENDING)
  -> OutboxMessage(execute_action)
  -> COMMIT
  -> publisher
  -> Celery worker
  -> ActionExecution(EXECUTING lease)
  -> COMMIT lease
  -> provider call
  -> verification/result
```

The provider is never called before the action intent is durably committed.

### Crash semantics

If an action worker dies while the provider call may have happened, a stale `EXECUTING` lease becomes:

```text
UNKNOWN
```

It is **not** automatically retried. An operator must reconcile the provider outcome first.

This is the central safety rule for money-moving or otherwise non-idempotent external effects.

### Recovery console

The operator UI now surfaces:

- failed/dead-letter inbound events
- failed/dead/stuck outbox messages
- retrying/unknown/dead external actions

Supported controls:

- safe event replay when no workflow execution exists
- manual outbox requeue for admins
- provider reconciliation for `UNKNOWN` actions

### Health/readiness

Threshold now exposes both legacy and explicit probe paths:

- `/health` and `/health/live`
- `/ready` and `/health/ready`

Readiness checks PostgreSQL and Redis and reports the pending outbox backlog.

## Deliberate boundaries

Milestone 4 does **not** claim:

- end-to-end production proof against real PostgreSQL/Redis/Celery in this build environment
- provider-specific Shopify or Stripe adapters
- distributed tracing/SLO alerting
- KMS/Vault implementation (the secret-reference contract is ready for one)
- automatic replay of workflow executions that crashed after arbitrary committed mid-step state

That last case is intentionally surfaced for manual recovery rather than guessed.

## Next milestone

Milestone 5 should implement the first commercial vertical adapter set, preferably Shopify + Stripe, on top of this durable execution boundary.
