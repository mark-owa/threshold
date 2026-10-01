from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode, urljoin, urlparse

import httpx

from app.core.config import get_settings
from app.models import IntegrationConfig
from app.models.enums import IntegrationProvider


@dataclass(frozen=True)
class ProviderResult:
    status: str
    response: dict
    provider_operation_id: str | None = None
    verified: bool = False
    retryable: bool = False
    unknown: bool = False
    error: str | None = None


class RefundProvider:
    name = "base"

    def execute_refund(
        self,
        integration: IntegrationConfig,
        *,
        order_number: str,
        amount_usd: Decimal,
        idempotency_key: str,
        external_order_id: str | None = None,
        payment_reference: str | None = None,
        payment_gateway: str | None = None,
        currency: str = "USD",
    ) -> ProviderResult:
        raise NotImplementedError

    def reconcile_refund(
        self,
        integration: IntegrationConfig,
        *,
        idempotency_key: str,
        provider_operation_id: str | None = None,
    ) -> ProviderResult:
        raise NotImplementedError


class MockRefundProvider(RefundProvider):
    name = "mock_payments"

    def execute_refund(self, integration, *, order_number, amount_usd, idempotency_key, **kwargs):
        import uuid

        refund_id = f"rf_{uuid.uuid4().hex[:12]}"
        return ProviderResult(
            status="succeeded",
            response={"provider": self.name, "refund_id": refund_id},
            provider_operation_id=refund_id,
            verified=True,
        )

    def reconcile_refund(self, integration, *, idempotency_key, provider_operation_id=None):
        if provider_operation_id:
            return ProviderResult(
                status="succeeded",
                response={"provider": self.name, "refund_id": provider_operation_id},
                provider_operation_id=provider_operation_id,
                verified=True,
            )
        return ProviderResult(
            status="unknown", response={}, unknown=True, error="missing_provider_id"
        )


def _credential_value(reference: str | None) -> str | None:
    if not reference:
        return None
    return os.getenv(f"THRESHOLD_INTEGRATION_SECRET__{reference.upper()}")


def validate_live_endpoint(url: str) -> None:
    parsed = urlparse(url)
    settings = get_settings()
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("Integration endpoint must be an absolute HTTP(S) URL")
    if settings.APP_ENV in {"staging", "production"} and parsed.scheme != "https":
        raise ValueError("Live integrations require HTTPS outside development")
    allowed = settings.integration_allowed_hosts_list
    if not allowed:
        raise ValueError("INTEGRATION_ALLOWED_HOSTS must contain the provider host")
    if parsed.hostname.lower() not in allowed:
        raise ValueError("Integration host is not allowlisted")


class GenericRestRefundProvider(RefundProvider):
    name = "generic_rest"

    @staticmethod
    def _headers(integration: IntegrationConfig, idempotency_key: str) -> dict[str, str]:
        token = _credential_value(integration.credential_ref)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def _url(integration: IntegrationConfig, key: str, **values: str) -> str:
        base = str(integration.config.get("base_url", "")).rstrip("/") + "/"
        path = str(integration.config.get(key, ""))
        if not path:
            raise ValueError(f"Integration config missing {key}")
        url = urljoin(base, path.format(**values).lstrip("/"))
        validate_live_endpoint(url)
        return url

    def execute_refund(self, integration, *, order_number, amount_usd, idempotency_key, **kwargs):
        url = self._url(integration, "refund_path")
        payload = {"order_number": order_number, "amount_usd": float(amount_usd)}
        timeout = float(integration.config.get("timeout_seconds", 10))
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                response = client.post(
                    url, headers=self._headers(integration, idempotency_key), json=payload
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            reconciled = self.reconcile_refund(integration, idempotency_key=idempotency_key)
            if reconciled.verified:
                return reconciled
            return ProviderResult(
                status="unknown",
                response={},
                unknown=True,
                error=f"provider_transport_unknown:{exc.__class__.__name__}",
            )
        body = self._safe_json(response)
        if 200 <= response.status_code < 300:
            provider_id = str(body.get("id") or body.get("refund_id") or "") or None
            reconciled = self.reconcile_refund(
                integration, idempotency_key=idempotency_key, provider_operation_id=provider_id
            )
            if reconciled.verified:
                return reconciled
            return ProviderResult(
                status="unknown",
                response=body,
                provider_operation_id=provider_id,
                unknown=True,
                error="provider_acknowledged_but_not_verified",
            )
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            return ProviderResult(
                status="retryable_failure",
                response=body,
                retryable=True,
                error=f"provider_http_{response.status_code}",
            )
        return ProviderResult(
            status="failed", response=body, error=f"provider_http_{response.status_code}"
        )

    def reconcile_refund(self, integration, *, idempotency_key, provider_operation_id=None):
        path_key = "verify_path_template" if provider_operation_id else "reconcile_path_template"
        values = {
            "provider_operation_id": provider_operation_id or "",
            "idempotency_key": idempotency_key,
        }
        url = self._url(integration, path_key, **values)
        timeout = float(integration.config.get("timeout_seconds", 10))
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                response = client.get(url, headers=self._headers(integration, idempotency_key))
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return ProviderResult(
                status="unknown",
                response={},
                unknown=True,
                error=f"reconciliation_transport_error:{exc.__class__.__name__}",
            )
        body = self._safe_json(response)
        if response.status_code == 404:
            return ProviderResult(status="not_found", response=body)
        if 200 <= response.status_code < 300:
            provider_id = (
                str(body.get("id") or body.get("refund_id") or provider_operation_id or "") or None
            )
            return ProviderResult(
                status="succeeded", response=body, provider_operation_id=provider_id, verified=True
            )
        return ProviderResult(
            status="unknown",
            response=body,
            provider_operation_id=provider_operation_id,
            unknown=True,
            error=f"reconciliation_http_{response.status_code}",
        )

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict:
        try:
            value = response.json()
            return value if isinstance(value, dict) else {"data": value}
        except ValueError:
            return {"text": response.text[:2000]}


class StripeRefundProvider(RefundProvider):
    name = "stripe"
    base_url = "https://api.stripe.com"

    @staticmethod
    def _headers(
        integration: IntegrationConfig, idempotency_key: str | None = None
    ) -> dict[str, str]:
        token = _credential_value(integration.credential_ref)
        if not token:
            raise ValueError("Stripe secret key is not configured")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        api_version = integration.config.get("api_version")
        if api_version:
            headers["Stripe-Version"] = str(api_version)
        return headers

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        try:
            body = response.json()
            return body if isinstance(body, dict) else {"data": body}
        except ValueError:
            return {"text": response.text[:2000]}

    def execute_refund(
        self,
        integration,
        *,
        order_number,
        amount_usd,
        idempotency_key,
        payment_reference=None,
        currency="USD",
        **kwargs,
    ):
        if not payment_reference:
            return ProviderResult(
                status="failed", response={}, error="stripe_payment_reference_missing"
            )
        validate_live_endpoint(f"{self.base_url}/v1/refunds")
        cents = int((amount_usd * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        form = {
            "amount": str(cents),
            "payment_intent": payment_reference,
            "reason": "requested_by_customer",
            "metadata[threshold_order_number]": order_number,
            "metadata[threshold_idempotency_key]": idempotency_key,
        }
        timeout = float(integration.config.get("timeout_seconds", 10))
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                response = client.post(
                    f"{self.base_url}/v1/refunds",
                    headers=self._headers(integration, idempotency_key),
                    content=urlencode(form),
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return ProviderResult(
                status="unknown",
                response={},
                unknown=True,
                error=f"stripe_transport_unknown:{exc.__class__.__name__}",
            )
        body = self._json(response)
        if 200 <= response.status_code < 300:
            refund_id = str(body.get("id") or "") or None
            status = str(body.get("status") or "").lower()
            verified = status == "succeeded"
            return ProviderResult(
                status="succeeded" if verified else "unknown",
                response=body,
                provider_operation_id=refund_id,
                verified=verified,
                unknown=not verified,
                error=None if verified else f"stripe_refund_status_{status or 'unknown'}",
            )
        if response.status_code in {408, 409, 429} or response.status_code >= 500:
            return ProviderResult(
                status="retryable_failure",
                response=body,
                retryable=True,
                error=f"stripe_http_{response.status_code}",
            )
        return ProviderResult(
            status="failed", response=body, error=f"stripe_http_{response.status_code}"
        )

    def reconcile_refund(self, integration, *, idempotency_key, provider_operation_id=None):
        if not provider_operation_id:
            # Stripe idempotency safely protects a repeat POST, but Threshold's UNKNOWN
            # state deliberately requires a known provider id or explicit operator review.
            return ProviderResult(
                status="unknown", response={}, unknown=True, error="stripe_refund_id_unknown"
            )
        url = f"{self.base_url}/v1/refunds/{provider_operation_id}"
        validate_live_endpoint(url)
        try:
            with httpx.Client(
                timeout=float(integration.config.get("timeout_seconds", 10)), follow_redirects=False
            ) as client:
                response = client.get(url, headers=self._headers(integration))
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return ProviderResult(
                status="unknown",
                response={},
                provider_operation_id=provider_operation_id,
                unknown=True,
                error=f"stripe_reconciliation_transport:{exc.__class__.__name__}",
            )
        body = self._json(response)
        if response.status_code == 404:
            return ProviderResult(status="not_found", response=body)
        if 200 <= response.status_code < 300:
            status = str(body.get("status") or "").lower()
            if status == "succeeded":
                return ProviderResult(
                    status="succeeded",
                    response=body,
                    provider_operation_id=provider_operation_id,
                    verified=True,
                )
            if status in {"failed", "canceled"}:
                return ProviderResult(
                    status="failed",
                    response=body,
                    provider_operation_id=provider_operation_id,
                    error=f"stripe_refund_{status}",
                )
            return ProviderResult(
                status="unknown",
                response=body,
                provider_operation_id=provider_operation_id,
                unknown=True,
                error=f"stripe_refund_status_{status or 'unknown'}",
            )
        return ProviderResult(
            status="unknown",
            response=body,
            provider_operation_id=provider_operation_id,
            unknown=True,
            error=f"stripe_reconciliation_http_{response.status_code}",
        )


class ShopifyRefundProvider(RefundProvider):
    name = "shopify"

    def _client(self, integration: IntegrationConfig):
        from app.integrations.shopify import ShopifyAdminClient

        return ShopifyAdminClient(integration)

    def execute_refund(
        self,
        integration,
        *,
        order_number,
        amount_usd,
        idempotency_key,
        external_order_id=None,
        payment_reference=None,
        payment_gateway=None,
        currency="USD",
        **kwargs,
    ):
        if not external_order_id:
            return ProviderResult(
                status="failed", response={}, error="shopify_external_order_id_missing"
            )
        if not payment_reference or not payment_gateway:
            return ProviderResult(
                status="failed", response={}, error="shopify_refund_transaction_missing"
            )
        client = self._client(integration)
        safe_key = idempotency_key.replace('"', "")
        mutation = f"""
        mutation ThresholdRefund($input: RefundInput!) {{
          refundCreate(input: $input) @idempotent(key: \"{safe_key}\") {{
            refund {{ id totalRefundedSet {{ shopMoney {{ amount currencyCode }} }} }}
            userErrors {{ field message }}
          }}
        }}
        """
        variables = {
            "input": {
                "orderId": external_order_id,
                "note": f"Threshold controlled refund for {order_number}",
                "transactions": [
                    {
                        "orderId": external_order_id,
                        "parentId": payment_reference,
                        "gateway": payment_gateway,
                        "kind": "REFUND",
                        "amount": f"{amount_usd:.2f}",
                    }
                ],
            }
        }
        try:
            data = client._graphql(mutation, variables)
        except httpx.HTTPError as exc:
            return ProviderResult(
                status="unknown",
                response={},
                unknown=True,
                error=f"shopify_transport_unknown:{exc.__class__.__name__}",
            )
        except ValueError as exc:
            return ProviderResult(status="failed", response={}, error=str(exc))
        payload = data.get("refundCreate") or {}
        errors = payload.get("userErrors") or []
        if errors:
            return ProviderResult(
                status="failed", response=payload, error="shopify_refund_user_error"
            )
        refund = payload.get("refund") or {}
        refund_id = str(refund.get("id") or "") or None
        if not refund_id:
            return ProviderResult(
                status="unknown", response=payload, unknown=True, error="shopify_refund_id_missing"
            )
        return ProviderResult(
            status="succeeded", response=payload, provider_operation_id=refund_id, verified=True
        )

    def reconcile_refund(self, integration, *, idempotency_key, provider_operation_id=None):
        if not provider_operation_id:
            return ProviderResult(
                status="unknown", response={}, unknown=True, error="shopify_refund_id_unknown"
            )
        client = self._client(integration)
        query = """
        query ThresholdRefundVerify($id: ID!) {
          node(id: $id) {
            ... on Refund { id totalRefundedSet { shopMoney { amount currencyCode } } }
          }
        }
        """
        try:
            data = client._graphql(query, {"id": provider_operation_id})
        except httpx.HTTPError as exc:
            return ProviderResult(
                status="unknown",
                response={},
                provider_operation_id=provider_operation_id,
                unknown=True,
                error=f"shopify_reconciliation_transport:{exc.__class__.__name__}",
            )
        node = data.get("node")
        if not node:
            return ProviderResult(status="not_found", response={})
        return ProviderResult(
            status="succeeded",
            response=node,
            provider_operation_id=provider_operation_id,
            verified=True,
        )


def get_refund_provider(integration: IntegrationConfig) -> RefundProvider:
    if integration.provider == IntegrationProvider.MOCK_PAYMENTS:
        return MockRefundProvider()
    if integration.provider == IntegrationProvider.GENERIC_REST:
        return GenericRestRefundProvider()
    if integration.provider == IntegrationProvider.STRIPE:
        return StripeRefundProvider()
    if integration.provider == IntegrationProvider.SHOPIFY:
        return ShopifyRefundProvider()
    raise ValueError(f"Provider {integration.provider.value} does not support refunds")
