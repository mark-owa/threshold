> Historical report. Statements, test counts, environment limits, and next steps
> describe the milestone or review recorded below. Current implementation and
> evidence are in [Scope](../SCOPE.md) and [Verification](../VERIFICATION.md).

# Threshold Private Beta Readiness Report — Milestone 8

## Verdict

**NO-GO for real customer data or money in the current validation environment.**

This is not a code-feature verdict. The private-beta launch gate is implemented, but several required operational proofs cannot be produced inside this container because the supporting runtime and external test accounts are unavailable.

## Evidence produced here

- Python application, scripts, and Alembic migrations compile successfully.
- Frontend `main.tsx` transpiles successfully with TypeScript.
- Shell scripts pass `bash -n` syntax validation.
- 23 dependency-light regression/validation tests pass.
- Provider simulator proves idempotent duplicate delivery, retry-once behavior, and reconciliation by idempotency key.
- Private-beta readiness configuration checks reject development runtime, insecure HTTP public URL, and missing restore-drill evidence.
- Live execution is guarded at both action creation and durable worker execution.
- Owners can enable live execution only after a zero-blocker runtime readiness gate; owners/admins can disable it immediately.

## Runtime evidence blocked in this environment

The current container does not provide:

- Docker / Docker Compose
- PostgreSQL server/client
- Redis server/client package
- Celery package/runtime
- bcrypt package
- psycopg package
- installed frontend npm dependency tree
- Shopify development-store credentials
- Stripe test-mode credentials
- external secret-vault service

Therefore the following must still be executed in staging before private beta:

1. Full FastAPI/PostgreSQL test suite.
2. Redis/Celery worker and beat startup.
3. Production Compose (or equivalent deployment) health/readiness checks.
4. Transactional-outbox delivery under worker interruption.
5. Stale lease recovery and UNKNOWN-action reconciliation exercise.
6. Shopify development-store OAuth, signed webhook, order sync, and uninstall lifecycle.
7. Stripe test-mode subscription and refund/reconciliation flow.
8. External secret-vault write/read lifecycle.
9. PostgreSQL backup and restore drill.
10. Tested alert delivery with named incident owner.
11. Deployed staging smoke workflow with zero readiness blockers.

## Launch control implemented in M8

The application exposes a tenant-scoped beta-readiness report and live execution control. Live external actions require `organization.settings.live_execution_enabled=true`.

The switch is checked twice:

1. before a live `ActionExecution` is created; and
2. inside the durable action worker immediately before provider execution.

This means an administrator can disable live execution after an action has been queued and Threshold will still refuse to call the provider.

## Go criteria

A workspace may be considered for private beta only when its full runtime readiness report contains **zero blockers**, staging smoke tests pass, restore/alerting evidence is current, provider probes succeed in test/development accounts, and a human go/no-go review approves the release.
