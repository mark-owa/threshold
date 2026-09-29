from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.integrations import providers
from app.integrations.providers import (
    GenericRestRefundProvider,
    MockRefundProvider,
    ProviderResult,
    RefundProvider,
    ShopifyRefundProvider,
    StripeRefundProvider,
    get_refund_provider,
    validate_live_endpoint,
)
from app.models import IntegrationConfig
from app.models.enums import IntegrationProvider


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload
        self.text = text

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeHttpClient:
    response = FakeResponse(200, {})
    error = None
    calls = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        self.__class__.calls.append(("post", url, kwargs))
        if self.__class__.error:
            raise self.__class__.error
        return self.__class__.response

    def get(self, url, **kwargs):
        self.__class__.calls.append(("get", url, kwargs))
        if self.__class__.error:
            raise self.__class__.error
        return self.__class__.response


def integration(provider, **config):
    return IntegrationConfig(
        id=uuid4(),
        organization_id=uuid4(),
        provider=provider,
        credential_ref="TEST_KEY",
        config=config,
        is_enabled=True,
    )


def set_http(monkeypatch, response, error=None):
    FakeHttpClient.response = response
    FakeHttpClient.error = error
    FakeHttpClient.calls = []
    monkeypatch.setattr(providers.httpx, "Client", FakeHttpClient)


def test_base_and_mock_provider_contracts():
    base = RefundProvider()
    with pytest.raises(NotImplementedError):
        base.execute_refund(
            SimpleNamespace(),
            order_number="O-1",
            amount_usd=Decimal("1"),
            idempotency_key="k",
        )
    with pytest.raises(NotImplementedError):
        base.reconcile_refund(SimpleNamespace(), idempotency_key="k")

    mock = MockRefundProvider()
    result = mock.execute_refund(
        SimpleNamespace(),
        order_number="O-1",
        amount_usd=Decimal("1"),
        idempotency_key="k",
    )
    assert result.verified and result.provider_operation_id
    assert mock.reconcile_refund(
        SimpleNamespace(), idempotency_key="k", provider_operation_id="rf_1"
    ).verified
    unknown = mock.reconcile_refund(SimpleNamespace(), idempotency_key="k")
    assert unknown.unknown and unknown.error == "missing_provider_id"


@pytest.mark.parametrize(
    ("url", "settings", "message"),
    [
        (
            "relative/path",
            SimpleNamespace(APP_ENV="development", integration_allowed_hosts_list=["api.example"]),
            "absolute",
        ),
        (
            "http://api.example/refund",
            SimpleNamespace(APP_ENV="production", integration_allowed_hosts_list=["api.example"]),
            "HTTPS",
        ),
        (
            "https://api.example/refund",
            SimpleNamespace(APP_ENV="development", integration_allowed_hosts_list=[]),
            "ALLOWED_HOSTS",
        ),
        (
            "https://evil.example/refund",
            SimpleNamespace(APP_ENV="development", integration_allowed_hosts_list=["api.example"]),
            "allowlisted",
        ),
    ],
)
def test_validate_live_endpoint_rejects_invalid_targets(monkeypatch, url, settings, message):
    monkeypatch.setattr(providers, "get_settings", lambda: settings)
    with pytest.raises(ValueError, match=message):
        validate_live_endpoint(url)


def test_validate_live_endpoint_accepts_allowlisted_https(monkeypatch):
    settings = SimpleNamespace(APP_ENV="production", integration_allowed_hosts_list=["api.example"])
    monkeypatch.setattr(providers, "get_settings", lambda: settings)
    validate_live_endpoint("https://api.example/refund")


def test_generic_headers_urls_and_json(monkeypatch):
    row = integration(
        IntegrationProvider.GENERIC_REST,
        base_url="https://api.example",
        refund_path="/refunds",
        verify_path_template="/refunds/{provider_operation_id}",
        reconcile_path_template="/lookup/{idempotency_key}",
    )
    monkeypatch.setenv("THRESHOLD_INTEGRATION_SECRET__TEST_KEY", "token")
    headers = GenericRestRefundProvider._headers(row, "idem")
    assert headers["Authorization"] == "Bearer token"
    monkeypatch.delenv("THRESHOLD_INTEGRATION_SECRET__TEST_KEY")
    assert "Authorization" not in GenericRestRefundProvider._headers(row, "idem")

    seen = []
    monkeypatch.setattr(providers, "validate_live_endpoint", seen.append)
    assert GenericRestRefundProvider._url(row, "refund_path") == "https://api.example/refunds"
    assert seen == ["https://api.example/refunds"]
    with pytest.raises(ValueError, match="missing"):
        GenericRestRefundProvider._url(row, "missing")

    assert GenericRestRefundProvider._safe_json(FakeResponse(payload=[1])) == {"data": [1]}
    assert GenericRestRefundProvider._safe_json(
        FakeResponse(payload=ValueError("bad"), text="not-json")
    ) == {"text": "not-json"}


def test_generic_execute_and_reconcile_outcomes(monkeypatch):
    row = integration(
        IntegrationProvider.GENERIC_REST,
        base_url="https://api.example",
        refund_path="/refunds",
        verify_path_template="/refunds/{provider_operation_id}",
        reconcile_path_template="/lookup/{idempotency_key}",
    )
    monkeypatch.setattr(providers, "validate_live_endpoint", lambda url: None)
    provider = GenericRestRefundProvider()

    set_http(monkeypatch, FakeResponse(200, {"id": "r1"}))
    monkeypatch.setattr(
        provider,
        "reconcile_refund",
        lambda *args, **kwargs: ProviderResult(
            status="succeeded", response={"id": "r1"}, verified=True
        ),
    )
    assert provider.execute_refund(
        row, order_number="O-1", amount_usd=Decimal("2.50"), idempotency_key="idem"
    ).verified

    set_http(monkeypatch, FakeResponse(200, {"id": "r2"}))
    monkeypatch.setattr(
        provider,
        "reconcile_refund",
        lambda *args, **kwargs: ProviderResult(status="unknown", response={}),
    )
    assert provider.execute_refund(
        row, order_number="O-1", amount_usd=Decimal("2.50"), idempotency_key="idem"
    ).unknown

    set_http(monkeypatch, FakeResponse(429, {"error": "slow"}))
    assert provider.execute_refund(
        row, order_number="O-1", amount_usd=Decimal("2.50"), idempotency_key="idem"
    ).retryable

    set_http(monkeypatch, FakeResponse(400, {"error": "bad"}))
    assert provider.execute_refund(
        row, order_number="O-1", amount_usd=Decimal("2.50"), idempotency_key="idem"
    ).status == "failed"

    error = httpx.ConnectError("down", request=httpx.Request("POST", "https://api.example"))
    set_http(monkeypatch, FakeResponse(), error=error)
    monkeypatch.setattr(
        provider,
        "reconcile_refund",
        lambda *args, **kwargs: ProviderResult(status="unknown", response={}),
    )
    assert provider.execute_refund(
        row, order_number="O-1", amount_usd=Decimal("2.50"), idempotency_key="idem"
    ).unknown


def test_generic_reconcile_outcomes(monkeypatch):
    row = integration(
        IntegrationProvider.GENERIC_REST,
        base_url="https://api.example",
        refund_path="/refunds",
        verify_path_template="/refunds/{provider_operation_id}",
        reconcile_path_template="/lookup/{idempotency_key}",
    )
    monkeypatch.setattr(providers, "validate_live_endpoint", lambda url: None)
    provider = GenericRestRefundProvider()

    set_http(monkeypatch, FakeResponse(404, {}))
    assert provider.reconcile_refund(
        row, idempotency_key="idem", provider_operation_id="r1"
    ).status == "not_found"

    set_http(monkeypatch, FakeResponse(200, {"refund_id": "r1"}))
    assert provider.reconcile_refund(
        row, idempotency_key="idem", provider_operation_id="r1"
    ).verified

    set_http(monkeypatch, FakeResponse(503, {}))
    assert provider.reconcile_refund(
        row, idempotency_key="idem", provider_operation_id="r1"
    ).unknown

    error = httpx.ConnectError("down", request=httpx.Request("GET", "https://api.example"))
    set_http(monkeypatch, FakeResponse(), error=error)
    assert provider.reconcile_refund(row, idempotency_key="idem").unknown


def test_stripe_headers_json_and_execute(monkeypatch):
    row = integration(IntegrationProvider.STRIPE, api_version="2026-07")
    monkeypatch.setenv("THRESHOLD_INTEGRATION_SECRET__TEST_KEY", "sk_test")
    headers = StripeRefundProvider._headers(row, "idem")
    assert headers["Authorization"] == "Bearer sk_test"
    assert headers["Idempotency-Key"] == "idem"
    assert headers["Stripe-Version"] == "2026-07"
    monkeypatch.delenv("THRESHOLD_INTEGRATION_SECRET__TEST_KEY")
    with pytest.raises(ValueError, match="not configured"):
        StripeRefundProvider._headers(row)

    assert StripeRefundProvider._json(FakeResponse(payload=[1])) == {"data": [1]}
    assert StripeRefundProvider._json(
        FakeResponse(payload=ValueError("bad"), text="oops")
    ) == {"text": "oops"}

    monkeypatch.setenv("THRESHOLD_INTEGRATION_SECRET__TEST_KEY", "sk_test")
    monkeypatch.setattr(providers, "validate_live_endpoint", lambda url: None)
    provider = StripeRefundProvider()
    missing = provider.execute_refund(
        row, order_number="O-1", amount_usd=Decimal("2"), idempotency_key="idem"
    )
    assert missing.error == "stripe_payment_reference_missing"

    set_http(monkeypatch, FakeResponse(200, {"id": "re_1", "status": "succeeded"}))
    success = provider.execute_refund(
        row,
        order_number="O-1",
        amount_usd=Decimal("2.50"),
        idempotency_key="idem",
        payment_reference="pi_1",
    )
    assert success.verified and success.provider_operation_id == "re_1"

    set_http(monkeypatch, FakeResponse(200, {"id": "re_2", "status": "pending"}))
    assert provider.execute_refund(
        row,
        order_number="O-1",
        amount_usd=Decimal("2.50"),
        idempotency_key="idem",
        payment_reference="pi_1",
    ).unknown

    set_http(monkeypatch, FakeResponse(429, {}))
    assert provider.execute_refund(
        row,
        order_number="O-1",
        amount_usd=Decimal("2.50"),
        idempotency_key="idem",
        payment_reference="pi_1",
    ).retryable

    set_http(monkeypatch, FakeResponse(400, {}))
    assert provider.execute_refund(
        row,
        order_number="O-1",
        amount_usd=Decimal("2.50"),
        idempotency_key="idem",
        payment_reference="pi_1",
    ).status == "failed"


def test_stripe_reconcile_outcomes(monkeypatch):
    row = integration(IntegrationProvider.STRIPE)
    monkeypatch.setenv("THRESHOLD_INTEGRATION_SECRET__TEST_KEY", "sk_test")
    monkeypatch.setattr(providers, "validate_live_endpoint", lambda url: None)
    provider = StripeRefundProvider()
    assert provider.reconcile_refund(row, idempotency_key="idem").unknown

    set_http(monkeypatch, FakeResponse(404, {}))
    assert provider.reconcile_refund(
        row, idempotency_key="idem", provider_operation_id="re_1"
    ).status == "not_found"

    set_http(monkeypatch, FakeResponse(200, {"status": "succeeded"}))
    assert provider.reconcile_refund(
        row, idempotency_key="idem", provider_operation_id="re_1"
    ).verified

    set_http(monkeypatch, FakeResponse(200, {"status": "failed"}))
    assert provider.reconcile_refund(
        row, idempotency_key="idem", provider_operation_id="re_1"
    ).status == "failed"

    set_http(monkeypatch, FakeResponse(200, {"status": "pending"}))
    assert provider.reconcile_refund(
        row, idempotency_key="idem", provider_operation_id="re_1"
    ).unknown

    set_http(monkeypatch, FakeResponse(500, {}))
    assert provider.reconcile_refund(
        row, idempotency_key="idem", provider_operation_id="re_1"
    ).unknown


class FakeShopifyClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def _graphql(self, query, variables):
        if self.error:
            raise self.error
        return self.result


def test_shopify_execute_and_reconcile(monkeypatch):
    row = integration(IntegrationProvider.SHOPIFY)
    provider = ShopifyRefundProvider()

    assert provider.execute_refund(
        row, order_number="O-1", amount_usd=Decimal("2"), idempotency_key="idem"
    ).error == "shopify_external_order_id_missing"
    assert provider.execute_refund(
        row,
        order_number="O-1",
        amount_usd=Decimal("2"),
        idempotency_key="idem",
        external_order_id="gid://order/1",
    ).error == "shopify_refund_transaction_missing"

    success_payload = {"refundCreate": {"refund": {"id": "gid://refund/1"}, "userErrors": []}}
    monkeypatch.setattr(provider, "_client", lambda integration: FakeShopifyClient(success_payload))
    result = provider.execute_refund(
        row,
        order_number="O-1",
        amount_usd=Decimal("2"),
        idempotency_key='id"em',
        external_order_id="gid://order/1",
        payment_reference="gid://txn/1",
        payment_gateway="shopify_payments",
    )
    assert result.verified and result.provider_operation_id == "gid://refund/1"

    monkeypatch.setattr(
        provider,
        "_client",
        lambda integration: FakeShopifyClient(
            {"refundCreate": {"refund": None, "userErrors": [{"message": "bad"}]}}
        ),
    )
    assert provider.execute_refund(
        row,
        order_number="O-1",
        amount_usd=Decimal("2"),
        idempotency_key="idem",
        external_order_id="gid://order/1",
        payment_reference="gid://txn/1",
        payment_gateway="shopify_payments",
    ).status == "failed"

    monkeypatch.setattr(
        provider,
        "_client",
        lambda integration: FakeShopifyClient({"refundCreate": {"refund": {}, "userErrors": []}}),
    )
    assert provider.execute_refund(
        row,
        order_number="O-1",
        amount_usd=Decimal("2"),
        idempotency_key="idem",
        external_order_id="gid://order/1",
        payment_reference="gid://txn/1",
        payment_gateway="shopify_payments",
    ).unknown

    assert provider.reconcile_refund(row, idempotency_key="idem").unknown
    monkeypatch.setattr(
        provider, "_client", lambda integration: FakeShopifyClient({"node": {"id": "gid://refund/1"}})
    )
    assert provider.reconcile_refund(
        row, idempotency_key="idem", provider_operation_id="gid://refund/1"
    ).verified
    monkeypatch.setattr(provider, "_client", lambda integration: FakeShopifyClient({"node": None}))
    assert provider.reconcile_refund(
        row, idempotency_key="idem", provider_operation_id="gid://refund/1"
    ).status == "not_found"


def test_provider_selection():
    assert isinstance(
        get_refund_provider(integration(IntegrationProvider.MOCK_PAYMENTS)), MockRefundProvider
    )
    assert isinstance(
        get_refund_provider(integration(IntegrationProvider.GENERIC_REST)),
        GenericRestRefundProvider,
    )
    assert isinstance(
        get_refund_provider(integration(IntegrationProvider.STRIPE)), StripeRefundProvider
    )
    assert isinstance(
        get_refund_provider(integration(IntegrationProvider.SHOPIFY)), ShopifyRefundProvider
    )
