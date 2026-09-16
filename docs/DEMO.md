# Threshold demonstration and recording guide

**Recording status:** script and capture plan prepared; no recorded video or product
screenshots are included yet. Use the real application, default mock provider, and
fictional seeded data. The architecture SVG is a diagram, not an application capture.

## Prepare the real application

Follow the root [README](../README.md), including its PowerShell alternative.
Use a fresh disposable demo database and keep `AI_PROVIDER=mock`. No paid model call
is needed. The dashboard is at http://localhost:5173.

The seed script skips an organization that already exists. Old seeded orders may
age out of the 30-day refund window; repeated ordinary demos may reuse a successful
action. Use a fresh disposable setup for a predictable first recording. Do not
delete a database containing work you need to keep.

For a clean manual retry demonstration, stop only the local demo's scheduler after
startup: `docker compose stop beat`. This prevents the minute-based automatic retry
from completing before it is shown. Restart it afterward with
`docker compose start beat`. State explicitly in the walkthrough that recovery is
being triggered manually. This does not demonstrate broker transport.

Sign in as `reviewer@acme-demo.example.com` using the public demo password from the
README. Keep the browser at a readable desktop size, close unrelated tabs, and
check that no terminal or settings panel exposes real credentials.

## Three-minute walkthrough

| Time | On-screen action | Suggested narration |
|---|---|---|
| 0:00–0:20 | Show the dashboard and controlled-demo controls. | “Threshold demonstrates how an internal refund request can move through policy checks, human review, and observable recovery. The retailer and all payment effects here are simulated.” |
| 0:20–0:55 | Click **Low-risk refund**. Show completion, then the rules, risk, execute, and verify outputs. | “This $65 request refers to an eligible seeded order. The configured automatic limit is $75. The system validates the amount and records a mock refund and its outcome.” |
| 0:55–1:35 | Click **High-risk refund**. Show the approval queue, then click **Approve** and inspect the result. | “This $89.99 request exceeds the automatic limit. The workflow pauses. An authorized reviewer decides whether it should continue; the action still validates the order and amount.” |
| 1:35–2:20 | Click **Failure + retry**. Show the error; click **Retry failed action** and show the successful retry output and its action identifier. | “This scenario creates a separate demo order and injects one timeout. I am triggering recovery manually. The retry updates the same action row and records success; no real payment request is sent.” |
| 2:20–2:45 | Show the execution timeline and audit feed. | “Request identity and business-action identity are separate. Repeated delivery can reuse an execution, while a new request for the same successful order and amount can reuse an action.” |
| 2:45–3:00 | Return to the project overview. | “This is a local prototype. Payments and notifications are mocked. Real-provider delivery, crash recovery, and production payment safety would need additional work.” |

The failed step's error is visible in the dashboard; its output does not display
the failed action identifier. Before recording, use the existing authenticated
`GET /api/v1/ops/audit?org_id=<organization-id>` endpoint to compare `action_id`
in the `action_failed` and `action_retried_and_succeeded` event payloads. The
successful retry's step output also includes the action ID. The dashboard audit
feed itself displays event labels, not their full payloads.

## Optional second clip: rejection

Click **Policy-failing refund**. Explain that $150 exceeds the seeded order total.
Select **Reject** and show the cancelled execution. Approval is an operator decision;
the presence of an approval button does not make an invalid amount executable.

Keep modification demonstrations separate: the API supports modified parameters,
but this dashboard only exposes Approve and Reject.

## Capture list

| Intended asset | What it must show | Destination after capture |
|---|---|---|
| Overview screenshot | Authenticated dashboard with a small amount of relevant demo history. | `assets/dashboard-overview.png` |
| Approval screenshot | The $89.99 request, pending approval, and proposed parameters. | `assets/approval-required.png` |
| Execution screenshot | Completed workflow with readable rule/action/verification outputs. | `assets/execution-inspector.png` |
| Recovery screenshot | The failed step plus successful retry steps in the same execution. | `assets/retry-recovery.png` |
| Short GIF | One approval progressing to completion, with a clear starting state. | `assets/approval-demo.gif` |
| Full walkthrough | The real three-minute sequence above, with narration or readable captions. | Video attachment or approved video host; link only after upload succeeds. |

These are planned filenames, not existing links. Do not replace missing captures
with invented interface screenshots or scripted playback of fabricated API results.
Confirm the runtime works first, then capture once and reuse the same assets in the
README and case study.

## Completion check

Confirm that the first scenario really completes, the second really pauses, the
reviewer decision is recorded, and the injected failure really recovers. Keep any
recording limitations in the verification record. Export a readable 2–4-minute
video, review it end to end, and verify its final link before adding it to the README.
