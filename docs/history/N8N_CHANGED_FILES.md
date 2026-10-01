> Historical report. Statements, test counts, environment limits, and next steps
> describe the milestone or review recorded below. Current implementation and
> evidence are in [Scope](../SCOPE.md) and [Verification](../VERIFICATION.md).

# Historical n8n merge inventory — September 30, 2026

This inventory accompanied the supplied archive. It describes that merge relative
to its frontend-overhaul base, not the later GitHub import. Current import changes
and retained fixes are summarized in [IMPORT_REPORT](IMPORT_REPORT.md).

## Added files

- `MERGE_REPORT.md` (packaging report, now summarized in `docs/IMPORT_REPORT.md`)
- `START_HERE_N8N.md`
- `backend/app/services/outcomes.py`
- `backend/scripts/setup_n8n_bridge.py`
- `backend/tests/test_n8n_bridge.py`
- `backend/tests/test_n8n_http_delivery.py`
- `backend/tests/unit/test_n8n_outcomes.py`
- `docs/N8N_CHANGED_FILES.md`
- `docs/N8N_INTEGRATION.md`
- `docs/N8N_VERIFICATION.md`
- `integrations/n8n/01_submit_refund.json`
- `integrations/n8n/02_sync_outcome_to_hubspot.json`
- `integrations/n8n/sample_intake.json`
- `scripts/check_n8n_templates.cjs`

## Modified files relative to frontend-overhaul

- `.env.example`
- `.github/workflows/ci.yml`
- `README.md`
- `backend/app/ai/providers.py`
- `backend/app/api/approvals.py`
- `backend/app/api/auth.py`
- `backend/app/api/commercial.py`
- `backend/app/api/demo.py`
- `backend/app/api/ops.py`
- `backend/app/api/organizations.py`
- `backend/app/api/webhooks.py`
- `backend/app/api/workspace.py`
- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/core/middleware.py`
- `backend/app/core/security.py`
- `backend/app/core/webhooks.py`
- `backend/app/integrations/providers.py`
- `backend/app/integrations/shopify.py`
- `backend/app/main.py`
- `backend/app/models/__init__.py`
- `backend/app/models/action.py`
- `backend/app/models/approval.py`
- `backend/app/models/billing.py`
- `backend/app/models/delivery.py`
- `backend/app/models/domain.py`
- `backend/app/models/event.py`
- `backend/app/models/organization.py`
- `backend/app/models/security.py`
- `backend/app/models/workflow.py`
- `backend/app/services/beta_readiness.py`
- `backend/app/services/commercial.py`
- `backend/app/workers/tasks.py`
- `backend/app/workflows/engine.py`
- `backend/app/workflows/primitives.py`
- `backend/scripts/beta_readiness.py`
- `backend/scripts/provider_simulator.py`
- `backend/scripts/staging_smoke.py`
- `backend/scripts/validate_beta_providers.py`
- `backend/tests/test_ecommerce_vertical.py`
- `backend/tests/test_m7_security.py`
- `backend/tests/test_m8_beta_gate.py`
- `backend/tests/test_saas_milestone2.py`
- `backend/tests/unit/test_provider_simulator.py`
- `docker-compose.yml`
- `docs/ARCHITECTURE.md`

Beyond the n8n merge, backend changes fix existing Ruff/type findings. Most extra
files had import/formatting cleanup only. See [IMPORT_REPORT](IMPORT_REPORT.md)
for historical verification scope and the safeguards retained during import.
