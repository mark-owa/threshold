from datetime import UTC, datetime

from app.core.config import Settings
from app.services.beta_readiness import configuration_checks


def _levels(checks):
    return {check.key: check.level for check in checks}


def test_beta_config_blocks_development_defaults():
    settings = Settings(
        APP_ENV="development",
        PUBLIC_APP_URL="http://localhost:5173",
        CORS_ORIGINS="*",
        AI_PROVIDER="mock",
        BETA_ALLOW_MOCK_AI=False,
        BETA_ALERTING_CONFIGURED=False,
        BETA_ONCALL_OWNER="",
        BETA_LAST_RESTORE_DRILL_AT="",
    )
    levels = _levels(configuration_checks(settings))
    assert levels["runtime_environment"] == "block"
    assert levels["https_public_url"] == "block"
    assert levels["cors_scope"] == "block"
    assert levels["ai_provider"] == "block"
    assert levels["restore_drill"] == "block"
    assert levels["alerting"] == "block"
    assert levels["oncall_owner"] == "block"


def test_beta_config_can_be_green_with_declared_operational_evidence():
    settings = Settings(
        APP_ENV="staging",
        SECRET_KEY="s" * 40,
        WEBHOOK_SIGNING_SECRET="w" * 40,
        PUBLIC_APP_URL="https://threshold.example.test",
        CORS_ORIGINS="https://threshold.example.test",
        AI_PROVIDER="openai",
        OPENAI_API_KEY="test-only-key",
        SHOPIFY_CLIENT_ID="client",
        SHOPIFY_CLIENT_SECRET="secret",
        OAUTH_SECRET_SINK_URL="https://vault.example.test/store",
        BILLING_STRIPE_SECRET_REF="BILLING",
        BILLING_STRIPE_WEBHOOK_SECRET_REF="BILLING_WEBHOOK",
        STRIPE_STARTER_PRICE_ID="price_start",
        STRIPE_BUSINESS_PRICE_ID="price_business",
        BETA_ALERTING_CONFIGURED=True,
        BETA_ONCALL_OWNER="ops@example.test",
        BETA_LAST_RESTORE_DRILL_AT=datetime.now(UTC).isoformat(),
    )
    checks = configuration_checks(settings)
    levels = _levels(checks)
    assert all(level != "block" for level in levels.values())
    assert levels["billing_configuration"] == "pass"
    assert levels["shopify_oauth_vault"] == "pass"
