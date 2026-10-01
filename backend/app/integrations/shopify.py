from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.providers import _credential_value, validate_live_endpoint
from app.models import Customer, IntegrationConfig, Order


@dataclass(frozen=True)
class ShopifyOrderSnapshot:
    external_order_id: str
    order_number: str
    customer_external_id: str | None
    customer_name: str
    customer_email: str
    currency: str
    total_amount: Decimal
    refunded_amount: Decimal
    status: str
    ordered_at: datetime
    payment_reference: str | None
    payment_gateway: str | None

    @property
    def refundable_amount(self) -> Decimal:
        value = self.total_amount - self.refunded_amount
        return value if value > 0 else Decimal("0.00")


def verify_shopify_hmac(secret: str, body: bytes, supplied_signature: str) -> bool:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, supplied_signature.strip())


def _money(value: object) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def snapshot_from_webhook(payload: dict) -> ShopifyOrderSnapshot:
    order_id = str(payload.get("admin_graphql_api_id") or payload.get("id") or "")
    if order_id and not order_id.startswith("gid://"):
        order_id = f"gid://shopify/Order/{order_id}"
    order_name = str(payload.get("name") or payload.get("order_number") or "").strip()
    if not order_name:
        raise ValueError("Shopify order webhook is missing order number/name")
    customer = payload.get("customer") or {}
    first = str(customer.get("first_name") or "").strip()
    last = str(customer.get("last_name") or "").strip()
    email = str(customer.get("email") or payload.get("email") or "").strip().lower()
    customer_name = (
        " ".join(part for part in (first, last) if part).strip() or email or "Shopify customer"
    )
    transactions = payload.get("transactions") or []
    payment_reference = None
    payment_gateway = None
    for tx in transactions:
        candidate = (
            tx.get("payment_id") or tx.get("authorization") or tx.get("admin_graphql_api_id")
        )
        if candidate:
            payment_reference = str(tx.get("admin_graphql_api_id") or candidate)
            payment_gateway = str(tx.get("gateway") or "") or None
            break
    refunded = sum(
        (
            _money(item.get("amount"))
            for item in payload.get("refunds", [])
            if isinstance(item, dict)
        ),
        Decimal("0.00"),
    )
    return ShopifyOrderSnapshot(
        external_order_id=order_id,
        order_number=order_name,
        customer_external_id=str(customer.get("admin_graphql_api_id") or customer.get("id") or "")
        or None,
        customer_name=customer_name,
        customer_email=email or f"unknown-{order_name}@shopify.local",
        currency=str(payload.get("currency") or "USD").upper(),
        total_amount=_money(payload.get("total_price") or payload.get("current_total_price")),
        refunded_amount=refunded,
        status="completed"
        if str(payload.get("financial_status") or "").lower()
        in {"paid", "partially_refunded", "refunded"}
        else str(payload.get("financial_status") or "open").lower(),
        ordered_at=_parse_datetime(payload.get("created_at") or payload.get("processed_at")),
        payment_reference=payment_reference,
        payment_gateway=payment_gateway,
    )


def upsert_shopify_order(db: Session, organization_id, snapshot: ShopifyOrderSnapshot) -> Order:
    customer = None
    if snapshot.customer_external_id:
        customer = db.scalar(
            select(Customer).where(
                Customer.organization_id == organization_id,
                Customer.external_customer_id == snapshot.customer_external_id,
            )
        )
    if customer is None:
        customer = db.scalar(
            select(Customer).where(
                Customer.organization_id == organization_id,
                Customer.email == snapshot.customer_email,
            )
        )
    if customer is None:
        customer = Customer(
            organization_id=organization_id,
            name=snapshot.customer_name,
            email=snapshot.customer_email,
            external_customer_id=snapshot.customer_external_id,
        )
        db.add(customer)
        db.flush()
    else:
        customer.name = snapshot.customer_name or customer.name
        customer.external_customer_id = (
            snapshot.customer_external_id or customer.external_customer_id
        )

    order = db.scalar(
        select(Order).where(
            Order.organization_id == organization_id,
            Order.order_number == snapshot.order_number,
        )
    )
    if order is None:
        order = Order(
            organization_id=organization_id,
            customer_id=customer.id,
            order_number=snapshot.order_number,
            external_order_id=snapshot.external_order_id,
            payment_reference=snapshot.payment_reference,
            payment_gateway=snapshot.payment_gateway,
            currency=snapshot.currency,
            amount_usd=snapshot.total_amount,
            refunded_amount_usd=snapshot.refunded_amount,
            status=snapshot.status,
            ordered_at=snapshot.ordered_at,
        )
        db.add(order)
    else:
        order.customer_id = customer.id
        order.external_order_id = snapshot.external_order_id or order.external_order_id
        order.payment_reference = snapshot.payment_reference or order.payment_reference
        order.payment_gateway = snapshot.payment_gateway or order.payment_gateway
        order.currency = snapshot.currency
        order.amount_usd = snapshot.total_amount
        order.refunded_amount_usd = snapshot.refunded_amount
        order.status = snapshot.status
        order.ordered_at = snapshot.ordered_at
    db.flush()
    return order


class ShopifyAdminClient:
    def __init__(self, integration: IntegrationConfig):
        self.integration = integration
        self.shop_domain = str(integration.config.get("shop_domain", "")).strip().lower()
        if not self.shop_domain.endswith(".myshopify.com"):
            raise ValueError("Shopify shop_domain must end with .myshopify.com")
        self.api_version = str(integration.config.get("api_version", "2026-07"))
        token = _credential_value(integration.credential_ref)
        if not token:
            raise ValueError("Shopify access token secret is not configured")
        self.token = token
        self.url = f"https://{self.shop_domain}/admin/api/{self.api_version}/graphql.json"
        validate_live_endpoint(self.url)

    def _graphql(self, query: str, variables: dict) -> dict:
        timeout = float(self.integration.config.get("timeout_seconds", 10))
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.post(
                self.url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Shopify-Access-Token": self.token,
                },
                json={"query": query, "variables": variables},
            )
        response.raise_for_status()
        body = response.json()
        if body.get("errors"):
            raise ValueError(f"Shopify GraphQL error: {body['errors']}")
        return body.get("data") or {}

    def fetch_order(self, order_number: str) -> ShopifyOrderSnapshot | None:
        query = """
        query ThresholdOrder($query: String!) {
          orders(first: 5, query: $query, sortKey: ORDER_NUMBER) {
            nodes {
              id
              name
              createdAt
              displayFinancialStatus
              currencyCode
              currentTotalPriceSet { shopMoney { amount currencyCode } }
              totalRefundedSet { shopMoney { amount currencyCode } }
              customer { id displayName email }
              transactions(first: 20) { id kind status paymentId gateway }
            }
          }
        }
        """
        data = self._graphql(query, {"query": order_number})
        nodes = data.get("orders", {}).get("nodes", [])
        normalized = order_number.strip().lstrip("#")
        node = next((n for n in nodes if str(n.get("name", "")).lstrip("#") == normalized), None)
        if node is None:
            return None
        customer = node.get("customer") or {}
        transactions = node.get("transactions") or []
        payment_reference = None
        payment_gateway = None
        for tx in transactions:
            if tx.get("status") in {"SUCCESS", "PENDING"} and tx.get("kind") in {"SALE", "CAPTURE"}:
                payment_reference = str(tx.get("id") or tx.get("paymentId") or "") or None
                payment_gateway = str(tx.get("gateway") or "") or None
                if payment_reference:
                    break
        total = node.get("currentTotalPriceSet", {}).get("shopMoney", {})
        refunded = node.get("totalRefundedSet", {}).get("shopMoney", {})
        return ShopifyOrderSnapshot(
            external_order_id=str(node["id"]),
            order_number=str(node["name"]),
            customer_external_id=str(customer.get("id") or "") or None,
            customer_name=str(
                customer.get("displayName") or customer.get("email") or "Shopify customer"
            ),
            customer_email=str(
                customer.get("email") or f"unknown-{normalized}@shopify.local"
            ).lower(),
            currency=str(total.get("currencyCode") or node.get("currencyCode") or "USD"),
            total_amount=_money(total.get("amount")),
            refunded_amount=_money(refunded.get("amount")),
            status="completed"
            if str(node.get("displayFinancialStatus")) in {"PAID", "PARTIALLY_REFUNDED", "REFUNDED"}
            else str(node.get("displayFinancialStatus") or "OPEN").lower(),
            ordered_at=_parse_datetime(node.get("createdAt")),
            payment_reference=payment_reference,
            payment_gateway=payment_gateway,
        )
