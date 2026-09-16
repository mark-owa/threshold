# Threshold API

Threshold exposes two classes of API endpoints.

## Authentication

### `POST /api/v1/auth/login`

Accepts:

```json
{"email":"owner@acme-demo.example.com","password":"demo1234"}
```

Returns a short-lived bearer token.

### `GET /api/v1/auth/me`

Returns the authenticated user and organization memberships.

## Operations

Business-data `/api/v1/ops/*` endpoints require a bearer token plus an `org_id` query parameter. The server checks that the authenticated user belongs to that organization.

### `GET /api/v1/ops/metrics?org_id=<uuid>`

Returns total executions, completed/failed/awaiting counts, automation rate, and approval rate.

### `GET /api/v1/ops/executions?org_id=<uuid>&limit=25`

Returns the most recent workflow executions for the organization.

### `GET /api/v1/ops/approvals?org_id=<uuid>&status=pending`

Returns the review queue for owner/admin/reviewer users.

### `POST /api/v1/approvals/{approval_id}/decision?org_id=<uuid>`

Body:

```json
{
  "decision": "approved",
  "notes": "Policy and order verified",
  "modified_parameters": null
}
```

The reviewer identity always comes from the JWT. The client cannot impersonate another reviewer by submitting a `reviewer_id`.

### `GET /api/v1/ops/executions/{execution_id}?org_id=<uuid>`

Returns the execution state plus every step's input, output, status, latency and error.

### `GET /api/v1/ops/audit?org_id=<uuid>&limit=50`

Returns the most recent audit events for the organization.

## Demo ingestion

`POST /api/v1/demo/orgs/{org_slug}/events` remains a deliberately lightweight demo endpoint. It is intended for local demonstrations and should not be treated as the production webhook surface; API-key and signature verification are not implemented. It requires login and organization membership.

### `POST /api/v1/demo/run?org_id=<uuid>`

Authenticated demo control. Body:

```json
{"scenario":"low_risk_refund"}
```

Supported scenarios: `low_risk_refund`, `high_risk_refund`, `rejected_refund`, `failed_refund`, `support_inquiry`, `lead_inquiry`. The endpoint uses the seeded mock integrations and is intended for portfolio demonstrations.


## Worker-only reliability

`threshold.retry_due_actions` is a Celery task rather than an HTTP endpoint. It processes persisted actions whose `next_retry_at` has passed.

## Queue and retry

`POST /api/v1/demo/orgs/{org_slug}/events/queue` accepts the same event body
as synchronous ingestion and returns a task ID with HTTP 202.
`GET /api/v1/ops/tasks/{task_id}` requires login and returns coarse task state
only; task ownership is not tenant-mapped. Broker transport was not tested in this review.

`POST /api/v1/ops/executions/{execution_id}/retry?org_id=<uuid>` requires
reviewer permission and skips the backoff delay, while respecting the circuit
and attempt limit. Only failed workflows with a retryable action are eligible.

The `/api/v1/demo/approvals/{approval_id}/decision` compatibility route uses the
same validation and decision handler as the canonical approval route. Use
`modified_parameters` only with `decision=modified`, supplying both an order number
and a valid amount. Repeated decisions return HTTP 409.
