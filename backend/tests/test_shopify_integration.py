import base64
import hashlib
import hmac
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.integrations import shopify
from app.integrations.shopify import (
    ShopifyAdminClient,
    ShopifyOrderSnapshot,
    snapshot_from_webhook,
    upsert_shopify_order,
    verify_shopify_hmac,
)
from app.models import Customer, IntegrationConfig, Order, Organization
from app.models.enums import IntegrationProvider


def _snapshot(**overrides):
    values = {
        "external_order_id": "gid://shopify/Order/123",
        "order_number": "#1001",
        "customer_external_id": "gid://shopify/Customer/9",
        "customer_name": "Ada Owner",
        "customer_email": "ada@example.com",
        "currency": "USD",
        "total_amount": Decimal("100.00"),
        "refunded_amount": Decimal("25.00"),
        "status": "completed",
        "ordered_at": datetime(2026, 9, 1, tzinfo=UTC),
        "payment_reference": "gid://shopify/OrderTransaction/77",
        "payment_gateway": "shopify_payments",
    }
    values.update(overrides)
    return ShopifyOrderSnapshot(**values)


def test_snapshot_helpers_and_webhook_parsing():
    body = b'{"id":123}'
    secret = "secret"
    signature = base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    assert verify_shopify_hmac(secret, body, signature)
    assert not verify_shopify_hmac(secret, body, "wrong")

    assert _snapshot().refundable_amount == Decimal("75.00")
    assert _snapshot(refunded_amount=Decimal("200")).refundable_amount == Decimal("0.00")
    assert shopify._money(None) == Decimal("0.00")
    assert shopify._parse_datetime("2026-09-01T00:00:00").tzinfo is not None
    assert shopify._parse_datetime(None).tzinfo is not None

    parsed = snapshot_from_webhook(
        {
            "id": 123,
            "name": "#1001",
            "currency": "usd",
            "total_price": "100.00",
            "financial_status": "paid",
            "created_at": "2026-09-01T00:00:00Z",
            "email": "ORDER@EXAMPLE.COM",
            "customer": {
                "id": 9,
                "first_name": "Ada",
                "last_name": "Owner",
                "email": "ADA@EXAMPLE.COM",
            },
            "transactions": [
                {
                    "authorization": "auth-1",
                    "admin_graphql_api_id": "gid://shopify/OrderTransaction/1",
                    "gateway": "shopify_payments",
                }
            ],
            "refunds": [{"amount": "25.00"}, {"amount": "5.00"}],
        }
    )
    assert parsed.external_order_id == "gid://shopify/Order/123"
    assert parsed.customer_name == "Ada Owner"
    assert parsed.customer_email == "ada@example.com"
    assert parsed.currency == "USD"
    assert parsed.refunded_amount == Decimal("30.00")
    assert parsed.payment_gateway == "shopify_payments"
    assert parsed.status == "completed"

    fallback = snapshot_from_webhook(
        {
            "admin_graphql_api_id": "gid://shopify/Order/5",
            "order_number": "1005",
            "current_total_price": "12",
            "financial_status": "pending",
        }
    )
    assert fallback.customer_name == "Shopify customer"
    assert fallback.customer_email == "unknown-1005@shopify.local"
    assert fallback.status == "pending"

    with pytest.raises(ValueError, match="order number"):
        snapshot_from_webhook({"id": 1})


def test_upsert_shopify_order_creates_and_updates(db_session):
    org = Organization(name="Shopify Test", slug="shopify-test", plan="trial")
    db_session.add(org)
    db_session.flush()

    first = upsert_shopify_order(db_session, org.id, _snapshot())
    customer = db_session.get(Customer, first.customer_id)
    assert first.order_number == "#1001"
    assert customer.email == "ada@example.com"
    assert customer.external_customer_id == "gid://shopify/Customer/9"

    updated = upsert_shopify_order(
        db_session,
        org.id,
        _snapshot(
            customer_name="Ada Updated",
            total_amount=Decimal("120.00"),
            refunded_amount=Decimal("30.00"),
            payment_reference="gid://shopify/OrderTransaction/88",
        ),
    )
    assert updated.id == first.id
    assert updated.amount_usd == Decimal("120.00")
    assert updated.refunded_amount_usd == Decimal("30.00")
    assert db_session.get(Customer, updated.customer_id).name == "Ada Updated"
    assert db_session.query(Order).filter_by(organization_id=org.id).count() == 1


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    payload = {"data": {}}
    calls = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        self.__class__.calls.append((url, kwargs))
        return FakeResponse(self.__class__.payload)


def _integration(**config):
    values = {
        "shop_domain": "store.myshopify.com",
        "api_version": "2026-07",
        "timeout_seconds": 3,
    }
    values.update(config)
    return IntegrationConfig(
        id=uuid4(),
        organization_id=uuid4(),
        provider=IntegrationProvider.SHOPIFY,
        credential_ref="SHOPIFY_TEST",
        config=values,
        is_enabled=True,
    )


def test_shopify_admin_client_validation_and_graphql(monkeypatch):
    monkeypatch.setattr(shopify, "_credential_value", lambda ref: "token")
    seen = []
    monkeypatch.setattr(shopify, "validate_live_endpoint", seen.append)

    with pytest.raises(ValueError, match="myshopify"):
        ShopifyAdminClient(_integration(shop_domain="example.com"))

    monkeypatch.setattr(shopify, "_credential_value", lambda ref: None)
    with pytest.raises(ValueError, match="access token"):
        ShopifyAdminClient(_integration())

    monkeypatch.setattr(shopify, "_credential_value", lambda ref: "token")
    client = ShopifyAdminClient(_integration())
    assert client.url.endswith("/admin/api/2026-07/graphql.json")
    assert seen[-1] == client.url

    FakeClient.calls = []
    FakeClient.payload = {"data": {"shop": {"id": "gid://shopify/Shop/1"}}}
    monkeypatch.setattr(shopify.httpx, "Client", FakeClient)
    data = client._graphql("query { shop { id } }", {})
    assert data["shop"]["id"] == "gid://shopify/Shop/1"
    assert FakeClient.calls[0][1]["headers"]["X-Shopify-Access-Token"] == "token"

    FakeClient.payload = {"errors": [{"message": "bad query"}]}
    with pytest.raises(ValueError, match="GraphQL"):
        client._graphql("bad", {})


def test_fetch_order_missing_and_success(monkeypatch):
    monkeypatch.setattr(shopify, "_credential_value", lambda ref: "token")
    monkeypatch.setattr(shopify, "validate_live_endpoint", lambda url: None)
    client = ShopifyAdminClient(_integration())

    monkeypatch.setattr(
        client,
        "_graphql",
        lambda query, variables: {"orders": {"nodes": [{"name": "#9999"}]}},
    )
    assert client.fetch_order("#1001") is None

    node = {
        "id": "gid://shopify/Order/123",
        "name": "#1001",
        "createdAt": "2026-09-01T00:00:00Z",
        "displayFinancialStatus": "PAID",
        "currencyCode": "USD",
        "currentTotalPriceSet": {"shopMoney": {"amount": "100", "currencyCode": "USD"}},
        "totalRefundedSet": {"shopMoney": {"amount": "15", "currencyCode": "USD"}},
        "customer": {
            "id": "gid://shopify/Customer/9",
            "displayName": "Ada Owner",
            "email": "ADA@EXAMPLE.COM",
        },
        "transactions": [
            {
                "id": "gid://shopify/OrderTransaction/1",
                "kind": "CAPTURE",
                "status": "SUCCESS",
                "paymentId": "pay-1",
                "gateway": "shopify_payments",
            }
        ],
    }
    monkeypatch.setattr(
        client,
        "_graphql",
        lambda query, variables: {"orders": {"nodes": [node]}},
    )
    result = client.fetch_order("1001")
    assert result.order_number == "#1001"
    assert result.total_amount == Decimal("100.00")
    assert result.refunded_amount == Decimal("15.00")
    assert result.customer_email == "ada@example.com"
    assert result.payment_reference == "gid://shopify/OrderTransaction/1"
    assert result.payment_gateway == "shopify_payments"
