"""Optional final-outcome delivery. Never executes or retries a refund."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.webhooks import compute_signature, webhook_secret_value
from app.integrations.providers import validate_live_endpoint
from app.models import OutboxMessage
from app.models.enums import OutboxStatus, WorkflowStatus

TOPIC = "deliver_n8n_outcome"


class DeliveryError(Exception):
    def __init__(self, code: str, *, retryable: bool = True, retry_after: int = 0):
        super().__init__(code)
        self.retryable = retryable
        self.retry_after = retry_after


def outcome_payload(execution, target: dict) -> dict | None:
    """Final refund outcomes only. No raw request text, email or provider secrets."""
    context = execution.context or {}
    crm = context.get("event", {}).get("crm")
    if not crm or context.get("category") != "refund_request":
        return None
    if execution.status not in {WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED}:
        return None
    if execution.status == WorkflowStatus.COMPLETED and context.get("verified") is not True:
        return None
    # Portal mismatch was rejected at ingress; fail closed if legacy data differs.
    if crm.get("portal_id") != target.get("hubspot_portal_id"):
        return None
    delivery_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"threshold:outcome:{execution.organization_id}:{execution.id}:{execution.status.value}",
    )
    return {
        "schema_version": 1,
        "delivery_id": str(delivery_id),
        "type": "threshold.refund.final",
        "organization_id": str(execution.organization_id),
        "execution_id": str(execution.id),
        "event_id": str(execution.incoming_event_id),
        "status": execution.status.value,
        "verified": context.get("verified") is True,
        "crm": crm,
    }


def enqueue_final_outcome(db, execution) -> None:
    target = get_settings().N8N_OUTCOME_TARGETS.get(str(execution.organization_id))
    if not target:
        return
    payload = outcome_payload(execution, target)
    if payload is None:
        return
    # Same DB transaction as final business state; PK makes duplicate hooks safe.
    db.execute(
        insert(OutboxMessage)
        .values(
            id=uuid.UUID(payload["delivery_id"]),
            organization_id=execution.organization_id,
            topic=TOPIC,
            aggregate_type="workflow_execution",
            aggregate_id=execution.id,
            payload=payload,
            status=OutboxStatus.PENDING,
            attempt_count=0,
            max_attempts=8,
            available_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )


def deliver_outcome(row, *, client=None) -> None:
    settings = get_settings()
    target = settings.N8N_OUTCOME_TARGETS.get(str(row.organization_id), {})
    url = target.get("url", "")
    parsed = urlparse(url)
    try:
        validate_live_endpoint(url)
        if parsed.username or parsed.password or parsed.fragment or parsed.query:
            raise ValueError("Invalid destination")
        if parsed.scheme != "https" and settings.APP_ENV != "development":
            raise ValueError("HTTPS required")
        if row.payload.get("crm", {}).get("portal_id") != target.get("hubspot_portal_id"):
            raise ValueError("Portal mismatch")
        secret = webhook_secret_value(target.get("secret_ref"))
        if not secret or len(secret) < 32:
            raise ValueError("Missing delivery secret")
    except ValueError as exc:
        raise DeliveryError("outcome_configuration_invalid", retryable=False) from exc
    body = json.dumps(row.payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Threshold-Delivery-Id": str(row.id),
        "X-Threshold-Timestamp": timestamp,
        "X-Threshold-Signature": "sha256=" + compute_signature(secret, timestamp, body),
        # n8n Header Auth validates this credential before workflow execution.
        "X-Threshold-Token": secret,
    }
    # Keep HTTP timeout below publisher lease; redirects never receive secrets.
    timeout = max(0.2, min(10.0, settings.OUTBOX_LEASE_SECONDS / 4))
    owned = client is None
    client = client or httpx.Client()
    try:
        try:
            response = client.post(
                url, content=body, headers=headers, timeout=timeout, follow_redirects=False
            )
        except httpx.TransportError as exc:
            raise DeliveryError("outcome_transport_error") from exc
        code = response.status_code
        if code != 200:
            value = response.headers.get("Retry-After", "")
            delay = min(int(value), 3600) if value.isdigit() else 0
            raise DeliveryError(
                f"outcome_http_{code}",
                retryable=code in {408, 429, 500, 502, 503, 504},
                retry_after=delay,
            )
        try:
            ack = response.json()
        except ValueError as exc:
            raise DeliveryError("outcome_invalid_ack") from exc
        if (
            not isinstance(ack, dict)
            or ack.get("ok") is not True
            or ack.get("delivery_id") != str(row.id)
        ):
            raise DeliveryError("outcome_invalid_ack")
    finally:
        if owned:
            client.close()
