# A refund request with an inspectable decision trail

**Status:** simulated business case using fictional retail data. No real payments,
customers, deployment, time savings, or revenue results are claimed.

## The operational problem

A refund message leaves an operator with several questions: which order does it
refer to, is the amount valid, does the order meet policy, and who must approve it?
When processing fails or the same request arrives twice, the operator also needs
to distinguish a new request from a repeated attempt.

Threshold is a local demonstration of that decision process. The operator can see
why a workflow completed, paused, or failed, then take the supported next action.

## The implemented scenario

The seeded retailer has a 30-day refund window and a $75 automatic limit. Eligibility
also requires a completed order, a valid nonnegative age, and a positive amount in
whole cents no larger than the order total.

| Example input | Expected reference behavior | Evidence to inspect |
|---|---|---|
| Refund order ORD-1002 for $65 | Automatically completes when the seeded order is still eligible. | Policy/risk outputs, action result, verification, and audit events. |
| Refund order ORD-1001 for $89.99 | Pauses for review because it exceeds the automatic limit. | Approval queue, reviewer decision, and resumed execution. |
| Request $150 against the $89.99 order | Pauses for review; Reject cancels it. | Failed eligibility and cancellation. Approving the invalid amount still fails action validation. |
| Inject a one-time timeout on a fresh demo order | Fails, retains a retryable action, then supports mock recovery. | Failure details and the same action identifier before and after retry. |

These outcomes are defined by the code and covered by existing regression cases.
Current and previously reported execution evidence are separated in
[VERIFICATION](VERIFICATION.md).

## Why the controls matter

- **Extraction proposes fields.** Deterministic code checks order, amount, policy,
  and risk. The model's confidence score does not authorize a refund.
- **Review has a durable record.** A reviewer can approve, modify through the API,
  or reject. Authorization comes from organization membership and reviewer role.
- **Request and action identity are distinct.** Repeating the event key reuses a
  workflow; a new event with the same successful order/amount reuses the action.
- **A failure stays visible.** The execution retains its context and error. An
  eligible retry updates the existing action instead of inserting a new refund.

## What a client can evaluate

The repository provides a concrete example of Python API development, structured
input processing, policy-based approval, and debugging of stateful automation.
The dashboard makes the underlying decisions inspectable by an operator.

A scoped engagement could apply these techniques to one internal workflow, with
agreed inputs, review rules, outputs, and failure behavior. Connecting a real
payment service, CRM, or email system would require additional implementation and
testing; those integrations are not demonstrated here.

## Results and limitations

The result is a portfolio prototype with a configured demo, source, tests, and
documented boundaries. There are no measured business outcomes. The dashboard's
hours-saved metric assumes 15 minutes per automatically completed execution;
reused actions can still contribute completed executions, so it is not verified ROI.

Default classification and extraction use deterministic mock rules. Optional live
provider adapters exist, but this presentation makes no live-model accuracy claim.
Refund effects and notifications remain local database records. There is no
cumulative payment ledger, customer/order ownership check, or proven external
delivery/crash-recovery guarantee.

[Follow the demo](DEMO.md) · [Inspect the architecture](ARCHITECTURE.md) ·
[Read failure behavior](RELIABILITY.md)
