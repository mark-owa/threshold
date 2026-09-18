from types import SimpleNamespace

import app.core.config as config
from app.integrations import providers


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise providers.httpx.HTTPStatusError(
                "vault error",
                request=providers.httpx.Request("GET", "https://vault.example.com/secrets"),
                response=providers.httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


class FakeClient:
    calls = []
    response = FakeResponse(payload={"secret": "vault-token"})

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, *, headers=None, params=None):
        self.__class__.calls.append({"url": url, "headers": headers or {}, "params": params or {}})
        return self.__class__.response


def _settings(**overrides):
    values = {
        "OAUTH_SECRET_SINK_URL": "https://vault.example.com/secrets",
        "OAUTH_SECRET_SINK_AUTH_REF": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_environment_credential_precedes_vault(monkeypatch):
    monkeypatch.setenv("THRESHOLD_INTEGRATION_SECRET__SHOPIFY_ORG_TEST", "env-token")
    monkeypatch.setattr(config, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("vault must not be called")),
    )

    assert providers._credential_value("SHOPIFY_ORG_TEST") == "env-token"


def test_oauth_managed_credential_reads_from_vault(monkeypatch):
    monkeypatch.delenv("THRESHOLD_INTEGRATION_SECRET__SHOPIFY_ORG_TEST", raising=False)
    monkeypatch.setenv("THRESHOLD_INTEGRATION_SECRET__VAULT_AUTH", "vault-auth-token")
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: _settings(OAUTH_SECRET_SINK_AUTH_REF="VAULT_AUTH"),
    )
    monkeypatch.setattr(providers, "validate_live_endpoint", lambda url: None)
    FakeClient.calls = []
    FakeClient.response = FakeResponse(payload={"secret": "vault-token"})
    monkeypatch.setattr(providers.httpx, "Client", FakeClient)

    assert providers._credential_value("SHOPIFY_ORG_TEST") == "vault-token"
    assert FakeClient.calls == [
        {
            "url": "https://vault.example.com/secrets",
            "headers": {
                "Accept": "application/json",
                "Authorization": "Bearer vault-auth-token",
            },
            "params": {"reference": "SHOPIFY_ORG_TEST"},
        }
    ]


def test_vault_lookup_fails_closed(monkeypatch):
    monkeypatch.delenv("THRESHOLD_INTEGRATION_SECRET__SHOPIFY_ORG_TEST", raising=False)
    monkeypatch.setattr(config, "get_settings", lambda: _settings())
    monkeypatch.setattr(providers, "validate_live_endpoint", lambda url: None)
    FakeClient.calls = []
    FakeClient.response = FakeResponse(status_code=404)
    monkeypatch.setattr(providers.httpx, "Client", FakeClient)

    assert providers._credential_value("SHOPIFY_ORG_TEST") is None
