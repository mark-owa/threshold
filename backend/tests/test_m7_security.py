import hashlib
import hmac
import json
from datetime import UTC, datetime

from app.api.commercial import settings as commercial_settings
from app.models import ExternalWebhookReceipt


def _stripe_signature(secret: str, body: bytes, timestamp: int) -> str:
    digest = hmac.new(
        secret.encode(),
        str(timestamp).encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_stripe_billing_webhook_is_deduplicated(client, db_session, monkeypatch):
    secret = "whsec_test_threshold_m7"
    monkeypatch.setattr(commercial_settings, "BILLING_STRIPE_WEBHOOK_SECRET_REF", "M7_STRIPE")
    monkeypatch.setenv("THRESHOLD_INTEGRATION_SECRET__M7_STRIPE", secret)

    body = json.dumps(
        {
            "id": "evt_threshold_m7_duplicate",
            "type": "threshold.test.ignored",
            "data": {"object": {}},
        },
        separators=(",", ":"),
    ).encode()
    timestamp = int(datetime.now(UTC).timestamp())
    headers = {
        "Stripe-Signature": _stripe_signature(secret, body, timestamp),
        "Content-Type": "application/json",
    }

    first = client.post("/api/v1/commercial/stripe/webhook", content=body, headers=headers)
    second = client.post("/api/v1/commercial/stripe/webhook", content=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    rows = (
        db_session.query(ExternalWebhookReceipt)
        .filter_by(provider="stripe_billing", event_id="evt_threshold_m7_duplicate")
        .all()
    )
    assert len(rows) == 1
