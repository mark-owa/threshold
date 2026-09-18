import inspect
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.integrations import shopify
from app.models import IntegrationConfig
from app.models.enums import IntegrationProvider


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = shopify.httpx.Request("POST", "https://shop.myshopify.com/admin/oauth/access_token")
            response = shopify.httpx.Response(self.status_code, request=request)
            raise shopify.httpx.HTTPStatusError("HTTP error", request=request, response=response)


class FakeHttpClient:
    calls = []
    response = FakeResponse()

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        self.__class__.calls.append({"url": url, **kwargs})
        return self.__class__.response


class FakeSession:
    def __init__(self, integration):
        self.integration = integration
        self.flush_count = 0

    def scalar(self, statement):
        return self.integration

    def flush(self):
        self.flush_count += 1


def _settings():
    return SimpleNamespace(
        SHOPIFY_CLIENT_ID="client-id",
        SHOPIFY_CLIENT_SECRET="client-secret",
        OAUTH_SECRET_SINK_URL="https://vault.example.com/secrets",
        OAUTH_SECRET_SINK_AUTH_REF="",
    )


def _bundle(access="access-old", refresh="refresh-old", *, expired=False):
    now = datetime.now(UTC)
    return {
        "version": 1,
        "mode": shopify.SHOPIFY_EXPIRING_OFFLINE_BUNDLE,
        "access_token": access,
        "refresh_token": refresh,
        "access_token_expires_at": (
            now - timedelta(minutes=1) if expired else now + timedelta(minutes=30)
        ).isoformat(),
        "refresh_token_expires_at": (now + timedelta(days=30)).isoformat(),
    }


def test_build_shopify_expiring_bundle_requires_rotating_pair():
    now = datetime(2026, 9, 18, tzinfo=UTC)
    bundle = shopify.build_shopify_token_bundle(
        {
            "access_token": "access-new",
            "refresh_token": "refresh-new",
            "expires_in": 3600,
            "refresh_token_expires_in": 7776000,
        },
        now=now,
    )
    assert bundle["mode"] == shopify.SHOPIFY_EXPIRING_OFFLINE_BUNDLE
    assert bundle["access_token"] == "access-new"
    assert bundle["refresh_token"] == "refresh-new"
    assert datetime.fromisoformat(bundle["access_token_expires_at"]) == now + timedelta(hours=1)
    assert datetime.fromisoformat(bundle["refresh_token_expires_at"]) == now + timedelta(days=90)


def test_shopify_callback_requests_expiring_offline_tokens():
    from app.api import commercial

    source = inspect.getsource(commercial.shopify_callback)
    assert '"expiring": "1"' in source
    assert "build_shopify_token_bundle(token_body)" in source
    assert "store_oauth_secret(" in source


def test_shopify_client_refreshes_bundle_and_rotates_once(monkeypatch):
    integration = IntegrationConfig(
        id=uuid4(),
        organization_id=uuid4(),
        provider=IntegrationProvider.SHOPIFY,
        credential_ref="SHOPIFY_ORG_TEST",
        is_enabled=True,
        config={
            "shop_domain": "refresh-test.myshopify.com",
            "api_version": "2026-07",
            "oauth_managed": True,
            "oauth_token_mode": shopify.SHOPIFY_EXPIRING_OFFLINE_BUNDLE,
        },
    )
    old_bundle = _bundle(expired=True)
    fake_session = FakeSession(integration)
    stored = []

    monkeypatch.setattr(shopify, "get_settings", _settings)
    monkeypatch.setattr(shopify, "validate_live_endpoint", lambda url: None)
    monkeypatch.setattr(shopify, "object_session", lambda obj: fake_session)
    monkeypatch.setattr(shopify, "_credential_value", lambda ref: json.dumps(old_bundle))
    monkeypatch.setattr(
        shopify,
        "store_oauth_secret",
        lambda reference, secret, metadata: stored.append((reference, json.loads(secret), metadata)),
    )
    FakeHttpClient.calls = []
    FakeHttpClient.response = FakeResponse(
        payload={
            "access_token": "access-new",
            "refresh_token": "refresh-new",
            "expires_in": 3600,
            "refresh_token_expires_in": 7776000,
            "scope": "read_orders,write_orders",
        }
    )
    monkeypatch.setattr(shopify.httpx, "Client", FakeHttpClient)

    client = shopify.ShopifyAdminClient(integration)
    client._ensure_fresh_token()

    assert client.token == "access-new"
    assert len(FakeHttpClient.calls) == 1
    refresh_call = FakeHttpClient.calls[0]
    assert refresh_call["data"]["grant_type"] == "refresh_token"
    assert refresh_call["data"]["refresh_token"] == "refresh-old"
    assert stored[0][0] == "SHOPIFY_ORG_TEST"
    assert stored[0][1]["access_token"] == "access-new"
    assert stored[0][1]["refresh_token"] == "refresh-new"
    assert integration.config["reauthorization_required"] is False
    assert fake_session.flush_count == 1


def test_shopify_refresh_401_marks_reauthorization_required(monkeypatch):
    integration = IntegrationConfig(
        id=uuid4(),
        organization_id=uuid4(),
        provider=IntegrationProvider.SHOPIFY,
        credential_ref="SHOPIFY_ORG_TEST",
        is_enabled=True,
        config={
            "shop_domain": "refresh-test.myshopify.com",
            "api_version": "2026-07",
            "oauth_managed": True,
            "oauth_token_mode": shopify.SHOPIFY_EXPIRING_OFFLINE_BUNDLE,
        },
    )
    old_bundle = _bundle(expired=True)
    fake_session = FakeSession(integration)

    monkeypatch.setattr(shopify, "get_settings", _settings)
    monkeypatch.setattr(shopify, "validate_live_endpoint", lambda url: None)
    monkeypatch.setattr(shopify, "object_session", lambda obj: fake_session)
    monkeypatch.setattr(shopify, "_credential_value", lambda ref: json.dumps(old_bundle))
    FakeHttpClient.calls = []
    FakeHttpClient.response = FakeResponse(status_code=401, payload={"error": "invalid_request"})
    monkeypatch.setattr(shopify.httpx, "Client", FakeHttpClient)

    client = shopify.ShopifyAdminClient(integration)
    try:
        client._ensure_fresh_token()
    except ValueError as exc:
        assert str(exc) == "shopify_reauthorization_required"
    else:
        raise AssertionError("Expected refresh-token rejection to require reauthorization")

    assert integration.config["reauthorization_required"] is True
    assert fake_session.flush_count == 1
