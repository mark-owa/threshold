from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.integrations.providers import MockRefundProvider, validate_live_endpoint


def test_mock_provider_reports_verified_side_effect():
    result = MockRefundProvider().execute_refund(
        SimpleNamespace(),
        order_number="ORD-1001",
        amount_usd=Decimal("12.50"),
        idempotency_key="refund:test:1",
    )
    assert result.status == "succeeded"
    assert result.verified is True
    assert result.provider_operation_id


def test_live_endpoint_requires_allowlisted_host(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "INTEGRATION_ALLOWED_HOSTS", "api.safe.example")
    validate_live_endpoint("https://api.safe.example/refunds")
    with pytest.raises(ValueError, match="allowlisted"):
        validate_live_endpoint("https://evil.example/refunds")
