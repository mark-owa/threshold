from datetime import UTC, datetime

from app.core.config import Settings
from app.services.beta_readiness import configuration_checks


def _settings(**overrides):
    values = {
        "APP_ENV": "staging",
        "SECRET_KEY": "s" * 40,
        "WEBHOOK_SIGNING_SECRET": "w" * 40,
        "PUBLIC_APP_URL": "https://threshold.example.com",
        "CORS_ORIGINS": "https://threshold.example.com",
        "AI_PROVIDER": "mock",
        "BETA_ALLOW_MOCK_AI": True,
        "SHOPIFY_CLIENT_ID": "client",
        "SHOPIFY_CLIENT_SECRET": "secret",
        "OAUTH_SECRET_SINK_URL": "https://vault.example.com/token",
        "BETA_LAST_RESTORE_DRILL_AT": datetime.now(UTC).isoformat(),
        "BETA_ALERTING_CONFIGURED": True,
        "BETA_ONCALL_OWNER": "ops@example.com",
    }
    values.update(overrides)
    return Settings(**values)


def test_configuration_gate_blocks_development_runtime():
    checks = {check.key: check for check in configuration_checks(_settings(APP_ENV="development"))}
    assert checks["runtime_environment"].level == "block"


def test_configuration_gate_blocks_http_public_url():
    checks = {
        check.key: check
        for check in configuration_checks(_settings(PUBLIC_APP_URL="http://threshold.example.com"))
    }
    assert checks["https_public_url"].level == "block"


def test_configuration_gate_requires_restore_drill_evidence():
    checks = {
        check.key: check for check in configuration_checks(_settings(BETA_LAST_RESTORE_DRILL_AT=""))
    }
    assert checks["restore_drill"].level == "block"
