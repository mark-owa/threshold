from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.webhooks import webhook_secret_value
from app.integrations.providers import _credential_value
from app.models import (
    ActionExecution,
    BillingAccount,
    IncomingEvent,
    IntegrationConfig,
    Organization,
    OrganizationMember,
    OutboxMessage,
    Policy,
)
from app.models.enums import (
    ActionStatus,
    EventProcessingStatus,
    IntegrationProvider,
    MemberRole,
    OutboxStatus,
    RequestCategory,
)

EXPECTED_SCHEMA_REVISION = "d7a9b123e5f7"

ReadinessLevel = Literal["pass", "warn", "block"]


@dataclass(frozen=True)
class ReadinessCheck:
    key: str
    title: str
    level: ReadinessLevel
    detail: str
    category: str

    def to_dict(self) -> dict:
        return asdict(self)


def _check(
    key: str, title: str, level: ReadinessLevel, detail: str, category: str
) -> ReadinessCheck:
    return ReadinessCheck(key=key, title=title, level=level, detail=detail, category=category)


def configuration_checks(settings: Settings | None = None) -> list[ReadinessCheck]:
    """Checks that are safe to run without touching tenant data or external APIs."""
    settings = settings or get_settings()
    checks: list[ReadinessCheck] = []

    beta_env = settings.APP_ENV in {"staging", "production"}
    checks.append(
        _check(
            "runtime_environment",
            "Staging/production runtime",
            "pass" if beta_env else "block",
            f"APP_ENV={settings.APP_ENV}. Private beta must not run with development defaults.",
            "runtime",
        )
    )

    checks.append(
        _check(
            "https_public_url",
            "HTTPS public application URL",
            "pass" if settings.PUBLIC_APP_URL.startswith("https://") else "block",
            settings.PUBLIC_APP_URL,
            "security",
        )
    )

    checks.append(
        _check(
            "cors_scope",
            "Restricted CORS origins",
            "pass"
            if settings.cors_origins_list and "*" not in settings.cors_origins_list
            else "block",
            ", ".join(settings.cors_origins_list) or "No CORS origins configured",
            "security",
        )
    )
    runtime_secrets_strong = (
        len(settings.SECRET_KEY) >= 32 and len(settings.WEBHOOK_SIGNING_SECRET) >= 32
    )
    checks.append(
        _check(
            "runtime_secret_strength",
            "Strong application/webhook secrets",
            "pass" if runtime_secrets_strong else "block",
            "SECRET_KEY and WEBHOOK_SIGNING_SECRET satisfy the minimum length."
            if runtime_secrets_strong
            else "SECRET_KEY and WEBHOOK_SIGNING_SECRET must both be at least 32 characters.",
            "security",
        )
    )

    ai_credential_present = (
        settings.AI_PROVIDER == "openai" and bool(settings.OPENAI_API_KEY)
    ) or (settings.AI_PROVIDER == "anthropic" and bool(settings.ANTHROPIC_API_KEY))
    if settings.AI_PROVIDER == "mock":
        ai_level: ReadinessLevel = "warn" if settings.BETA_ALLOW_MOCK_AI else "block"
        ai_detail = (
            "Mock AI is enabled; set BETA_ALLOW_MOCK_AI=true only for a "
            "non-customer validation environment."
        )
    elif ai_credential_present:
        ai_level = "pass"
        ai_detail = f"{settings.AI_PROVIDER} is configured with a server-side credential."
    else:
        ai_level = "block"
        ai_detail = f"AI_PROVIDER={settings.AI_PROVIDER} but its credential is missing."
    checks.append(_check("ai_provider", "AI provider configured", ai_level, ai_detail, "runtime"))

    oauth_ready = bool(
        settings.SHOPIFY_CLIENT_ID
        and settings.SHOPIFY_CLIENT_SECRET
        and settings.OAUTH_SECRET_SINK_URL
    )
    checks.append(
        _check(
            "shopify_oauth_vault",
            "Shopify OAuth and token vault",
            "pass" if oauth_ready else "block",
            "OAuth client and server-side token sink are configured."
            if oauth_ready
            else (
                "SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET, and "
                "OAUTH_SECRET_SINK_URL are required for merchant onboarding."
            ),
            "integrations",
        )
    )

    billing_ready = bool(
        settings.BILLING_STRIPE_SECRET_REF
        and settings.BILLING_STRIPE_WEBHOOK_SECRET_REF
        and settings.STRIPE_STARTER_PRICE_ID
        and settings.STRIPE_BUSINESS_PRICE_ID
    )
    checks.append(
        _check(
            "billing_configuration",
            "Stripe Billing configuration",
            "pass" if billing_ready else "warn",
            "Billing checkout, webhook, and self-serve prices are configured."
            if billing_ready
            else (
                "Billing is incomplete. This does not block a free private "
                "beta, but paid signup must remain disabled."
            ),
            "commercial",
        )
    )

    restore_at = settings.BETA_LAST_RESTORE_DRILL_AT
    if restore_at:
        try:
            parsed = datetime.fromisoformat(restore_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            age = datetime.now(UTC) - parsed.astimezone(UTC)
            restore_fresh = (
                timedelta(0) <= age <= timedelta(days=settings.BETA_MAX_RESTORE_DRILL_AGE_DAYS)
            )
            detail = (
                f"Last restore drill: {parsed.astimezone(UTC).isoformat()} ({age.days} days ago)."
            )
        except ValueError:
            restore_fresh = False
            detail = "BETA_LAST_RESTORE_DRILL_AT is not a valid ISO-8601 timestamp."
    else:
        restore_fresh = False
        detail = "No restore-drill evidence is declared."
    checks.append(
        _check(
            "restore_drill",
            "Recent backup restore drill",
            "pass" if restore_fresh else "block",
            detail,
            "operations",
        )
    )

    checks.append(
        _check(
            "alerting",
            "Alerting configured",
            "pass" if settings.BETA_ALERTING_CONFIGURED else "block",
            "Operational alerts are declared configured."
            if settings.BETA_ALERTING_CONFIGURED
            else "Set BETA_ALERTING_CONFIGURED=true only after production alerts have been tested.",
            "operations",
        )
    )
    checks.append(
        _check(
            "oncall_owner",
            "Named incident owner",
            "pass" if settings.BETA_ONCALL_OWNER.strip() else "block",
            settings.BETA_ONCALL_OWNER.strip() or "No on-call/incident owner declared.",
            "operations",
        )
    )
    return checks


def _db_schema_check(db: Session) -> ReadinessCheck:
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    except Exception as exc:  # pragma: no cover - exercised in live beta gate
        return _check(
            "schema_revision",
            "Database schema at expected revision",
            "block",
            f"Could not read alembic_version: {exc.__class__.__name__}",
            "data",
        )
    if revision == EXPECTED_SCHEMA_REVISION:
        return _check(
            "schema_revision", "Database schema at expected revision", "pass", revision, "data"
        )
    return _check(
        "schema_revision",
        "Database schema at expected revision",
        "block",
        f"Database={revision!s}; expected={EXPECTED_SCHEMA_REVISION}",
        "data",
    )


def _redis_check(settings: Settings) -> ReadinessCheck:
    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        )
        client.ping()
        return _check("redis", "Redis reachable", "pass", "Redis responded to PING.", "runtime")
    except Exception as exc:  # pragma: no cover - exercised in live beta gate
        return _check(
            "redis",
            "Redis reachable",
            "block",
            f"Redis unavailable: {exc.__class__.__name__}",
            "runtime",
        )


def _celery_check() -> ReadinessCheck:
    try:
        from app.workers.celery_app import celery_app

        replies = celery_app.control.inspect(timeout=1.0).ping() or {}
        if replies:
            workers = ", ".join(sorted(replies))
            return _check("celery_workers", "Celery workers reachable", "pass", workers, "runtime")
        return _check(
            "celery_workers",
            "Celery workers reachable",
            "block",
            "No worker responded to Celery ping.",
            "runtime",
        )
    except Exception as exc:  # pragma: no cover - exercised in live beta gate
        return _check(
            "celery_workers",
            "Celery workers reachable",
            "block",
            f"Worker probe failed: {exc.__class__.__name__}",
            "runtime",
        )


def tenant_checks(
    db: Session, organization_id: UUID, settings: Settings | None = None
) -> list[ReadinessCheck]:
    settings = settings or get_settings()
    checks: list[ReadinessCheck] = []
    organization = db.get(Organization, organization_id)
    if organization is None or not organization.is_active:
        return [
            _check(
                "organization",
                "Workspace active",
                "block",
                "Workspace does not exist or is disabled.",
                "tenant",
            )
        ]
    checks.append(
        _check(
            "organization",
            "Workspace active",
            "pass",
            f"{organization.name} ({organization.plan})",
            "tenant",
        )
    )
    live_enabled = bool((organization.settings or {}).get("live_execution_enabled"))
    checks.append(
        _check(
            "live_execution_switch",
            "Live execution switch",
            "pass" if live_enabled else "warn",
            "Live provider execution is enabled for this workspace."
            if live_enabled
            else (
                "Live provider execution is disabled. Enable it only after "
                "this gate has no blockers."
            ),
            "tenant",
        )
    )

    policy = db.scalar(
        select(Policy).where(
            Policy.organization_id == organization_id,
            Policy.category == RequestCategory.REFUND_REQUEST,
        )
    )
    policy_ready = bool(policy and policy.structured_rules)
    checks.append(
        _check(
            "refund_policy",
            "Deterministic refund policy",
            "pass" if policy_ready else "block",
            "Refund rules are persisted."
            if policy_ready
            else (
                "Configure refund window and automatic-refund limits before "
                "enabling live execution."
            ),
            "tenant",
        )
    )

    integrations = db.scalars(
        select(IntegrationConfig).where(
            IntegrationConfig.organization_id == organization_id,
            IntegrationConfig.is_enabled.is_(True),
        )
    ).all()
    shopify = next(
        (row for row in integrations if row.provider == IntegrationProvider.SHOPIFY), None
    )
    checks.append(
        _check(
            "shopify_integration",
            "Shopify store connected",
            "pass" if shopify else "block",
            str((shopify.config or {}).get("shop_domain"))
            if shopify
            else "No enabled Shopify integration.",
            "integrations",
        )
    )
    if shopify:
        shopify_secret = _credential_value(shopify.credential_ref)
        webhook_ref = str((shopify.config or {}).get("webhook_secret_ref") or "")
        webhook_secret = webhook_secret_value(webhook_ref) if webhook_ref else None
        checks.append(
            _check(
                "shopify_credentials",
                "Shopify server-side credentials resolve",
                "pass" if shopify_secret and webhook_secret else "block",
                "Admin token and webhook secret references resolve without exposing their values."
                if shopify_secret and webhook_secret
                else (
                    "Shopify Admin API and webhook secret references must both "
                    "resolve in deployment secrets."
                ),
                "integrations",
            )
        )

    refund_integrations = [
        row
        for row in integrations
        if row.provider
        in {
            IntegrationProvider.SHOPIFY,
            IntegrationProvider.STRIPE,
            IntegrationProvider.GENERIC_REST,
        }
        and bool((row.config or {}).get("refund_enabled"))
    ]
    if len(refund_integrations) == 1:
        refund_provider = refund_integrations[0]
        credential_ok = bool(_credential_value(refund_provider.credential_ref))
        checks.append(
            _check(
                "refund_executor",
                "Exactly one live refund executor",
                "pass" if credential_ok else "block",
                f"{refund_provider.provider.value} selected and credential reference resolves."
                if credential_ok
                else (
                    f"{refund_provider.provider.value} is selected but its "
                    f"credential reference does not resolve."
                ),
                "integrations",
            )
        )
    else:
        checks.append(
            _check(
                "refund_executor",
                "Exactly one live refund executor",
                "block",
                (
                    f"Found {len(refund_integrations)} enabled refund executors; "
                    f"exactly one is required."
                ),
                "integrations",
            )
        )

    human_reviewers = (
        db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.role.in_(
                    [MemberRole.OWNER, MemberRole.ADMIN, MemberRole.REVIEWER]
                ),
            )
        )
        or 0
    )
    checks.append(
        _check(
            "reviewer_coverage",
            "Human reviewer coverage",
            "pass" if human_reviewers >= 2 else "warn",
            (
                f"{human_reviewers} member(s) can make approval decisions. "
                f"Two or more are recommended for beta coverage."
            ),
            "tenant",
        )
    )

    billing = db.scalar(
        select(BillingAccount).where(BillingAccount.organization_id == organization_id)
    )
    billing_ok = billing is not None and billing.subscription_status in {"trialing", "active"}
    checks.append(
        _check(
            "billing_state",
            "Workspace entitlement state",
            "pass" if billing_ok else "block",
            f"subscription_status={billing.subscription_status}"
            if billing
            else "No billing account exists.",
            "commercial",
        )
    )

    unknown_actions = (
        db.scalar(
            select(func.count())
            .select_from(ActionExecution)
            .where(
                ActionExecution.organization_id == organization_id,
                ActionExecution.status.in_([ActionStatus.UNKNOWN, ActionStatus.DEAD_LETTER]),
            )
        )
        or 0
    )
    checks.append(
        _check(
            "unresolved_actions",
            "No unresolved external-action incidents",
            "pass" if unknown_actions == 0 else "block",
            f"{unknown_actions} UNKNOWN/dead-letter action(s).",
            "recovery",
        )
    )

    dead_events = (
        db.scalar(
            select(func.count())
            .select_from(IncomingEvent)
            .where(
                IncomingEvent.organization_id == organization_id,
                IncomingEvent.processing_status == EventProcessingStatus.DEAD_LETTER,
            )
        )
        or 0
    )
    failed_events = (
        db.scalar(
            select(func.count())
            .select_from(IncomingEvent)
            .where(
                IncomingEvent.organization_id == organization_id,
                IncomingEvent.processing_status == EventProcessingStatus.FAILED,
            )
        )
        or 0
    )
    event_level: ReadinessLevel = "block" if dead_events else "warn" if failed_events else "pass"
    checks.append(
        _check(
            "event_failures",
            "Inbound event pipeline healthy",
            event_level,
            f"dead_letter={dead_events}, failed={failed_events}",
            "recovery",
        )
    )

    dead_outbox = (
        db.scalar(
            select(func.count())
            .select_from(OutboxMessage)
            .where(
                OutboxMessage.organization_id == organization_id,
                OutboxMessage.status == OutboxStatus.DEAD_LETTER,
            )
        )
        or 0
    )
    failed_outbox = (
        db.scalar(
            select(func.count())
            .select_from(OutboxMessage)
            .where(
                OutboxMessage.organization_id == organization_id,
                OutboxMessage.status == OutboxStatus.FAILED,
            )
        )
        or 0
    )
    outbox_level: ReadinessLevel = "block" if dead_outbox else "warn" if failed_outbox else "pass"
    checks.append(
        _check(
            "outbox_health",
            "Durable delivery pipeline healthy",
            outbox_level,
            f"dead_letter={dead_outbox}, failed={failed_outbox}",
            "recovery",
        )
    )
    return checks


def build_beta_readiness(
    db: Session,
    organization_id: UUID,
    *,
    probe_runtime: bool = True,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    checks = configuration_checks(settings)
    checks.append(_db_schema_check(db))
    if probe_runtime:
        checks.append(_redis_check(settings))
        checks.append(_celery_check())
    checks.extend(tenant_checks(db, organization_id, settings))

    blockers = sum(1 for check in checks if check.level == "block")
    warnings = sum(1 for check in checks if check.level == "warn")
    passed = sum(1 for check in checks if check.level == "pass")
    return {
        "ready": blockers == 0,
        "generated_at": datetime.now(UTC).isoformat(),
        "organization_id": str(organization_id),
        "summary": {"pass": passed, "warn": warnings, "block": blockers},
        "checks": [check.to_dict() for check in checks],
    }
