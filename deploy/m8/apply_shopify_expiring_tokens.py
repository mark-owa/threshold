from pathlib import Path

ROOT = Path("/app")

shopify_path = ROOT / "app/integrations/shopify.py"
shopify = shopify_path.read_text()

shopify = shopify.replace(
    "import hmac\nimport re\n",
    "import hmac\nimport json\nimport os\nimport re\n",
    1,
)
shopify = shopify.replace(
    "from datetime import UTC, datetime\n",
    "from datetime import UTC, datetime, timedelta\n",
    1,
)
shopify = shopify.replace(
    "from sqlalchemy.orm import Session\n",
    "from sqlalchemy.orm import Session, object_session\n",
    1,
)
shopify = shopify.replace(
    "from app.integrations.providers import _credential_value, validate_live_endpoint\n",
    "from app.core.config import get_settings\n"
    "from app.integrations.providers import _credential_value, validate_live_endpoint\n",
    1,
)

client_marker = "class ShopifyAdminClient:\n"
if client_marker not in shopify:
    raise SystemExit("ShopifyAdminClient marker not found; refusing unsafe expiring-token patch")

helpers = r'''
SHOPIFY_EXPIRING_OFFLINE_BUNDLE = "expiring_offline_bundle"


def build_shopify_token_bundle(token_body: dict, *, now: datetime | None = None) -> dict:
    access_token = token_body.get("access_token")
    refresh_token = token_body.get("refresh_token")
    try:
        expires_in = int(token_body.get("expires_in"))
        refresh_expires_in = int(token_body.get("refresh_token_expires_in"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Shopify expiring token response is missing token lifetimes") from exc
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("Shopify expiring token response is missing access_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise ValueError("Shopify expiring token response is missing refresh_token")
    if expires_in <= 0 or refresh_expires_in <= 0:
        raise ValueError("Shopify token lifetimes must be positive")
    issued_at = now or datetime.now(UTC)
    return {
        "version": 1,
        "mode": SHOPIFY_EXPIRING_OFFLINE_BUNDLE,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_token_expires_at": (issued_at + timedelta(seconds=expires_in)).isoformat(),
        "refresh_token_expires_at": (issued_at + timedelta(seconds=refresh_expires_in)).isoformat(),
    }


def decode_shopify_token_bundle(raw_secret: str) -> dict:
    try:
        value = json.loads(raw_secret)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Shopify OAuth credential bundle is malformed") from exc
    if not isinstance(value, dict) or value.get("mode") != SHOPIFY_EXPIRING_OFFLINE_BUNDLE:
        raise ValueError("Shopify OAuth credential bundle has unsupported format")
    if not isinstance(value.get("access_token"), str) or not value["access_token"]:
        raise ValueError("Shopify OAuth credential bundle is missing access token")
    if not isinstance(value.get("refresh_token"), str) or not value["refresh_token"]:
        raise ValueError("Shopify OAuth credential bundle is missing refresh token")
    return value


def _token_deadline(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("Shopify OAuth credential bundle is missing expiry metadata")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _oauth_vault_headers() -> dict[str, str]:
    settings = get_settings()
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    auth_ref = str(settings.OAUTH_SECRET_SINK_AUTH_REF or "").strip()
    if auth_ref:
        auth_value = os.getenv(f"THRESHOLD_INTEGRATION_SECRET__{auth_ref.upper()}")
        if not auth_value:
            raise ValueError("OAuth vault authentication credential is unavailable")
        headers["Authorization"] = f"Bearer {auth_value}"
    return headers


def store_oauth_secret(reference: str, secret: str, metadata: dict) -> None:
    settings = get_settings()
    vault_url = str(settings.OAUTH_SECRET_SINK_URL or "").strip()
    if not vault_url:
        raise ValueError("OAuth token vault sink is not configured")
    validate_live_endpoint(vault_url)
    headers = _oauth_vault_headers()
    last_error: Exception | None = None
    for _attempt in range(3):
        try:
            with httpx.Client(timeout=5, follow_redirects=False) as client:
                response = client.post(
                    vault_url,
                    headers=headers,
                    json={"reference": reference, "secret": secret, "metadata": metadata},
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            continue
        if 200 <= response.status_code < 300:
            return
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            last_error = RuntimeError(f"OAuth vault transient HTTP {response.status_code}")
            continue
        response.raise_for_status()
    raise RuntimeError("OAuth vault write failed after retries") from last_error


'''
shopify = shopify.replace(client_marker, helpers + client_marker, 1)

old_client = '''class ShopifyAdminClient:
    def __init__(self, integration: IntegrationConfig):
        self.integration = integration
        self.shop_domain = normalize_shopify_domain(str(integration.config.get("shop_domain", "")))
        self.api_version = str(integration.config.get("api_version", "2026-07"))
        self.token = _credential_value(integration.credential_ref)
        if not self.token:
            raise ValueError("Shopify access token secret is not configured")
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
'''

new_client = '''class ShopifyAdminClient:
    def __init__(self, integration: IntegrationConfig):
        self.integration = integration
        self.shop_domain = normalize_shopify_domain(str(integration.config.get("shop_domain", "")))
        self.api_version = str(integration.config.get("api_version", "2026-07"))
        raw_secret = _credential_value(integration.credential_ref)
        if not raw_secret:
            raise ValueError("Shopify access token secret is not configured")
        self.token_bundle = None
        if (integration.config or {}).get("oauth_token_mode") == SHOPIFY_EXPIRING_OFFLINE_BUNDLE:
            self.token_bundle = decode_shopify_token_bundle(raw_secret)
            self.token = self.token_bundle["access_token"]
        else:
            self.token = raw_secret
        self.url = f"https://{self.shop_domain}/admin/api/{self.api_version}/graphql.json"
        validate_live_endpoint(self.url)

    def _mark_reauthorization_required(self, integration: IntegrationConfig, db: Session) -> None:
        integration.config = {
            **(integration.config or {}),
            "reauthorization_required": True,
        }
        db.flush()

    def _refresh_expiring_token(self) -> None:
        if (self.integration.config or {}).get("oauth_token_mode") != SHOPIFY_EXPIRING_OFFLINE_BUNDLE:
            raise ValueError("shopify_reauthorization_required")
        db = object_session(self.integration)
        if db is None:
            raise ValueError("Shopify OAuth refresh requires an active database session")
        locked = db.scalar(
            select(IntegrationConfig)
            .where(IntegrationConfig.id == self.integration.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked is None:
            raise ValueError("Shopify integration no longer exists")
        raw_secret = _credential_value(locked.credential_ref)
        if not raw_secret:
            self._mark_reauthorization_required(locked, db)
            raise ValueError("shopify_reauthorization_required")
        bundle = decode_shopify_token_bundle(raw_secret)

        # A concurrent worker may have refreshed while this caller waited on the
        # row lock. Reuse the newly persisted access token instead of rotating
        # the refresh token a second time.
        if bundle["access_token"] != self.token:
            self.integration = locked
            self.token_bundle = bundle
            self.token = bundle["access_token"]
            return

        if _token_deadline(bundle["refresh_token_expires_at"]) <= datetime.now(UTC):
            self._mark_reauthorization_required(locked, db)
            raise ValueError("shopify_reauthorization_required")

        settings = get_settings()
        if not settings.SHOPIFY_CLIENT_ID or not settings.SHOPIFY_CLIENT_SECRET:
            raise ValueError("Shopify OAuth app credentials are not configured")
        token_url = f"https://{self.shop_domain}/admin/oauth/access_token"
        validate_live_endpoint(token_url)
        timeout = float(locked.config.get("timeout_seconds", 10))
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.post(
                token_url,
                headers={"Accept": "application/json"},
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.SHOPIFY_CLIENT_ID,
                    "client_secret": settings.SHOPIFY_CLIENT_SECRET,
                    "refresh_token": bundle["refresh_token"],
                },
            )
        if response.status_code == 401:
            self._mark_reauthorization_required(locked, db)
            raise ValueError("shopify_reauthorization_required")
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            response.raise_for_status()
        if not 200 <= response.status_code < 300:
            raise ValueError(f"shopify_token_refresh_http_{response.status_code}")
        new_bundle = build_shopify_token_bundle(response.json())
        # Persist the access+refresh pair as one opaque secret. This avoids
        # splitting a rotated credential pair across independent vault writes.
        store_oauth_secret(
            locked.credential_ref,
            json.dumps(new_bundle, separators=(",", ":")),
            {
                "provider": "shopify",
                "shop": self.shop_domain,
                "organization_id": str(locked.organization_id),
                "token_mode": SHOPIFY_EXPIRING_OFFLINE_BUNDLE,
            },
        )
        locked.config = {
            **(locked.config or {}),
            "oauth_token_mode": SHOPIFY_EXPIRING_OFFLINE_BUNDLE,
            "access_token_expires_at": new_bundle["access_token_expires_at"],
            "refresh_token_expires_at": new_bundle["refresh_token_expires_at"],
            "reauthorization_required": False,
        }
        db.flush()
        self.integration = locked
        self.token_bundle = new_bundle
        self.token = new_bundle["access_token"]

    def _ensure_fresh_token(self) -> None:
        if self.token_bundle is None:
            return
        # Refresh five minutes early so background jobs do not begin with a
        # credential that will expire during a provider call.
        if _token_deadline(self.token_bundle["access_token_expires_at"]) <= datetime.now(UTC) + timedelta(minutes=5):
            self._refresh_expiring_token()

    def _post_graphql(self, query: str, variables: dict) -> httpx.Response:
        timeout = float(self.integration.config.get("timeout_seconds", 10))
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            return client.post(
                self.url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Shopify-Access-Token": self.token,
                },
                json={"query": query, "variables": variables},
            )

    def _graphql(self, query: str, variables: dict) -> dict:
        self._ensure_fresh_token()
        response = self._post_graphql(query, variables)
        if response.status_code == 401 and self.token_bundle is not None:
            self._refresh_expiring_token()
            response = self._post_graphql(query, variables)
        if response.status_code == 403 and "Non-expiring access tokens are no longer accepted" in response.text:
            raise ValueError("shopify_reauthorization_required")
        response.raise_for_status()
        body = response.json()
        if body.get("errors"):
            raise ValueError(f"Shopify GraphQL error: {body['errors']}")
        return body.get("data") or {}
'''
if old_client not in shopify:
    raise SystemExit("Expected ShopifyAdminClient source block not found; refusing unsafe expiring-token patch")
shopify = shopify.replace(old_client, new_client, 1)
shopify_path.write_text(shopify)

commercial_path = ROOT / "app/api/commercial.py"
commercial = commercial_path.read_text()

old_import = "from app.integrations.shopify import normalize_shopify_domain, verify_shopify_callback_hmac\n"
new_import = (
    "from app.integrations.shopify import (\n"
    "    SHOPIFY_EXPIRING_OFFLINE_BUNDLE,\n"
    "    build_shopify_token_bundle,\n"
    "    normalize_shopify_domain,\n"
    "    store_oauth_secret,\n"
    "    verify_shopify_callback_hmac,\n"
    ")\n"
)
if old_import not in commercial:
    raise SystemExit("Expected Shopify import not found in commercial.py")
commercial = commercial.replace(old_import, new_import, 1)

old_exchange = '            token_response = client.post(token_url, json={"client_id": settings.SHOPIFY_CLIENT_ID, "client_secret": settings.SHOPIFY_CLIENT_SECRET, "code": code})\n'
new_exchange = '''            token_response = client.post(
                token_url,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.SHOPIFY_CLIENT_ID,
                    "client_secret": settings.SHOPIFY_CLIENT_SECRET,
                    "code": code,
                    "expiring": "1",
                },
            )
'''
if old_exchange not in commercial:
    raise SystemExit("Expected Shopify token exchange call not found")
commercial = commercial.replace(old_exchange, new_exchange, 1)

access_block = '''            access_token = token_body.get("access_token")
            if not access_token:
                raise ValueError("missing access token")
'''
replacement_access = '''            access_token = token_body.get("access_token")
            if not access_token:
                raise ValueError("missing access token")
            token_bundle = build_shopify_token_bundle(token_body)
'''
if access_block not in commercial:
    raise SystemExit("Expected Shopify access-token block not found")
commercial = commercial.replace(access_block, replacement_access, 1)

start_marker = '            credential_ref = f"SHOPIFY_ORG_{str(org_id).replace(\'-\', \'\').upper()}"\n'
start = commercial.find(start_marker)
if start < 0:
    raise SystemExit("Shopify credential_ref block start not found")
end_marker = "            sink_response.raise_for_status()\n"
end = commercial.find(end_marker, start)
if end < 0:
    raise SystemExit("Shopify vault sink block end not found")
end += len(end_marker)
new_sink = '''            credential_ref = f"SHOPIFY_ORG_{str(org_id).replace('-', '').upper()}"
            store_oauth_secret(
                credential_ref,
                json.dumps(token_bundle, separators=(",", ":")),
                {
                    "provider": "shopify",
                    "shop": normalized_shop,
                    "organization_id": str(org_id),
                    "token_mode": SHOPIFY_EXPIRING_OFFLINE_BUNDLE,
                },
            )
'''
commercial = commercial[:start] + new_sink + commercial[end:]

config_anchor = '''        "oauth_managed": True,
        "granted_scopes": sorted(granted_scopes),
'''
config_replacement = '''        "oauth_managed": True,
        "oauth_token_mode": SHOPIFY_EXPIRING_OFFLINE_BUNDLE,
        "access_token_expires_at": token_bundle["access_token_expires_at"],
        "refresh_token_expires_at": token_bundle["refresh_token_expires_at"],
        "reauthorization_required": False,
        "granted_scopes": sorted(granted_scopes),
'''
if config_anchor not in commercial:
    raise SystemExit("Expected Shopify integration config anchor not found")
commercial = commercial.replace(config_anchor, config_replacement, 1)
commercial_path.write_text(commercial)

print("Shopify expiring offline token patch applied")
