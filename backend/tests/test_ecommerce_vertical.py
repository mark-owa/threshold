from decimal import Decimal
from types import SimpleNamespace

from app.integrations.shopify import snapshot_from_webhook, verify_shopify_hmac


def test_shopify_hmac_round_trip():
    import base64, hashlib, hmac
    secret = "shpss_test"
    body = b'{"id":123}'
    signature = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    assert verify_shopify_hmac(secret, body, signature)
    assert not verify_shopify_hmac(secret, body + b"x", signature)


def test_shopify_order_snapshot_tracks_remaining_refundable_amount():
    snap = snapshot_from_webhook({
        "id": 123, "name": "#1001", "currency": "USD", "total_price": "100.00",
        "financial_status": "paid", "created_at": "2026-09-01T00:00:00Z",
        "customer": {"id": 9, "first_name": "Ada", "last_name": "Owner", "email": "ada@example.com"},
        "refunds": [{"amount": "25.00"}],
    })
    assert snap.external_order_id == "gid://shopify/Order/123"
    assert snap.order_number == "#1001"
    assert snap.refundable_amount == Decimal("75.00")
