from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.core.config import Settings
from app.models import (
    BillingAccount,
    IntegrationConfig,
    Organization,
    OrganizationMember,
    Policy,
    User,
)
from app.models.enums import IntegrationProvider, MemberRole, RequestCategory
from app.services import beta_readiness
from app.services.beta_readiness import (
    EXPECTED_SCHEMA_REVISION,
    ReadinessCheck,
    _db_schema_check,
    build_beta_readiness,
    configuration_checks,
    tenant_checks,
)


def _settings(**overrides):
    values = {
        "APP_ENV": "staging",
        "SECRET_KEY": "s" * 40,
        "WEBHOOK_SIGNING_SECRET": "w" * 40,
        "PUBLIC_APP_URL": "https://threshold.example.com",
        "CORS_ORIGINS": "https://threshold.example.com",
        "AI_PROVIDER": "openai",
        "OPENAI_API_KEY": "test-key",
        "ANTHROPIC_API_KEY": "",
        "BETA_ALLOW_MOCK_AI": False,
        "SHOPIFY_CLIENT_ID": "client",
        "SHOPIFY_CLIENT_SECRET": "secret",
        "OAUTH_SECRET_SINK_URL": "https://vault.example.com/token",
        "BILLING_STRIPE_SECRET_REF": "billing",
        "BILLING_STRIPE_WEBHOOK_SECRET_REF": "billing-webhook",
        "STRIPE_STARTER_PRICE_ID": "price_starter",
        "STRIPE_BUSINESS_PRICE_ID": "price_business",
        "BETA_LAST_RESTORE_DRILL_AT": datetime.now(UTC).isoformat(),
        "BETA_ALERTING_CONFIGURED": True,
        "BETA_ONCALL_OWNER": "ops@example.com",
    }
    values.update(overrides)
    return Settings(**values)


def test_readiness_check_and_configuration_branches():
    check = ReadinessCheck("k", "title", "pass", "detail", "category")
    assert check.to_dict()["key"] == "k"

    healthy = {row.key: row for row in configuration_checks(_settings())}
    assert healthy["runtime_environment"].level == "pass"
    assert healthy["https_public_url"].level == "pass"
    assert healthy["cors_scope"].level == "pass"
    assert healthy["runtime_secret_strength"].level == "pass"
    assert healthy["ai_provider"].level == "pass"
    assert healthy["shopify_oauth_vault"].level == "pass"
    assert healthy["billing_configuration"].level == "pass"
    assert healthy["restore_drill"].level == "pass"
    assert healthy["alerting"].level == "pass"
    assert healthy["oncall_owner"].level == "pass"

    mock_allowed = {
        row.key: row
        for row in configuration_checks(_settings(AI_PROVIDER="mock", BETA_ALLOW_MOCK_AI=True))
    }
    assert mock_allowed["ai_provider"].level == "warn"

    blocked = {
        row.key: row
        for row in configuration_checks(
            _settings(
                APP_ENV="development",
                PUBLIC_APP_URL="http://threshold.example.com",
                CORS_ORIGINS="*",
                SECRET_KEY="short",
                WEBHOOK_SIGNING_SECRET="short",
                AI_PROVIDER="anthropic",
                ANTHROPIC_API_KEY="",
                SHOPIFY_CLIENT_ID="",
                SHOPIFY_CLIENT_SECRET="",
                OAUTH_SECRET_SINK_URL="",
                BILLING_STRIPE_SECRET_REF="",
                BILLING_STRIPE_WEBHOOK_SECRET_REF="",
                STRIPE_STARTER_PRICE_ID="",
                STRIPE_BUSINESS_PRICE_ID="",
                BETA_LAST_RESTORE_DRILL_AT="not-a-date",
                BETA_ALERTING_CONFIGURED=False,
                BETA_ONCALL_OWNER="",
            )
        )
    }
    assert blocked["runtime_environment"].level == "block"
    assert blocked["https_public_url"].level == "block"
    assert blocked["cors_scope"].level == "block"
    assert blocked["runtime_secret_strength"].level == "block"
    assert blocked["ai_provider"].level == "block"
    assert blocked["shopify_oauth_vault"].level == "block"
    assert blocked["billing_configuration"].level == "warn"
    assert blocked["restore_drill"].level == "block"
    assert blocked["alerting"].level == "block"
    assert blocked["oncall_owner"].level == "block"

    stale = {
        row.key: row
        for row in configuration_checks(
            _settings(BETA_LAST_RESTORE_DRILL_AT=(datetime.now(UTC) - timedelta(days=365)).isoformat())
        )
    }
    assert stale["restore_drill"].level == "block"


class _RevisionResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDB:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def execute(self, statement):
        if self.error:
            raise self.error
        return _RevisionResult(self.value)


def test_schema_check_success_mismatch_and_failure():
    assert _db_schema_check(_FakeDB(EXPECTED_SCHEMA_REVISION)).level == "pass"
    mismatch = _db_schema_check(_FakeDB("old-revision"))
    assert mismatch.level == "block"
    assert "expected" in mismatch.detail
    failed = _db_schema_check(_FakeDB(error=RuntimeError("db down")))
    assert failed.level == "block"
    assert "RuntimeError" in failed.detail


def _add_member(db_session, org, email, role):
    user = User(email=email, hashed_password="unused", full_name=email)
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=role,
        )
    )


def test_tenant_checks_block_missing_workspace(db_session):
    checks = tenant_checks(db_session, Organization().id, _settings())
    assert checks[0].key == "organization"
    assert checks[0].level == "block"


def test_tenant_checks_and_build_readiness_for_configured_workspace(db_session, monkeypatch):
    org = Organization(
        name="Ready Workspace",
        slug="ready-workspace",
        plan="trial",
        settings={"live_execution_enabled": True},
    )
    db_session.add(org)
    db_session.flush()
    _add_member(db_session, org, "owner-ready@example.com", MemberRole.OWNER)
    _add_member(db_session, org, "reviewer-ready@example.com", MemberRole.REVIEWER)

    db_session.add(
        Policy(
            organization_id=org.id,
            category=RequestCategory.REFUND_REQUEST,
            title="Refund policy",
            content="Refund completed orders.",
            structured_rules={"refund_window_days": 30, "max_auto_refund_usd": 75},
        )
    )
    db_session.add(
        IntegrationConfig(
            organization_id=org.id,
            provider=IntegrationProvider.SHOPIFY,
            credential_ref="SHOPIFY_READY",
            config={
                "shop_domain": "ready.myshopify.com",
                "webhook_secret_ref": "SHOPIFY_WEBHOOK",
                "refund_enabled": True,
            },
            is_enabled=True,
        )
    )
    db_session.add(
        BillingAccount(
            organization_id=org.id,
            subscription_status="active",
        )
    )
    db_session.commit()

    monkeypatch.setattr(beta_readiness, "_credential_value", lambda ref: "secret")
    monkeypatch.setattr(beta_readiness, "webhook_secret_value", lambda ref: "webhook-secret")

    checks = {row.key: row for row in tenant_checks(db_session, org.id, _settings())}
    assert checks["organization"].level == "pass"
    assert checks["live_execution_switch"].level == "pass"
    assert checks["refund_policy"].level == "pass"
    assert checks["shopify_integration"].level == "pass"
    assert checks["shopify_credentials"].level == "pass"
    assert checks["refund_executor"].level == "pass"
    assert checks["reviewer_coverage"].level == "pass"
    assert checks["billing_state"].level == "pass"
    assert checks["unresolved_actions"].level == "pass"
    assert checks["event_failures"].level == "pass"
    assert checks["outbox_health"].level == "pass"

    monkeypatch.setattr(
        beta_readiness,
        "_db_schema_check",
        lambda db: ReadinessCheck(
            "schema_revision", "schema", "pass", EXPECTED_SCHEMA_REVISION, "data"
        ),
    )
    report = build_beta_readiness(
        db_session,
        org.id,
        probe_runtime=False,
        settings=_settings(),
    )
    assert report["ready"] is True
    assert report["summary"]["block"] == 0
    assert report["summary"]["pass"] > 0
    assert report["organization_id"] == str(org.id)


def test_tenant_checks_missing_policy_integration_and_billing(db_session):
    org = Organization(name="Blocked Workspace", slug="blocked-workspace", plan="trial")
    db_session.add(org)
    db_session.commit()

    checks = {row.key: row for row in tenant_checks(db_session, org.id, _settings())}
    assert checks["live_execution_switch"].level == "warn"
    assert checks["refund_policy"].level == "block"
    assert checks["shopify_integration"].level == "block"
    assert checks["refund_executor"].level == "block"
    assert checks["reviewer_coverage"].level == "warn"
    assert checks["billing_state"].level == "block"
