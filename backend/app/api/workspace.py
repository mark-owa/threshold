from decimal import Decimal
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.tenancy import get_active_organization, get_org_membership, require_org_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    AuditLogEntry,
    IntegrationConfig,
    OrganizationMember,
    Policy,
    User,
    WebhookEndpoint,
    WorkflowDefinition,
)
from app.integrations.providers import validate_live_endpoint
from app.models.enums import IntegrationProvider, MemberRole, RequestCategory

router = APIRouter(prefix=f"{get_settings().API_V1_PREFIX}/workspace", tags=["workspace"])




class GenericRestIntegrationRequest(BaseModel):
    base_url: str = Field(min_length=8, max_length=1000)
    refund_path: str = Field(default="/refunds", min_length=1, max_length=500)
    verify_path_template: str = Field(
        default="/refunds/{provider_operation_id}", min_length=1, max_length=500
    )
    reconcile_path_template: str = Field(
        default="/refunds/by-idempotency/{idempotency_key}", min_length=1, max_length=500
    )
    credential_ref: str | None = Field(default=None, min_length=1, max_length=255)
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    failure_threshold: int = Field(default=3, ge=1, le=20)
    recovery_timeout_seconds: int = Field(default=30, ge=5, le=3600)
    is_enabled: bool = True


class ShopifyIntegrationRequest(BaseModel):
    shop_domain: str = Field(min_length=8, max_length=255)
    credential_ref: str = Field(min_length=1, max_length=255)
    webhook_secret_ref: str | None = Field(default=None, min_length=1, max_length=255)
    api_version: str = Field(default="2026-07", min_length=7, max_length=20)
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    refund_enabled: bool = False
    is_enabled: bool = True


class StripeIntegrationRequest(BaseModel):
    credential_ref: str = Field(min_length=1, max_length=255)
    api_version: str | None = Field(default=None, max_length=64)
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    refund_enabled: bool = True
    is_enabled: bool = True


class WebhookEndpointRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    signing_secret_ref: str = Field(min_length=1, max_length=255)
    allowed_clock_skew_seconds: int = Field(default=300, ge=30, le=3600)


class RefundPolicyRequest(BaseModel):
    title: str = Field(default="Refund policy", min_length=2, max_length=255)
    content: str = Field(
        default="Refunds are eligible only inside the configured window and within the order total.",
        min_length=10,
        max_length=4000,
    )
    refund_window_days: int = Field(default=30, ge=1, le=365)
    max_auto_refund_usd: Decimal = Field(default=Decimal("50.00"), ge=0, le=1_000_000)


def _serialize_policy(row: Policy) -> dict:
    return {
        "id": str(row.id),
        "category": row.category.value,
        "title": row.title,
        "content": row.content,
        "structured_rules": row.structured_rules,
        "updated_at": row.updated_at,
    }


@router.get("/onboarding")
def onboarding_status(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    organization = get_active_organization(org_id, user.id, db)
    membership = get_org_membership(org_id, user.id, db)
    has_refund_policy = (
        db.scalar(
            select(func.count())
            .select_from(Policy)
            .where(
                Policy.organization_id == org_id,
                Policy.category == RequestCategory.REFUND_REQUEST,
            )
        )
        or 0
    ) > 0
    member_count = (
        db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(OrganizationMember.organization_id == org_id)
        )
        or 0
    )
    enabled_integrations = (
        db.scalar(
            select(func.count())
            .select_from(IntegrationConfig)
            .where(
                IntegrationConfig.organization_id == org_id,
                IntegrationConfig.is_enabled.is_(True),
            )
        )
        or 0
    )

    steps = [
        {
            "key": "workspace",
            "title": "Workspace created",
            "complete": True,
            "description": "Your tenant boundary and owner membership are active.",
        },
        {
            "key": "refund_policy",
            "title": "Configure refund policy",
            "complete": has_refund_policy,
            "description": "Set the deterministic eligibility window and automatic-refund limit.",
        },
        {
            "key": "team",
            "title": "Add a reviewer",
            "complete": member_count >= 2,
            "description": "Invite at least one teammate who can review high-risk actions.",
        },
        {
            "key": "integration",
            "title": "Connect a provider",
            "complete": enabled_integrations > 0,
            "description": "Connect the first external business system in the connector milestone.",
        },
    ]
    completed = sum(1 for step in steps if step["complete"])
    return {
        "organization_id": str(organization.id),
        "plan": organization.plan,
        "role": membership.role.value,
        "steps": steps,
        "completed_steps": completed,
        "total_steps": len(steps),
        "percent_complete": round(completed / len(steps) * 100),
        "ready_for_live_execution": has_refund_policy and enabled_integrations > 0,
    }


@router.get("/workflows")
def list_workflows(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    rows = db.scalars(
        select(WorkflowDefinition)
        .where(
            or_(
                WorkflowDefinition.organization_id == org_id,
                WorkflowDefinition.organization_id.is_(None),
            )
        )
        .order_by(WorkflowDefinition.name.asc(), WorkflowDefinition.version.desc())
    ).all()
    return [
        {
            "id": str(row.id),
            "key": row.key,
            "name": row.name,
            "description": row.description,
            "version": row.version,
            "trigger_category": row.trigger_category.value,
            "is_active": row.is_active,
            "scope": "workspace" if row.organization_id == org_id else "template",
        }
        for row in rows
    ]


@router.get("/policies")
def list_policies(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    rows = db.scalars(
        select(Policy)
        .where(Policy.organization_id == org_id)
        .order_by(Policy.category.asc())
    ).all()
    return [_serialize_policy(row) for row in rows]


@router.put("/refund-policy")
def upsert_refund_policy(
    request: RefundPolicyRequest,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required to edit policy",
    )
    policy = db.scalar(
        select(Policy).where(
            Policy.organization_id == org_id,
            Policy.category == RequestCategory.REFUND_REQUEST,
        )
    )
    created = policy is None
    if policy is None:
        policy = Policy(
            organization_id=org_id,
            category=RequestCategory.REFUND_REQUEST,
            title=request.title.strip(),
            content=request.content.strip(),
            structured_rules={},
        )
        db.add(policy)

    policy.title = request.title.strip()
    policy.content = request.content.strip()
    policy.structured_rules = {
        "refund_window_days": request.refund_window_days,
        "max_auto_refund_usd": float(request.max_auto_refund_usd),
    }
    db.add(
        AuditLogEntry(
            organization_id=org_id,
            workflow_execution_id=None,
            event_type="policy.created" if created else "policy.updated",
            actor_type="human",
            actor_id=str(user.id),
            payload={
                "category": RequestCategory.REFUND_REQUEST.value,
                "structured_rules": policy.structured_rules,
            },
        )
    )
    db.commit()
    db.refresh(policy)
    return _serialize_policy(policy)


@router.get("/integrations")
def list_integrations(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    rows = db.scalars(
        select(IntegrationConfig)
        .where(IntegrationConfig.organization_id == org_id)
        .order_by(IntegrationConfig.provider.asc())
    ).all()
    return [
        {
            "id": str(row.id),
            "provider": row.provider.value,
            "is_enabled": row.is_enabled,
            "config": row.config,
            "credential_configured": bool(row.credential_ref),
            "health": "circuit_open" if row.circuit_open_until else "available",
            "consecutive_failures": row.consecutive_failures,
            "failure_threshold": row.failure_threshold,
        }
        for row in rows
    ]


@router.put("/integrations/generic-rest")
def upsert_generic_rest_integration(
    request: GenericRestIntegrationRequest,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    organization = get_active_organization(org_id, user.id, db)
    require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required to manage integrations",
    )
    if organization.plan == "demo":
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Demo workspaces use isolated mock integrations")
    base_url = request.base_url.rstrip("/")
    validate_live_endpoint(base_url)
    for template in (request.refund_path, request.verify_path_template, request.reconcile_path_template):
        validate_live_endpoint(base_url + "/" + template.lstrip("/").replace("{provider_operation_id}", "probe").replace("{idempotency_key}", "probe"))

    row = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.organization_id == org_id,
            IntegrationConfig.provider == IntegrationProvider.GENERIC_REST,
        )
    )
    created = row is None
    if row is None:
        row = IntegrationConfig(
            organization_id=org_id,
            provider=IntegrationProvider.GENERIC_REST,
            config={},
        )
        db.add(row)
    row.config = {
        "base_url": base_url,
        "refund_path": request.refund_path,
        "verify_path_template": request.verify_path_template,
        "reconcile_path_template": request.reconcile_path_template,
        "timeout_seconds": request.timeout_seconds,
    }
    row.credential_ref = request.credential_ref
    row.failure_threshold = request.failure_threshold
    row.recovery_timeout_seconds = request.recovery_timeout_seconds
    row.is_enabled = request.is_enabled
    db.add(
        AuditLogEntry(
            organization_id=org_id,
            workflow_execution_id=None,
            event_type="integration.created" if created else "integration.updated",
            actor_type="human",
            actor_id=str(user.id),
            payload={
                "provider": IntegrationProvider.GENERIC_REST.value,
                "base_url": base_url,
                "credential_configured": bool(request.credential_ref),
                "is_enabled": request.is_enabled,
            },
        )
    )
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "provider": row.provider.value,
        "is_enabled": row.is_enabled,
        "config": row.config,
        "credential_configured": bool(row.credential_ref),
        "health": "circuit_open" if row.circuit_open_until else "available",
    }


@router.put("/integrations/shopify")
def upsert_shopify_integration(
    request: ShopifyIntegrationRequest,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    organization = get_active_organization(org_id, user.id, db)
    require_org_roles(org_id, user.id, db, {MemberRole.OWNER, MemberRole.ADMIN}, detail="Admin permission required to manage integrations")
    if organization.plan == "demo":
        raise HTTPException(status_code=409, detail="Demo workspaces use isolated mock integrations")
    shop_domain = request.shop_domain.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
    if not shop_domain.endswith(".myshopify.com"):
        raise HTTPException(status_code=422, detail="Shopify domain must end with .myshopify.com")
    validate_live_endpoint(f"https://{shop_domain}/admin/api/{request.api_version}/graphql.json")
    row = db.scalar(select(IntegrationConfig).where(IntegrationConfig.organization_id == org_id, IntegrationConfig.provider == IntegrationProvider.SHOPIFY))
    created = row is None
    if row is None:
        row = IntegrationConfig(organization_id=org_id, provider=IntegrationProvider.SHOPIFY, config={})
        db.add(row)
    row.config = {
        "shop_domain": shop_domain,
        "api_version": request.api_version,
        "timeout_seconds": request.timeout_seconds,
        "webhook_secret_ref": request.webhook_secret_ref,
        "refund_enabled": request.refund_enabled,
    }
    row.credential_ref = request.credential_ref
    row.is_enabled = request.is_enabled
    db.add(AuditLogEntry(organization_id=org_id, workflow_execution_id=None, event_type="integration.created" if created else "integration.updated", actor_type="human", actor_id=str(user.id), payload={"provider": "shopify", "shop_domain": shop_domain, "refund_enabled": request.refund_enabled, "credential_configured": True}))
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "provider": row.provider.value, "is_enabled": row.is_enabled, "config": row.config, "credential_configured": True, "webhook_path": f"{get_settings().API_V1_PREFIX}/webhooks/shopify/{org_id}"}


@router.put("/integrations/stripe")
def upsert_stripe_integration(
    request: StripeIntegrationRequest,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    organization = get_active_organization(org_id, user.id, db)
    require_org_roles(org_id, user.id, db, {MemberRole.OWNER, MemberRole.ADMIN}, detail="Admin permission required to manage integrations")
    if organization.plan == "demo":
        raise HTTPException(status_code=409, detail="Demo workspaces use isolated mock integrations")
    validate_live_endpoint("https://api.stripe.com/v1/refunds")
    row = db.scalar(select(IntegrationConfig).where(IntegrationConfig.organization_id == org_id, IntegrationConfig.provider == IntegrationProvider.STRIPE))
    created = row is None
    if row is None:
        row = IntegrationConfig(organization_id=org_id, provider=IntegrationProvider.STRIPE, config={})
        db.add(row)
    row.config = {"api_version": request.api_version, "timeout_seconds": request.timeout_seconds, "refund_enabled": request.refund_enabled}
    row.credential_ref = request.credential_ref
    row.is_enabled = request.is_enabled
    db.add(AuditLogEntry(organization_id=org_id, workflow_execution_id=None, event_type="integration.created" if created else "integration.updated", actor_type="human", actor_id=str(user.id), payload={"provider": "stripe", "refund_enabled": request.refund_enabled, "credential_configured": True}))
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "provider": row.provider.value, "is_enabled": row.is_enabled, "config": row.config, "credential_configured": True}


@router.post("/shopify/orders/sync")
def sync_shopify_order(
    order_number: str,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(org_id, user.id, db, {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.REVIEWER}, detail="Workspace membership required")
    integration = db.scalar(select(IntegrationConfig).where(IntegrationConfig.organization_id == org_id, IntegrationConfig.provider == IntegrationProvider.SHOPIFY, IntegrationConfig.is_enabled.is_(True)))
    if integration is None:
        raise HTTPException(status_code=409, detail="Shopify integration is not configured")
    from app.integrations.shopify import ShopifyAdminClient, upsert_shopify_order
    snapshot = ShopifyAdminClient(integration).fetch_order(order_number)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Shopify order not found")
    order = upsert_shopify_order(db, org_id, snapshot)
    db.add(AuditLogEntry(organization_id=org_id, workflow_execution_id=None, event_type="shopify.order_synced", actor_type="human", actor_id=str(user.id), payload={"order_id": str(order.id), "order_number": order.order_number, "external_order_id": order.external_order_id}))
    db.commit()
    return {"id": str(order.id), "order_number": order.order_number, "external_order_id": order.external_order_id, "currency": order.currency, "total": float(order.amount_usd), "refunded": float(order.refunded_amount_usd), "refundable": float(max(Decimal("0.00"), order.amount_usd - order.refunded_amount_usd)), "payment_reference_configured": bool(order.payment_reference)}


@router.get("/webhook-endpoints")
def list_webhook_endpoints(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    rows = db.scalars(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.organization_id == org_id)
        .order_by(WebhookEndpoint.created_at.asc())
    ).all()
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "endpoint_key": row.endpoint_key,
            "path": f"{get_settings().API_V1_PREFIX}/webhooks/{row.endpoint_key}",
            "signing_secret_ref": row.signing_secret_ref,
            "is_active": row.is_active,
            "allowed_clock_skew_seconds": row.allowed_clock_skew_seconds,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/webhook-endpoints", status_code=201)
def create_webhook_endpoint(
    request: WebhookEndpointRequest,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id, user.id, db, {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required to create webhook endpoints",
    )
    endpoint = WebhookEndpoint(
        organization_id=org_id,
        name=request.name.strip(),
        endpoint_key=secrets.token_urlsafe(24),
        signing_secret_ref=request.signing_secret_ref.strip(),
        allowed_clock_skew_seconds=request.allowed_clock_skew_seconds,
        is_active=True,
    )
    db.add(endpoint)
    db.flush()
    db.add(
        AuditLogEntry(
            organization_id=org_id, workflow_execution_id=None,
            event_type="webhook.endpoint_created", actor_type="human", actor_id=str(user.id),
            payload={"endpoint_id": str(endpoint.id), "name": endpoint.name},
        )
    )
    db.commit()
    db.refresh(endpoint)
    return {
        "id": str(endpoint.id),
        "name": endpoint.name,
        "endpoint_key": endpoint.endpoint_key,
        "path": f"{get_settings().API_V1_PREFIX}/webhooks/{endpoint.endpoint_key}",
        "signing_secret_ref": endpoint.signing_secret_ref,
        "is_active": endpoint.is_active,
    }


@router.delete("/webhook-endpoints/{endpoint_id}", status_code=204)
def disable_webhook_endpoint(
    endpoint_id: UUID,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id, user.id, db, {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required to disable webhook endpoints",
    )
    endpoint = db.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.organization_id == org_id,
        )
    )
    if endpoint is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    endpoint.is_active = False
    db.add(
        AuditLogEntry(
            organization_id=org_id, workflow_execution_id=None,
            event_type="webhook.endpoint_disabled", actor_type="human", actor_id=str(user.id),
            payload={"endpoint_id": str(endpoint.id), "name": endpoint.name},
        )
    )
    db.commit()
