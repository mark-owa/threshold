# Threshold + n8n: first integration slice

## Scope and ownership

Threshold owns refund policy, approvals, action execution and reconciliation.
n8n owns delivery of a normalized input and HubSpot synchronization. HubSpot owns
the customer-service ticket. This release uses mock refunds and one existing,
dedicated test ticket per request. It does not create tickets, send email, add GHL,
or replace Threshold's engine. The existing frontend is preserved.

Confirmed `completed` and `cancelled` refund executions generate final outcomes.
Completion requires `context.verified == true`. Pending approval, failed, unknown,
and waiting-external states do not generate final CRM updates in this version.
Use Threshold's dashboard for those states. CRM synchronization can fail even when
a refund succeeded; replay only the delivery, never the refund.

## Files

- `integrations/n8n/01_submit_refund.json`: manual, signed request submission.
- `integrations/n8n/02_sync_outcome_to_hubspot.json`: authenticated/signed outcome → ticket PATCH → acknowledgment.
- `backend/app/services/outcomes.py`: transactional outcome insertion and outbound delivery.
- `backend/scripts/setup_n8n_bridge.py`: demo-only ingress endpoint registration.
- `scripts/check_n8n_templates.cjs`: local structural/JavaScript checks, not an n8n runtime test.

## 1. Prepare local Threshold and two secrets

Complete `START_HERE_N8N.md` first. Generate two different random secrets using a
password manager (at least 32 characters; 64 hexadecimal characters work well).
In local `.env`, set these keys. Never paste the values into chat or commit `.env`:

```dotenv
THRESHOLD_WEBHOOK_SECRET__N8N_INTAKE=YOUR_FIRST_RANDOM_SECRET
THRESHOLD_WEBHOOK_SECRET__N8N_OUTCOME=YOUR_SECOND_RANDOM_SECRET
```

The first secret signs n8n → Threshold. The second authenticates and signs
Threshold → n8n. They are separate credentials. Restart/recreate processes after
changing environment configuration:

```powershell
docker compose up -d --force-recreate backend worker beat
docker compose exec backend python -m scripts.setup_n8n_bridge
```

The helper prints the organization UUID and signed webhook path. It reuses an
existing named endpoint. It never enables real refunds. If it reports an existing
disabled endpoint, inspect the reason instead of silently enabling it.

## 2. Prepare one HubSpot test ticket

In your existing practice HubSpot account, create a ticket for a fictional refund
request and record its ID. Associate it with your test contact if useful. A ticket
represents a request; a contact represents a person. Do not reuse one ticket for
unrelated requests, and do not use a customer's job title as a refund status field.

Record the HubSpot account/portal ID and the **internal stage IDs** for resolved
and rejected/closed states. These are account configuration values; do not assume
example IDs match your account. You can inspect ticket pipelines via the HubSpot
UI or `GET /crm/v3/pipelines/tickets` with authorized credentials. If only one
closed stage exists, both terminal outcomes may map there for the demo; Threshold
still distinguishes completion from rejection. Use separate stages when available.

Your n8n HubSpot Bearer credential must have ticket read/write permission supported
by your app/account; the earlier contact-only credential scopes may be insufficient.
Do not purchase an upgrade merely for this test. If the ticket feature/scope is
unavailable, pause the real-CRM demonstration and use a controlled test receiver.

Keep marketing/outreach triggers disabled for these synthetic ticket updates.
Repeated PATCH requests can still affect downstream automations depending on their
configuration even when the ticket's final stored value is unchanged.

### HubSpot API preflight

Before publishing the outcome workflow, use a separate manual n8n HTTP Request
node to read the dedicated fictional ticket. This check does not change its stage.
Select the same HTTP Bearer Auth credential used by `Update Existing HubSpot Ticket`.
Keep the credential in n8n; do not put its value in the URL, workflow JSON, or chat.

| Setting | Value |
| --- | --- |
| Method | `GET` |
| URL | `https://api.hubapi.com/crm/v3/objects/tickets/TICKET_ID` |
| Query parameter | `properties=subject,hs_pipeline,hs_pipeline_stage` |
| Authentication | Generic Credential Type → HTTP Bearer Auth |
| Response | JSON; include status/headers; disable redirects |

Substitute only the dedicated ticket's ID. Success is HTTP 200 with a JSON body
whose `id` matches that ticket and whose `properties` describe the expected
fictional request. Record its `hs_pipeline` and current `hs_pipeline_stage`.
Read `https://api.hubapi.com/crm/v3/pipelines/tickets/PIPELINE_ID` with that pipeline
ID to identify its internal stages, or inspect the same pipeline in HubSpot settings.
Both configured terminal stages must belong to that ticket's pipeline.

`app.hubspot.com` URLs open the HubSpot website. Do not copy a browser record URL
into an API node. HTTP 200 containing `<!doctype html>` or a HubSpot page is not a
successful ticket API response. Check the full request URL and any redirect, then
rerun the read before submitting anything to Threshold.

If the API returns an error, inspect its JSON body as well as the status:

| Result | Next action |
| --- | --- |
| 401 | Check the selected Bearer credential and token validity in n8n. |
| 403 with `MISSING_SCOPES` | Inspect the API's required scopes and the credential's app/account permissions. Contact access alone does not establish ticket access. |
| 404 | Check the ticket ID and that the credential belongs to the intended practice account. |
| 429 or transient 5xx | Respect the retry guidance; do not treat the preflight as passed. |
| HTML, missing `id`, or another ticket ID | Check the URL and response format; do not proceed on status alone. |

The [n8n HubSpot credential reference](https://docs.n8n.io/integrations/builtin/credentials/hubspot/)
lists the `tickets` scope for ticket operations. Verify the requirements for the
credential type and account actually in use rather than guessing scope names.
A successful GET proves read access only; write access remains unverified until
the signed outcome updates the dedicated ticket and receives a matching acknowledgment.

## 3. Import the OUTCOME workflow first

Import `02_sync_outcome_to_hubspot.json` into n8n. It is inactive and has no secrets.

1. `Receive Outcome`: select a **Header Auth** credential with header name
   `X-Threshold-Token` and value equal to `N8N_OUTCOME`'s secret.
2. `Calculate Outcome Signature`: select a **Crypto** credential whose **Hmac Secret**
   equals that same outcome secret. This uses Crypto node version 2. If your instance
   lacks the credential-backed Crypto node, update/check compatibility; do not embed
   the secret in a Code node or exported workflow.
3. `Validate and Map Outcome`: replace the four non-secret placeholders: Threshold
   organization UUID, HubSpot portal ID, completed stage ID, cancelled stage ID.
4. `Update Existing HubSpot Ticket`: select your HubSpot Bearer credential.
5. Preserve Raw Body on the Webhook, `Using Respond to Webhook Node`, and the final
   Respond node. Do not acknowledge on receipt.
6. Publish/activate it and copy the **production** webhook URL. The test URL only
   listens temporarily and is unsuitable for background delivery.

The receiver checks Header Auth first, calculates HMAC over the exact raw body,
checks a five-minute timestamp window, validates organization/account identifiers,
and allows only the two final states. It updates the existing ticket's
`hs_pipeline_stage`. It returns `{ "ok": true, "delivery_id": "..." }` only after
HubSpot returns HTTP 200 with the expected ticket ID. A generic 200/empty response
is not an acknowledgment. Invalid signatures stop before the CRM call.

Imports are templates: inspect the nodes in your installed n8n version. Current
Crypto parameters were checked against upstream source; the templates have not
been executed inside your n8n account.

## 4. Configure Threshold's outcome destination

In `.env`, replace the existing empty `N8N_OUTCOME_TARGETS={}` line with one JSON
line (substitute the real non-secret values):

```dotenv
N8N_OUTCOME_TARGETS='{"ORG_UUID":{"url":"https://YOUR-N8N-HOST/webhook/threshold-refund-outcome","secret_ref":"n8n_outcome","hubspot_portal_id":"PORTAL_ID"}}'
```

Add the exact n8n hostname to the existing comma-separated
`INTEGRATION_ALLOWED_HOSTS`. Preserve hosts needed by other integrations. Example:

```dotenv
INTEGRATION_ALLOWED_HOSTS=YOUR-N8N-HOST
```

Recreate backend, worker, and beat with the earlier command. These three processes
must load the same target configuration and secret. URLs come only from trusted
operator configuration, never from incoming customer JSON. Redirects are disabled.
Use HTTPS for Cloud connections. Configure the destination **before** submitting
a CRM-linked request. Old completed events without an outcome row are not backfilled.

## 5. Import the INTAKE workflow

Import `01_submit_refund.json`. Keep it manual during this demonstration.

1. In `Demo Request`, set your Threshold HTTPS webhook URL, HubSpot portal ID,
   and existing test ticket ID. Keep the synthetic refund text initially.
2. In `Sign Intake`, choose a Crypto credential with the **intake** Hmac Secret.
3. Execute the workflow once and inspect `Check Acceptance`.

For n8n Cloud, the URL must be reachable over HTTPS. `localhost` refers to n8n's
own machine, not your laptop. Never expose a full development server with seeded
public credentials just to make the webhook reachable. Use a restricted development
proxy route or properly configured staging environment.

The request body is serialized once. That exact string is both signed and sent.
The stable ID is `hubspot:PORTAL_ID:ticket:TICKET_ID`, also included as `external_id`
in the signed body. Threshold verifies that these identifiers match for CRM inputs.
An incoming event is scoped by organization and webhook endpoint. Use one bridge
endpoint per organization for this first demonstration.

Expected response: HTTP 202, `accepted: true`, `duplicate: false`. This confirms
persistence for processing, not successful refund execution. Then observe the
Threshold execution, queued outcome, n8n receiver, and HubSpot ticket.

## 6. Prove the business behavior

| Test | Expected evidence |
|---|---|
| New low-risk synthetic refund | Accepted; Threshold verified completion; ticket updated; outcome SENT |
| Identical request again | 202 duplicate; same event; no second business action/outcome |
| Same ticket/event ID, changed amount | 409 EVENT_ID_CONFLICT; original payload preserved |
| High-risk refund using a fresh ticket/order | Threshold waits for approval; no final CRM update yet |
| Reviewer rejects | Cancelled outcome; ticket mapped to rejection stage; no refund action |
| Reviewer approves | Verified mock action, then completion outcome |
| Invalid input signature | 401 from Threshold, no event inserted |
| Wrong CRM portal or mismatched event/body ID | 422 before persistence |
| Wrong outcome credential/signature | No HubSpot call; delivery failure visible |
| HubSpot 429/503 | Delivery retries; refund stays completed |
| HubSpot 401/403/404 | Delivery dead-lettered for configuration repair |
| Empty/wrong delivery acknowledgment | Not SENT; bounded retry then dead-letter |
| n8n updates HubSpot but acknowledgment is lost | Retry PATCHes the same ticket and same stage; no new refund |

Use separate test tickets for separate business requests. For repeated refund
experiments, inspect remaining refundable amount or reset only a disposable demo
workspace deliberately; never delete a real database to make a demo pass.

## 7. Delivery and recovery semantics

The final outcome row is inserted in the same PostgreSQL transaction as the final
business state. It uses a deterministic UUID primary key with `ON CONFLICT DO NOTHING`.
Repeated lifecycle hooks cannot add another row for the same execution/outcome.
No database migration is needed for this slice: it reuses `outbox_messages`.

Celery Beat invokes the existing outbox dispatcher. For this topic the dispatcher
performs the HTTP delivery and waits for the receiver's acknowledgment. It does not
mark SENT merely because another background task was queued. The HTTP timeout is
kept below the configured lease. Stale publisher leases are recoverable; completion
updates require the worker still to own the lease.

Delivery is **at least once**, not exactly once. A crash after CRM success but
before marking SENT causes redelivery. The receiver deliberately uses PATCH on a
stable existing ticket, and does not create contacts, notes, tickets, payments, or
messages. It has no durable receiver inbox, so this design must be extended before
adding a non-idempotent CRM operation or downstream notification.

Retries are limited to eight automatic delivery attempts. Transport failures,
invalid acknowledgments, 408, 429, and selected transient 5xx statuses retry.
Other HTTP statuses dead-letter immediately. The delay follows the existing bounded
outbox exponential schedule and respects numeric Retry-After seconds up to an hour;
HTTP-date Retry-After and jitter are not implemented in this slice.

Use the authenticated recovery API/dashboard to inspect failed/dead-letter outbox
rows. The API is `GET /api/v1/ops/recovery?org_id=ORG_UUID`. After repairing configuration,
an authorized operator can use the existing
`POST /api/v1/ops/outbox/MESSAGE_ID/requeue?org_id=ORG_UUID` route. Requeue the outcome
message, not the event or refund action. Existing requeue behavior retains attempt
history. Exhausted messages may require another manual intervention if the next
attempt also fails. No polling or callback can grant a human approval.

Disabling/removing the destination prevents new delivery attempts from succeeding;
existing messages become visible failures. Repair and requeue deliberately. Avoid
retargeting an organization's queued deliveries to a different HubSpot account.

## Security and evidence boundary

Credentials live in n8n credentials or Threshold environment secret references.
The exports contain placeholders only. Templates disable saved success/error/manual
execution data by default to reduce persistence of webhook authentication headers.
Check your instance's execution retention/redaction settings before real use.

This implementation does not prove live-provider readiness. It does not change
Threshold's existing payment safety gates. The 2026-10-01 CI passed 177 tests on
PostgreSQL 16, including bridge persistence checks. The suite also exercises a
real loopback HTTP receiver and the template harness checks 16 workflow/JavaScript
cases. These checks do not execute the exports in n8n or update a real HubSpot ticket.
Worker interruption tests and a live n8n/HubSpot demonstration remain required.
See [VERIFICATION](VERIFICATION.md) for dated evidence and [historical n8n checks](history/N8N_VERIFICATION.md)
for the earlier packaging review.

## Reference documentation checked during implementation

- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.crypto/
- https://docs.n8n.io/integrations/builtin/credentials/crypto/
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.respondtowebhook/
- https://docs.n8n.io/integrations/builtin/credentials/hubspot/
- https://developers.hubspot.com/docs/api-reference/legacy/crm/objects/tickets/guide
- https://developers.hubspot.com/docs/api-reference/crm-pipelines-v3/guide
