# Threshold demonstration and recording guide

The current screenshots and approval GIF were recorded on **2026-10-01**, at source
commit `94cca1901628ee219359872ed28df0799ffebbf4`. The application uses mock AI/payments and fictional seeded data.
Recovery was manual, with Worker and Beat absent. A permanent narrated walkthrough
is not published.

## Existing media

| Asset | File |
| --- | --- |
| Dashboard | [Overview](assets/current-demo/dashboard-overview.png) |
| Human review | [Approval required](assets/current-demo/approval-required.png) |
| Execution steps | [Execution inspector](assets/current-demo/execution-inspector.png) |
| Manual recovery | [Retry recovery](assets/current-demo/retry-recovery.png) |
| Approval animation | [Approval GIF](assets/current-demo/approval-demo.gif) |
| Source and checked IDs | [Capture evidence](assets/current-demo/capture-evidence.json) |

The [capture run](https://github.com/mark-owa/threshold/actions/runs/36811368664) checks browser sign-in, session reload, scenario execution,
approval confirmation, and retry. API responses confirm final state and the same
action ID in failure/recovery audit events. This does not verify scheduled broker
delivery, live payments, or real n8n/HubSpot.

The older September 19 media remains under `assets/demo/`. Its [original capture
evidence](assets/demo/capture-evidence.json) describes the earlier dashboard.

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
| 0:00–0:20 | Show the dashboard and open **Scenarios**. | “Threshold demonstrates how an internal refund request can move through policy checks, human review, and observable recovery. The retailer and all payment effects here are simulated.” |
| 0:20–0:55 | Select **Run scenario** under **Low-risk refund**. Open its execution and inspect rules, risk, action, and verification outputs. | “This $65 request refers to an eligible seeded order. The configured automatic limit is $75. The system validates the amount and records a mock refund and its outcome.” |
| 0:55–1:35 | Run **High-risk refund**. Open Approvals, approve the request, and inspect its execution. | “This $89.99 request exceeds the automatic limit. The workflow pauses. An authorized reviewer decides whether it should continue; the action still validates the order and amount.” |
| 1:35–2:20 | Run **Provider failure**. Open its execution, trigger retry, and inspect the recovered action. | “This scenario creates a separate demo order and injects one timeout. I am triggering recovery manually. The retry updates the same action row and records success; no real payment request is sent.” |
| 2:20–2:45 | Show the execution timeline and audit feed. | “Request identity and business-action identity are separate. Repeated delivery can reuse an execution, while a new request for the same successful order and amount can reuse an action.” |
| 2:45–3:00 | Return to the project overview. | “This is a local prototype. Payments and notifications are mocked. Real-provider delivery, crash recovery, and production payment safety would need additional work.” |

The failed step's error is visible in the dashboard; its output does not display
the failed action identifier. Before recording, use the existing authenticated
`GET /api/v1/ops/audit?org_id=<organization-id>` endpoint to compare `action_id`
in the failure and retry event payloads. Canonical source currently emits
`action_retried_and_verified` for a successful manual retry; earlier captures used
the previous event naming. The dashboard audit feed displays event labels, not
their full payloads. Compare API payloads to confirm action identity.

After recovery, the execution is completed and the action is verified. The original
failed step remains red in the timeline; the provider attempts and audit trail
record the retry outcome.

## Optional second clip: rejection

Run **Refund likely to be rejected**. Explain that $150 exceeds the seeded order total.
Select **Reject** and show the cancelled execution. Approval is an operator decision;
the presence of an approval button does not make an invalid amount executable.

Keep modification demonstrations separate: the API supports modified parameters,
and the current dashboard includes a modify-and-approve form. The current capture does not exercise
modified approval parameters.

## Capture list

| Asset to refresh | What it must show | Existing destination |
|---|---|---|
| Overview screenshot | Authenticated dashboard with a small amount of relevant demo history. | `assets/current-demo/dashboard-overview.png` |
| Approval screenshot | The $89.99 request, pending approval, and proposed parameters. | `assets/current-demo/approval-required.png` |
| Execution screenshot | Completed workflow with readable rule/action/verification outputs. | `assets/current-demo/execution-inspector.png` |
| Recovery screenshot | Failure and verified recovery in the same execution. | `assets/current-demo/retry-recovery.png` |
| Short GIF | One approval progressing to completion, with a clear starting state. | `assets/current-demo/approval-demo.gif` |
| Full walkthrough | The real three-minute sequence above, with narration or readable captions. | Video attachment or approved video host; link only after upload succeeds. |

Refresh these assets against the current runtime and update the source commit in
capture evidence. Preserve the distinction between recorded results and intended
behavior; the architecture SVG is an illustration, not an application screenshot.

## Completion check

Confirm that the first scenario really completes, the second really pauses, the
reviewer decision is recorded, and the injected failure really recovers. Keep any
recording limitations in the verification record. Export a readable 2–4-minute
video, review it end to end, and verify its final link before adding it to the README.
