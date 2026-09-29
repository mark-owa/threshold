from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.webhooks import verify_signature, webhook_secret_value
from app.db.session import get_db
from app.models import AuditLogEntry, IncomingEvent, IntegrationConfig, WebhookEndpoint
from app.models.enums import EventProcessingStatus, EventSource, IntegrationProvider
from app.services.outbox import enqueue_outbox

router = APIRouter(prefix=f"{get_settings().API_V1_PREFIX}/webhooks", tags=["webhooks"])


@router.post("/{endpoint_key}", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(
    endpoint_key: str,
    request: Request,
    x_threshold_event_id: str = Header(alias="X-Threshold-Event-Id"),
    x_threshold_timestamp: str = Header(alias="X-Threshold-Timestamp"),
    x_threshold_signature: str = Header(alias="X-Threshold-Signature"),
    db: Session = Depends(get_db),
):
    # Lock the endpoint row so two simultaneous deliveries with the same
    # provider event id cannot both pass the pre-insert duplicate check.
    endpoint = db.scalar(
        select(WebhookEndpoint)
        .where(
            WebhookEndpoint.endpoint_key == endpoint_key,
            WebhookEndpoint.is_active.is_(True),
        )
        .with_for_update()
    )
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    body = await request.body()
    secret = webhook_secret_value(endpoint.signing_secret_ref)
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook signing secret is not configured")
    if not verify_signature(
        secret=secret,
        timestamp=x_threshold_timestamp,
        body=body,
        signature=x_threshold_signature,
        allowed_clock_skew_seconds=endpoint.allowed_clock_skew_seconds,
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired webhook signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Webhook body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook JSON payload must be an object")

    idempotency_key = f"webhook:{endpoint.id}:{x_threshold_event_id}"
    existing = db.scalar(
        select(IncomingEvent).where(
            IncomingEvent.organization_id == endpoint.organization_id,
            IncomingEvent.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "accepted": True,
                "duplicate": True,
                "event_id": str(existing.id),
                "processing_status": existing.processing_status.value,
            },
        )

    event = IncomingEvent(
        organization_id=endpoint.organization_id,
        source=EventSource.WEBHOOK,
        external_id=x_threshold_event_id,
        idempotency_key=idempotency_key,
        request_id=getattr(request.state, "request_id", None),
        raw_payload=payload,
        signature_verified=True,
        processing_status=EventProcessingStatus.RECEIVED,
        received_at=datetime.now(UTC),
    )
    db.add(event)
    db.flush()
    enqueue_outbox(
        db,
        organization_id=endpoint.organization_id,
        topic="process_incoming_event",
        aggregate_type="incoming_event",
        aggregate_id=event.id,
        payload={"event_id": str(event.id), "organization_id": str(endpoint.organization_id)},
    )
    db.add(
        AuditLogEntry(
            organization_id=endpoint.organization_id,
            workflow_execution_id=None,
            event_type="webhook.accepted",
            actor_type="integration",
            actor_id=endpoint.name,
            payload={
                "event_id": str(event.id),
                "external_event_id": x_threshold_event_id,
                "endpoint_id": str(endpoint.id),
            },
        )
    )
    db.commit()
    return {
        "accepted": True,
        "duplicate": False,
        "event_id": str(event.id),
        "processing_status": event.processing_status.value,
    }


@router.post("/shopify/{organization_id}", status_code=status.HTTP_202_ACCEPTED)
async def receive_shopify_webhook(
    organization_id: str,
    request: Request,
    x_shopify_hmac_sha256: str = Header(alias="X-Shopify-Hmac-SHA256"),
    x_shopify_webhook_id: str = Header(alias="X-Shopify-Webhook-Id"),
    x_shopify_topic: str = Header(alias="X-Shopify-Topic"),
    db: Session = Depends(get_db),
):
    from uuid import UUID

    try:
        org_id = UUID(organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Shopify webhook target not found") from exc
    integration = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.organization_id == org_id,
            IntegrationConfig.provider == IntegrationProvider.SHOPIFY,
            IntegrationConfig.is_enabled.is_(True),
        )
    )
    if integration is None:
        raise HTTPException(status_code=404, detail="Shopify integration not found")
    body = await request.body()
    secret_ref = str((integration.config or {}).get("webhook_secret_ref") or "")
    secret = webhook_secret_value(secret_ref) if secret_ref else None
    if not secret:
        raise HTTPException(
            status_code=503, detail="Shopify webhook signing secret is not configured"
        )
    from app.integrations.shopify import verify_shopify_hmac

    if not verify_shopify_hmac(secret, body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400, detail="Shopify webhook body must be valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400, detail="Shopify webhook JSON payload must be an object"
        )

    idempotency_key = f"shopify:{integration.id}:{x_shopify_webhook_id}"
    existing = db.scalar(
        select(IncomingEvent).where(
            IncomingEvent.organization_id == org_id,
            IncomingEvent.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"accepted": True, "duplicate": True, "event_id": str(existing.id)},
        )

    event = IncomingEvent(
        organization_id=org_id,
        source=EventSource.WEBHOOK,
        external_id=x_shopify_webhook_id,
        idempotency_key=idempotency_key,
        request_id=getattr(request.state, "request_id", None),
        raw_payload={"shopify_topic": x_shopify_topic, "payload": payload},
        signature_verified=True,
        processing_status=EventProcessingStatus.RECEIVED,
        received_at=datetime.now(UTC),
    )
    db.add(event)
    db.flush()
    if x_shopify_topic.startswith("orders/"):
        topic = "sync_shopify_order"
    else:
        topic = "process_incoming_event"
    enqueue_outbox(
        db,
        organization_id=org_id,
        topic=topic,
        aggregate_type="incoming_event",
        aggregate_id=event.id,
        payload={"event_id": str(event.id), "organization_id": str(org_id)},
    )
    db.add(
        AuditLogEntry(
            organization_id=org_id,
            workflow_execution_id=None,
            event_type="shopify.webhook_accepted",
            actor_type="integration",
            actor_id=x_shopify_topic,
            payload={
                "event_id": str(event.id),
                "webhook_id": x_shopify_webhook_id,
                "topic": x_shopify_topic,
            },
        )
    )
    db.commit()
    return {
        "accepted": True,
        "duplicate": False,
        "event_id": str(event.id),
        "topic": x_shopify_topic,
    }
