# Reliability model

Threshold demonstrates deduplication and observable recovery for database-only mock
actions. It does not establish at-least-once delivery to a real external provider.
There is no transactional outbox or provider reconciliation protocol.

## What happens when something goes wrong

| Condition | Implemented behavior | Boundary to explain |
|---|---|---|
| Same event key submitted again in one organization | Returns the existing workflow execution. | A different key is a new event; identical text alone does not deduplicate it. |
| New event asks for the same successful order/amount refund | Reuses the canonical action result. | No cumulative partial-refund ledger or external-provider guarantee. |
| Missing amount or failed automatic eligibility | Pauses for reviewer action when extraction succeeds. | An invalid provider result can fail extraction instead of reaching approval. |
| Reviewer rejects | Cancels the workflow and records the decision. | No refund action is created on this path. |
| Reviewer supplies invalid modified parameters | Fails the workflow before creating a refund action. | Modification is available through the API; the dashboard has Approve and Reject only. |
| One simulated action timeout | Retains a failed workflow and a scheduled retryable action. | This is an injected demo failure, not a real payment-provider timeout. |
| Retry succeeds | Updates the same action, clears retry/error state, and completes the workflow. | The demo retry records mock success; it does not contact a provider. |
| Attempt limit reached | Marks the action dead-letter and removes its retry schedule. | No replay UI; the one-time timeout scenario does not naturally demonstrate repeated outages. |
| Circuit open or integration disabled before action creation | Stops execution. | There is no action for the retry endpoint to recover; the request needs a new event after the cause is resolved. |
| Database or worker process unavailable | Processing or persistence can fail. | Durable broker delivery, process-kill recovery, and guaranteed audit persistence are not demonstrated. |

## Retry lifecycle

```text
Action executing
  -> failed
  -> RETRYING + next_retry_at
  -> Celery Beat selects due action
  -> retry
  -> succeeded + verification
  -> or DEAD_LETTER after max attempts
```

Backoff is deterministic and bounded. These delays make an action eligible;
the scheduled task polls once per minute, so they are not promises of wall-clock
retry timing. The helper supports the delays below;
the reference refund action permits three total attempts, including the initial one:

| Attempt | Delay |
|---:|---:|
| 1 | 1s |
| 2 | 2s |
| 3 | 4s |
| 4 | 8s |
| 5 | 16s |
| 6 | 32s |
| 7+ | 60s |

The action keeps the same idempotency key across retries. A successful existing action is reused rather than executed again.

## Circuit breaker

Each organization/provider integration tracks consecutive failures. After the configured failure threshold, the integration is opened until the recovery timeout elapses. During the open window, new action execution is rejected with `integration_circuit_open` rather than continuing to hammer a failing dependency. A successful execution resets the failure counter and closes the circuit.

## Dead-letter behavior

When `attempt_count >= max_attempts`, the action becomes `dead_letter`. The workflow remains failed and the dead-letter transition is written to the audit log. Operators can investigate the action without silently replaying a business side effect.

## Demo behavior

`simulate_failure_once` is a controlled test/demo flag. It intentionally produces a deterministic external timeout so the dashboard can demonstrate failure, retry scheduling, and recovery. It is not a production integration failure simulator.

## Worker behavior

`threshold.retry_due_actions` is scheduled every minute by Celery Beat. The task selects due retryable actions and delegates execution back to `WorkflowEngine.retry_failed_execution`. The API's manual retry path can force a retry for an authorized operator.

## Scope limits

All side effects are database-only mocks. An open circuit blocks new actions and
retry attempts; `force=True` skips the backoff delay but does not bypass that gate
or re-enable a disabled integration. A failure before an action row is created
(such as an open circuit) has no action to retry and needs resubmission as a new event.

Successful retries clear their schedule/error and update execution context and
approval results. Dead-letter rows remain failed for inspection; there is no replay UI.
The one-time timeout demo does not exercise repeated provider outages. Process-kill
recovery, durable broker delivery, and a real payment provider protocol remain unimplemented.
