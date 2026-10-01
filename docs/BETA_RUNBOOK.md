# Threshold Private Beta Runbook

This is the go/no-go sequence for enabling a real merchant workspace.

## 1. Deploy staging

Use production-equivalent PostgreSQL, Redis, worker, beat, HTTPS ingress, and a real secret manager. Apply migrations before accepting traffic.

```bash
alembic upgrade head
```

Current canonical schema head: `e8b0c234f6a8`. Confirm it with `alembic heads`.

## 2. Configure the merchant tenant

The merchant must have:

- an active refund policy;
- Shopify connected;
- Shopify Admin token and webhook secret references resolving from deployment secrets;
- exactly one live refund executor (Shopify or Stripe);
- at least one person capable of reviewing approvals;
- active/trialing entitlement state.

## 3. Prove read-only provider connectivity

Run from the backend environment:

```bash
python -m scripts.validate_beta_providers --org-id "$BETA_ORG_ID"
```

Use Stripe test mode. Do not pass `--allow-live-stripe-key` for private-beta validation.

## 4. Run failure injection locally/staging-equivalent

Bring up the validation provider overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.validation.yml up -d --build
```

Configure a validation-only Generic REST integration with:

```text
base_url: http://provider-simulator:8090
refund_path: /refunds
verify_path_template: /refunds/{provider_operation_id}
reconcile_path_template: /refunds/by-idempotency/{idempotency_key}
credential_ref: LOCAL_SIMULATOR
```

Exercise normal, transient, permanent, and ambiguous-provider cases. Confirm that UNKNOWN actions require reconciliation and are never blindly replayed.

## 5. Prove backup recovery

Run a real backup and isolated restore drill using the supplied scripts. Only after the restored database has been verified, set:

```text
BETA_LAST_RESTORE_DRILL_AT=<successful ISO-8601 UTC timestamp>
```

Never set the timestamp merely to satisfy the launch gate.

## 6. Prove alerting and ownership

Trigger at least one real alert path, verify delivery to the responsible operator, then set:

```text
BETA_ALERTING_CONFIGURED=true
BETA_ONCALL_OWNER=<named person or rotation>
```

## 7. Run the launch gate

```bash
python -m scripts.beta_readiness --org-id "$BETA_ORG_ID"
```

`block=0` is required. Warnings require explicit review.

## 8. Run deployed smoke validation

```bash
python -m scripts.staging_smoke --output beta-smoke-report.json
```

Archive the report with the release/deployment record.

## 9. Go / no-go

Go only when all of these are true:

- no beta-readiness blockers;
- no UNKNOWN/dead-letter customer actions;
- no dead-letter outbox records;
- provider test-mode validation succeeds;
- restore drill succeeded recently;
- alerts are tested;
- an incident owner is named;
- rollback procedure and data backup are available.

If any one of those conditions is false, the merchant should remain in sandbox/staging mode.

## Emergency stop

Owners and admins can use **Beta readiness → Emergency disable**. The server-side kill switch is checked again by the worker immediately before a live provider call, so an already queued but not-yet-executed action is blocked rather than sent externally.

After the cause is understood, clear readiness blockers, re-enable live execution as an owner, and explicitly retry only actions whose previous provider outcome is known. UNKNOWN actions must still be reconciled first.
