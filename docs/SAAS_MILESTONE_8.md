# SaaS Milestone 8 — Private Beta Validation

Milestone 8 is a proof milestone, not a feature-expansion milestone. Threshold now has a repeatable launch gate and validation tooling that distinguishes code presence from operational evidence.

## Beta readiness gate

Owners/admins can inspect `GET /api/v1/ops/beta-readiness?org_id=<uuid>`.

The report emits `pass`, `warn`, or `block` checks and never returns secret values. It evaluates:

- staging/production runtime mode and HTTPS/CORS posture;
- configured AI provider and server-side credential presence;
- Shopify OAuth plus external token-vault handoff;
- Stripe Billing configuration (warning for a free beta, not a blocker);
- recent declared restore-drill evidence;
- tested alerting declaration and a named incident owner;
- Alembic schema revision;
- Redis and Celery worker reachability when runtime probes are enabled;
- deterministic refund policy presence;
- enabled Shopify integration and resolvable secret references;
- exactly one live refund executor;
- human reviewer coverage;
- workspace entitlement status;
- unresolved UNKNOWN/dead-letter actions;
- failed/dead-letter incoming events and outbox messages.

The application does **not** automatically mark operational evidence complete. `BETA_ALERTING_CONFIGURED`, `BETA_LAST_RESTORE_DRILL_AT`, and `BETA_ONCALL_OWNER` are human-operated evidence declarations and should only be set after the corresponding proof has actually happened.

## Repeatable validation tools

### In-container launch gate

```bash
python -m scripts.beta_readiness --org-id <uuid>
```

Exit code `2` means blockers remain. Add `--strict-warnings` to make warnings fail the command as well.

### Deployed staging smoke test

```bash
BETA_BASE_URL=https://staging.example.com \
BETA_OWNER_EMAIL=owner@example.com \
BETA_OWNER_PASSWORD='...' \
BETA_ORG_ID=<uuid> \
python -m scripts.staging_smoke --output beta-smoke-report.json
```

The smoke test is non-destructive: liveness, readiness, login, identity, and the tenant beta-readiness gate.

### Read-only live provider probes

```bash
python -m scripts.validate_beta_providers --org-id <uuid>
```

This performs a Shopify GraphQL shop identity query and a Stripe account read. It refuses a `sk_live_` Stripe key by default so the private-beta proof path cannot casually hit live money infrastructure.

### Local failure injection

`docker-compose.validation.yml` adds a local idempotent refund-provider simulator. It supports deterministic cases based on the order number:

- `RETRY-ONCE-*`: first call returns `503`, later idempotent retry succeeds;
- `HARD-FAIL-*`: permanent `422` provider rejection;
- `UNKNOWN-RECOVER-*`: provider records the refund and intentionally delays the response so a short-timeout client can reconcile the committed result.

The simulator is validation-only and must never be used as a production provider.

## GitHub private-beta workflow

`.github/workflows/private-beta.yml` is manually triggered against an HTTPS staging deployment. It uses environment-protected owner credentials and uploads the JSON smoke report as workflow evidence.

## What still requires real infrastructure

This repository can define and test the gates, but it cannot manufacture evidence. Before real customer data or money is enabled, an operator must still run:

1. full PostgreSQL/Redis/Celery API suite;
2. production Compose or the actual deployment equivalent;
3. Shopify development-store connection and webhook delivery;
4. Stripe test-mode connectivity and refund/reconciliation test;
5. external secret-vault write/read lifecycle;
6. backup restore drill and recorded timestamp;
7. tested alert delivery and incident ownership;
8. failure-injection exercise with worker/provider interruptions;
9. staging smoke workflow with zero blockers;
10. explicit go/no-go review.

## Live-execution gate and kill switch

Non-demo workspaces no longer gain live provider authority merely because an integration exists. The organization must have `live_execution_enabled=true` in its tenant settings.

An owner enables it through the beta-readiness control only when the live readiness probe returns zero blockers. Owners/admins can disable it immediately without satisfying any gate.

Both action creation **and the durable worker** enforce the switch. This matters because disabling a workspace after an action has been queued must still stop the provider call. A blocked queued action becomes a known FAILED state without contacting the provider; after the incident is resolved and live execution is re-enabled, the operator may retry it.

The archived M8 staging report describes manual live retries entering the durable
worker path. Canonical source at `99d6d03` differs: the manual retry endpoint calls
`WorkflowEngine.retry_failed_execution`, which invokes the configured provider
directly. New non-demo action intents and worker recovery use the outbox. Consolidate
and test these paths before relying on the staging report's manual-retry boundary.

## Development versus production containers

`backend/Dockerfile` installs runtime dependencies and uses a non-root user.
`backend/Dockerfile.dev` also exists and installs development dependencies, but
the current `docker-compose.yml` uses the default `backend/Dockerfile`; it does
not select the development image. Follow [TESTING](TESTING.md) to install test/lint
tools in a disposable local container before using the Make targets.

`docker-compose.prod.yml` uses the runtime image with its production runtime
restrictions. The presence of a development Dockerfile alone does not make
`make test` work in a container that lacks development dependencies.
