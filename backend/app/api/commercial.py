from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.tenancy import get_active_organization, require_org_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.providers import validate_live_endpoint
from app.models import (
    AuditLogEntry,
    BillingAccount,
    ExternalWebhookReceipt,
    IntegrationConfig,
    OAuthStateNonce,
    Organization,
    UsageCounter,
    User,
)
from app.models.enums import IntegrationProvider, MemberRole
from app.services.commercial import PLAN_CATALOG, current_period_key, get_or_create_billing_account, get_plan

settings = get_settings()
router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/commercial", tags=["commercial"])


class CheckoutRequest(BaseModel):
    plan: str


def _sign_state(payload: dict) -> str:
    if not settings.SECRET_KEY:
        raise HTTPException(status_code=503, detail="OAuth state signing is not configured")
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _verify_state(value: str) -> dict:
    try:
        body, sig = value.rsplit(".", 1)
        expected = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if int(payload["exp"]) < int(datetime.now(UTC).timestamp()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state") from exc


def _nonce_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _consume_oauth_nonce(db: Session, payload: dict, *, provider: str, subject: str) -> OAuthStateNonce:
    nonce = str(payload.get("nonce") or "")
    try:
        org_id = UUID(str(payload["org_id"]))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid OAuth state workspace") from exc
    row = db.scalar(
        select(OAuthStateNonce).where(
            OAuthStateNonce.nonce_hash == _nonce_hash(nonce),
            OAuthStateNonce.organization_id == org_id,
            OAuthStateNonce.provider == provider,
        )
    )
    now = datetime.now(UTC)
    if row is None or row.subject != subject or row.consumed_at is not None or row.expires_at <= now:
        raise HTTPException(status_code=400, detail="OAuth state has already been used or expired")
    row.consumed_at = now
    db.flush()
    return row


def _reserve_webhook_receipt(
    db: Session,
    *,
    provider: str,
    event_id: str,
    event_type: str | None,
    raw_body: bytes,
    organization_id: UUID | None = None,
) -> bool:
    """Reserve a provider event id in the current DB transaction.

    Returns False for an exact duplicate. Reusing an event id with different
    bytes is rejected rather than silently treated as a duplicate.
    """
    digest = hashlib.sha256(raw_body).hexdigest()
    existing = db.scalar(
        select(ExternalWebhookReceipt).where(
            ExternalWebhookReceipt.provider == provider,
            ExternalWebhookReceipt.event_id == event_id,
        )
    )
    if existing is not None:
        if existing.payload_sha256 != digest:
            raise HTTPException(status_code=400, detail="Webhook event id was reused with a different payload")
        return False
    db.add(
        ExternalWebhookReceipt(
            provider=provider,
            event_id=event_id,
            organization_id=organization_id,
            event_type=event_type,
            payload_sha256=digest,
            processed_at=datetime.now(UTC),
        )
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(ExternalWebhookReceipt).where(
                ExternalWebhookReceipt.provider == provider,
                ExternalWebhookReceipt.event_id == event_id,
            )
        )
        if existing is not None and existing.payload_sha256 == digest:
            return False
        raise HTTPException(status_code=409, detail="Webhook delivery conflicted with another request")
    return True


def _billing_secret() -> str:
    ref = settings.BILLING_STRIPE_SECRET_REF.strip()
    if not ref:
        raise HTTPException(status_code=503, detail="Stripe Billing is not configured")
    value = os.getenv(f"THRESHOLD_INTEGRATION_SECRET__{ref.upper()}")
    if not value:
        raise HTTPException(status_code=503, detail="Stripe Billing credential is unavailable")
    return value


def _stripe_post(path: str, form: dict[str, str]) -> dict:
    validate_live_endpoint(f"https://api.stripe.com{path}")
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.post(
                f"https://api.stripe.com{path}",
                headers={"Authorization": f"Bearer {_billing_secret()}"},
                content=urlencode(form),
            )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise HTTPException(status_code=503, detail="Billing provider unavailable") from exc
    try:
        body = response.json()
    except ValueError:
        body = {"error": {"message": response.text[:500]}}
    if not 200 <= response.status_code < 300:
        message = body.get("error", {}).get("message", "Billing provider rejected request") if isinstance(body, dict) else "Billing provider rejected request"
        raise HTTPException(status_code=502, detail=message)
    return body


@router.get("/plans")
def plans():
    return {key: value for key, value in PLAN_CATALOG.items() if key != "demo"}


@router.get("/status")
def commercial_status(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    organization = get_active_organization(org_id, user.id, db)
    billing = get_or_create_billing_account(db, organization)
    usage_rows = db.scalars(
        select(UsageCounter).where(
            UsageCounter.organization_id == org_id,
            UsageCounter.period_key == current_period_key(),
        )
    ).all()
    db.commit()
    return {
        "plan": organization.plan,
        "plan_definition": get_plan(organization),
        "subscription_status": billing.subscription_status,
        "trial_ends_at": billing.trial_ends_at,
        "current_period_end": billing.current_period_end,
        "cancel_at_period_end": billing.cancel_at_period_end,
        "usage_period": current_period_key(),
        "usage": {row.metric: row.quantity for row in usage_rows},
        "billing_configured": bool(settings.BILLING_STRIPE_SECRET_REF),
        "shopify_oauth_configured": bool(settings.SHOPIFY_CLIENT_ID and settings.SHOPIFY_CLIENT_SECRET),
    }


@router.post("/checkout")
def create_checkout(
    request: CheckoutRequest,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    organization = get_active_organization(org_id, user.id, db)
    require_org_roles(org_id, user.id, db, {MemberRole.OWNER}, detail="Owner permission required for billing")
    if request.plan not in {"starter", "business"}:
        raise HTTPException(status_code=422, detail="Only Starter and Business use self-serve checkout")
    price_id = settings.stripe_price_for_plan(request.plan)
    if not price_id:
        raise HTTPException(status_code=503, detail=f"Stripe price is not configured for {request.plan}")
    billing = get_or_create_billing_account(db, organization)
    form = {
        "mode": "subscription",
        "success_url": f"{settings.PUBLIC_APP_URL.rstrip('/')}/?billing=success&org_id={org_id}",
        "cancel_url": f"{settings.PUBLIC_APP_URL.rstrip('/')}/?billing=cancelled&org_id={org_id}",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "client_reference_id": str(org_id),
        "metadata[threshold_org_id]": str(org_id),
        "subscription_data[metadata][threshold_org_id]": str(org_id),
    }
    if billing.customer_id:
        form["customer"] = billing.customer_id
    else:
        form["customer_email"] = user.email
    body = _stripe_post("/v1/checkout/sessions", form)
    db.add(AuditLogEntry(organization_id=org_id, workflow_execution_id=None, event_type="billing.checkout_created", actor_type="human", actor_id=str(user.id), payload={"plan": request.plan, "checkout_session_id": body.get("id")}))
    db.commit()
    return {"checkout_url": body.get("url"), "session_id": body.get("id")}


@router.post("/portal")
def create_portal(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    organization = get_active_organization(org_id, user.id, db)
    require_org_roles(org_id, user.id, db, {MemberRole.OWNER}, detail="Owner permission required for billing")
    billing = get_or_create_billing_account(db, organization)
    if not billing.customer_id:
        raise HTTPException(status_code=409, detail="No Stripe billing customer exists for this workspace")
    body = _stripe_post("/v1/billing_portal/sessions", {"customer": billing.customer_id, "return_url": settings.PUBLIC_APP_URL})
    return {"url": body.get("url")}


@router.get("/shopify/install")
def shopify_install_url(
    org_id: UUID,
    shop: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_active_organization(org_id, user.id, db)
    require_org_roles(org_id, user.id, db, {MemberRole.OWNER, MemberRole.ADMIN}, detail="Admin permission required")
    shop = shop.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
    if not shop.endswith(".myshopify.com"):
        raise HTTPException(status_code=422, detail="Shop must be a .myshopify.com domain")
    if not settings.SHOPIFY_CLIENT_ID or not settings.SHOPIFY_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Shopify OAuth app credentials are not configured")
    nonce = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    db.add(
        OAuthStateNonce(
            organization_id=org_id,
            initiated_by_user_id=user.id,
            provider="shopify",
            subject=shop,
            nonce_hash=_nonce_hash(nonce),
            expires_at=expires_at,
        )
    )
    db.commit()
    state = _sign_state({"org_id": str(org_id), "shop": shop, "nonce": nonce, "exp": int(expires_at.timestamp())})
    query = urlencode({"client_id": settings.SHOPIFY_CLIENT_ID, "scope": settings.SHOPIFY_SCOPES, "redirect_uri": settings.SHOPIFY_OAUTH_REDIRECT_URI, "state": state})
    return {"authorization_url": f"https://{shop}/admin/oauth/authorize?{query}", "expires_in_seconds": 600}


@router.get("/shopify/callback")
def shopify_callback(code: str, state: str, shop: str, db: Session = Depends(get_db)):
    payload = _verify_state(state)
    normalized_shop = shop.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
    if payload.get("shop") != normalized_shop:
        raise HTTPException(status_code=400, detail="Shop does not match OAuth state")
    _consume_oauth_nonce(db, payload, provider="shopify", subject=normalized_shop)
    # OAuth state is single-use even if the downstream token exchange/vault
    # handoff fails. A retry must begin a fresh install and obtain fresh state.
    db.commit()
    org_id = UUID(payload["org_id"])
    organization = db.get(Organization, org_id)
    if organization is None or not organization.is_active:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not settings.OAUTH_SECRET_SINK_URL:
        raise HTTPException(status_code=503, detail="OAuth token vault sink is not configured; refusing to exchange and persist merchant credentials")
    validate_live_endpoint(settings.OAUTH_SECRET_SINK_URL)
    token_url = f"https://{normalized_shop}/admin/oauth/access_token"
    validate_live_endpoint(token_url)
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            token_response = client.post(token_url, json={"client_id": settings.SHOPIFY_CLIENT_ID, "client_secret": settings.SHOPIFY_CLIENT_SECRET, "code": code})
            token_response.raise_for_status()
            token_body = token_response.json()
            access_token = token_body.get("access_token")
            if not access_token:
                raise ValueError("missing access token")
            credential_ref = f"SHOPIFY_ORG_{str(org_id).replace('-', '').upper()}"
            sink_headers = {"Content-Type": "application/json"}
            if settings.OAUTH_SECRET_SINK_AUTH_REF:
                sink_secret = os.getenv(f"THRESHOLD_INTEGRATION_SECRET__{settings.OAUTH_SECRET_SINK_AUTH_REF.upper()}")
                if sink_secret:
                    sink_headers["Authorization"] = f"Bearer {sink_secret}"
            sink_response = client.post(settings.OAUTH_SECRET_SINK_URL, headers=sink_headers, json={"reference": credential_ref, "secret": access_token, "metadata": {"provider": "shopify", "shop": normalized_shop, "organization_id": str(org_id)}})
            sink_response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Shopify OAuth credential exchange/vault handoff failed") from exc
    integration = db.scalar(select(IntegrationConfig).where(IntegrationConfig.organization_id == org_id, IntegrationConfig.provider == IntegrationProvider.SHOPIFY))
    if integration is None:
        integration = IntegrationConfig(organization_id=org_id, provider=IntegrationProvider.SHOPIFY, config={})
        db.add(integration)
    integration.config = {**(integration.config or {}), "shop_domain": normalized_shop, "api_version": settings.SHOPIFY_API_VERSION, "oauth_managed": True, "refund_enabled": False}
    integration.credential_ref = credential_ref
    integration.is_enabled = True
    db.add(AuditLogEntry(organization_id=org_id, workflow_execution_id=None, event_type="shopify.oauth_connected", actor_type="system", actor_id=None, payload={"shop": normalized_shop, "credential_ref": credential_ref}))
    db.commit()
    return {"status": "connected", "organization_id": str(org_id), "shop": normalized_shop}


def _stripe_webhook_secret() -> str:
    ref = settings.BILLING_STRIPE_WEBHOOK_SECRET_REF.strip()
    if not ref:
        raise HTTPException(status_code=503, detail="Stripe billing webhook is not configured")
    value = os.getenv(f"THRESHOLD_INTEGRATION_SECRET__{ref.upper()}")
    if not value:
        raise HTTPException(status_code=503, detail="Stripe billing webhook secret is unavailable")
    return value


def _verify_stripe_signature(raw_body: bytes, signature_header: str, tolerance_seconds: int = 300) -> None:
    parts: dict[str, list[str]] = {}
    for item in signature_header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts.setdefault(key.strip(), []).append(value.strip())
    try:
        timestamp = int(parts["t"][0])
        signatures = parts["v1"]
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Malformed Stripe signature") from exc
    now = int(datetime.now(UTC).timestamp())
    if abs(now - timestamp) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Expired Stripe webhook signature")
    signed_payload = str(timestamp).encode() + b"." + raw_body
    expected = hmac.new(_stripe_webhook_secret().encode(), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")


def _plan_from_price(price_id: str | None) -> str | None:
    if price_id and price_id == settings.STRIPE_STARTER_PRICE_ID:
        return "starter"
    if price_id and price_id == settings.STRIPE_BUSINESS_PRICE_ID:
        return "business"
    return None


@router.post("/stripe/webhook")
async def stripe_billing_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    _verify_stripe_signature(raw, request.headers.get("Stripe-Signature", ""))
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe event JSON") from exc
    event_type = str(event.get("type") or "")
    event_id = str(event.get("id") or "")
    if not event_id:
        raise HTTPException(status_code=400, detail="Stripe event id is required")
    if not _reserve_webhook_receipt(
        db,
        provider="stripe_billing",
        event_id=event_id,
        event_type=event_type or None,
        raw_body=raw,
    ):
        return {"received": True, "duplicate": True}
    obj = (event.get("data") or {}).get("object") or {}
    metadata = obj.get("metadata") or {}
    org_value = metadata.get("threshold_org_id") or obj.get("client_reference_id")
    subscription = None
    if event_type == "checkout.session.completed":
        subscription_id = obj.get("subscription")
        customer_id = obj.get("customer")
        if not org_value:
            db.commit()
            return {"received": True, "ignored": "missing_threshold_org_id"}
        organization = db.get(Organization, UUID(org_value))
        if organization is None:
            db.commit()
            return {"received": True, "ignored": "unknown_workspace"}
        billing = get_or_create_billing_account(db, organization)
        billing.customer_id = str(customer_id) if customer_id else billing.customer_id
        billing.subscription_id = str(subscription_id) if subscription_id else billing.subscription_id
        billing.subscription_status = "active"
        db.add(AuditLogEntry(organization_id=organization.id, workflow_execution_id=None, event_type="billing.checkout_completed", actor_type="system", actor_id=None, payload={"stripe_event_id": event.get("id"), "subscription_id": billing.subscription_id}))
        db.commit()
        return {"received": True}

    if event_type.startswith("customer.subscription."):
        org_value = metadata.get("threshold_org_id")
        if not org_value:
            db.commit()
            return {"received": True, "ignored": "missing_threshold_org_id"}
        organization = db.get(Organization, UUID(org_value))
        if organization is None:
            db.commit()
            return {"received": True, "ignored": "unknown_workspace"}
        billing = get_or_create_billing_account(db, organization)
        subscription = obj
        first_item = (((obj.get("items") or {}).get("data") or [{}])[0])
        price = first_item.get("price") or {}
        price_id = price.get("id")
        resolved_plan = _plan_from_price(price_id)
        billing.customer_id = str(obj.get("customer") or billing.customer_id or "") or None
        billing.subscription_id = str(obj.get("id") or billing.subscription_id or "") or None
        billing.subscription_status = str(obj.get("status") or "unknown")
        billing.price_id = price_id
        billing.cancel_at_period_end = bool(obj.get("cancel_at_period_end", False))
        period_end = obj.get("current_period_end")
        billing.current_period_end = datetime.fromtimestamp(period_end, tz=UTC) if period_end else None
        if event_type == "customer.subscription.deleted":
            organization.plan = "trial"
        elif resolved_plan:
            organization.plan = resolved_plan
        db.add(AuditLogEntry(organization_id=organization.id, workflow_execution_id=None, event_type="billing.subscription_synced", actor_type="system", actor_id=None, payload={"stripe_event_id": event.get("id"), "status": billing.subscription_status, "price_id": price_id, "plan": organization.plan}))
        db.commit()
        return {"received": True}

    db.commit()
    return {"received": True, "ignored": event_type or "unknown_event"}
