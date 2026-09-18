from pathlib import Path

ROOT = Path("/app")

REPLACEMENTS = [('app/integrations/shopify.py', 'import hmac\n', 'import hmac\nimport re\n'),
 ('app/integrations/shopify.py',
  '\n\ndef verify_shopify_hmac(secret: str, body: bytes, supplied_signature: str) -> bool:\n',
  '\n'
  '\n'
  'SHOPIFY_SHOP_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]*\\.myshopify\\.com$")\n'
  '\n'
  '\n'
  'def normalize_shopify_domain(value: str) -> str:\n'
  '    shop = str(value or "").strip().lower()\n'
  '    shop = shop.removeprefix("https://").removeprefix("http://").rstrip("/")\n'
  '    if not SHOPIFY_SHOP_DOMAIN_RE.fullmatch(shop):\n'
  '        raise ValueError("Shopify shop domain must match <shop>.myshopify.com")\n'
  '    return shop\n'
  '\n'
  '\n'
  'def verify_shopify_callback_hmac(\n'
  '    secret: str,\n'
  '    query_items: list[tuple[str, str]] | tuple[tuple[str, str], ...],\n'
  ') -> bool:\n'
  '    supplied = None\n'
  '    canonical: list[tuple[str, str]] = []\n'
  '    for key, value in query_items:\n'
  '        if key == "hmac":\n'
  '            supplied = value\n'
  '            continue\n'
  '        canonical.append((key, value))\n'
  '    if not secret or not supplied:\n'
  '        return False\n'
  '    canonical.sort(key=lambda item: (item[0], item[1]))\n'
  '    message = "&".join(f"{key}={value}" for key, value in canonical)\n'
  '    expected = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()\n'
  '    return hmac.compare_digest(expected, supplied.strip().lower())\n'
  '\n'
  '\n'
  'def verify_shopify_hmac(secret: str, body: bytes, supplied_signature: str) -> bool:\n'),
 ('app/integrations/shopify.py',
  '        self.shop_domain = str(integration.config.get("shop_domain", "")).strip().lower()\n'
  '        if not self.shop_domain.endswith(".myshopify.com"):\n'
  '            raise ValueError("Shopify shop_domain must end with .myshopify.com")\n',
  '        self.shop_domain = normalize_shopify_domain(str(integration.config.get("shop_domain", "")))\n'),
 ('app/api/commercial.py',
  'from app.integrations.providers import validate_live_endpoint\n',
  'from app.integrations.providers import validate_live_endpoint\n'
  'from app.integrations.shopify import normalize_shopify_domain, verify_shopify_callback_hmac\n'),
 ('app/api/commercial.py',
  '    row = db.scalar(\n'
  '        select(OAuthStateNonce).where(\n'
  '            OAuthStateNonce.nonce_hash == _nonce_hash(nonce),\n'
  '            OAuthStateNonce.organization_id == org_id,\n'
  '            OAuthStateNonce.provider == provider,\n'
  '        )\n'
  '    )\n',
  '    row = db.scalar(\n'
  '        select(OAuthStateNonce)\n'
  '        .where(\n'
  '            OAuthStateNonce.nonce_hash == _nonce_hash(nonce),\n'
  '            OAuthStateNonce.organization_id == org_id,\n'
  '            OAuthStateNonce.provider == provider,\n'
  '        )\n'
  '        .with_for_update()\n'
  '    )\n'),
 ('app/api/commercial.py',
  '    shop = shop.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")\n'
  '    if not shop.endswith(".myshopify.com"):\n'
  '        raise HTTPException(status_code=422, detail="Shop must be a .myshopify.com domain")\n',
  '    try:\n'
  '        shop = normalize_shopify_domain(shop)\n'
  '    except ValueError as exc:\n'
  '        raise HTTPException(status_code=422, detail=str(exc)) from exc\n'),
 ('app/api/commercial.py',
  '@router.get("/shopify/callback")\n'
  'def shopify_callback(code: str, state: str, shop: str, db: Session = Depends(get_db)):\n'
  '    payload = _verify_state(state)\n'
  '    normalized_shop = shop.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")\n'
  '    if payload.get("shop") != normalized_shop:\n'
  '        raise HTTPException(status_code=400, detail="Shop does not match OAuth state")\n',
  '@router.get("/shopify/callback")\n'
  'def shopify_callback(request: Request, code: str, state: str, shop: str, db: Session = Depends(get_db)):\n'
  '    if not settings.SHOPIFY_CLIENT_SECRET:\n'
  '        raise HTTPException(status_code=503, detail="Shopify OAuth app credentials are not configured")\n'
  '    if not verify_shopify_callback_hmac(\n'
  '        settings.SHOPIFY_CLIENT_SECRET,\n'
  '        list(request.query_params.multi_items()),\n'
  '    ):\n'
  '        raise HTTPException(status_code=400, detail="Invalid Shopify OAuth callback signature")\n'
  '    try:\n'
  '        normalized_shop = normalize_shopify_domain(shop)\n'
  '    except ValueError as exc:\n'
  '        raise HTTPException(status_code=400, detail=str(exc)) from exc\n'
  '    payload = _verify_state(state)\n'
  '    if payload.get("shop") != normalized_shop:\n'
  '        raise HTTPException(status_code=400, detail="Shop does not match OAuth state")\n'),
 ('app/api/commercial.py',
  '            token_body = token_response.json()\n'
  '            access_token = token_body.get("access_token")\n'
  '            if not access_token:\n'
  '                raise ValueError("missing access token")\n'
  '            credential_ref = f"SHOPIFY_ORG_{str(org_id).replace(\'-\', \'\').upper()}"\n',
  '            token_body = token_response.json()\n'
  '            access_token = token_body.get("access_token")\n'
  '            if not access_token:\n'
  '                raise ValueError("missing access token")\n'
  '            requested_scopes = {scope.strip() for scope in settings.SHOPIFY_SCOPES.split(",") if scope.strip()}\n'
  '            granted_scopes = {scope.strip() for scope in str(token_body.get("scope") or "").split(",") if scope.strip()}\n'
  '            missing_scopes = {\n'
  '                scope\n'
  '                for scope in requested_scopes\n'
  '                if scope not in granted_scopes\n'
  '                and not (\n'
  '                    scope.startswith("read_")\n'
  '                    and f"write_{scope.removeprefix(\'read_\')}" in granted_scopes\n'
  '                )\n'
  '            }\n'
  '            if missing_scopes:\n'
  '                raise ValueError("Shopify did not grant all required access scopes")\n'
  '            credential_ref = f"SHOPIFY_ORG_{str(org_id).replace(\'-\', \'\').upper()}"\n'),
 ('app/api/commercial.py',
  '    integration.config = {**(integration.config or {}), "shop_domain": normalized_shop, "api_version": settings.SHOPIFY_API_VERSION, "oauth_managed": True, '
  '"refund_enabled": False}\n',
  '    integration.config = {\n'
  '        **(integration.config or {}),\n'
  '        "shop_domain": normalized_shop,\n'
  '        "api_version": settings.SHOPIFY_API_VERSION,\n'
  '        "oauth_managed": True,\n'
  '        "granted_scopes": sorted(granted_scopes),\n'
  '        "refund_enabled": False,\n'
  '    }\n'),
 ('app/api/workspace.py',
  'from app.integrations.providers import validate_live_endpoint\n',
  'from app.integrations.providers import validate_live_endpoint\nfrom app.integrations.shopify import normalize_shopify_domain\n'),
 ('app/api/workspace.py',
  '    shop_domain = request.shop_domain.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")\n'
  '    if not shop_domain.endswith(".myshopify.com"):\n'
  '        raise HTTPException(status_code=422, detail="Shopify domain must end with .myshopify.com")\n',
  '    try:\n'
  '        shop_domain = normalize_shopify_domain(request.shop_domain)\n'
  '    except ValueError as exc:\n'
  '        raise HTTPException(status_code=422, detail=str(exc)) from exc\n'),
 ('app/api/webhooks.py',
  '    x_shopify_hmac_sha256: str = Header(alias="X-Shopify-Hmac-SHA256"),\n'
  '    x_shopify_webhook_id: str = Header(alias="X-Shopify-Webhook-Id"),\n'
  '    x_shopify_topic: str = Header(alias="X-Shopify-Topic"),\n',
  '    x_shopify_hmac_sha256: str = Header(alias="X-Shopify-Hmac-SHA256"),\n'
  '    x_shopify_webhook_id: str = Header(alias="X-Shopify-Webhook-Id"),\n'
  '    x_shopify_topic: str = Header(alias="X-Shopify-Topic"),\n'
  '    x_shopify_shop_domain: str = Header(alias="X-Shopify-Shop-Domain"),\n'),
 ('app/api/webhooks.py',
  '    integration = db.scalar(\n'
  '        select(IntegrationConfig).where(\n'
  '            IntegrationConfig.organization_id == org_id,\n'
  '            IntegrationConfig.provider == IntegrationProvider.SHOPIFY,\n'
  '            IntegrationConfig.is_enabled.is_(True),\n'
  '        )\n'
  '    )\n',
  '    integration = db.scalar(\n'
  '        select(IntegrationConfig)\n'
  '        .where(\n'
  '            IntegrationConfig.organization_id == org_id,\n'
  '            IntegrationConfig.provider == IntegrationProvider.SHOPIFY,\n'
  '            IntegrationConfig.is_enabled.is_(True),\n'
  '        )\n'
  '        .with_for_update()\n'
  '    )\n'),
 ('app/api/webhooks.py',
  '    body = await request.body()\n'
  '    secret_ref = str((integration.config or {}).get("webhook_secret_ref") or "")\n'
  '    secret = webhook_secret_value(secret_ref) if secret_ref else None\n'
  '    if not secret:\n'
  '        raise HTTPException(status_code=503, detail="Shopify webhook signing secret is not configured")\n'
  '    from app.integrations.shopify import verify_shopify_hmac\n'
  '    if not verify_shopify_hmac(secret, body, x_shopify_hmac_sha256):\n'
  '        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature")\n',
  '    body = await request.body()\n'
  '    config = integration.config or {}\n'
  '    if bool(config.get("oauth_managed")):\n'
  '        secret = get_settings().SHOPIFY_CLIENT_SECRET or None\n'
  '    else:\n'
  '        secret_ref = str(config.get("webhook_secret_ref") or "")\n'
  '        secret = webhook_secret_value(secret_ref) if secret_ref else None\n'
  '    if not secret:\n'
  '        raise HTTPException(status_code=503, detail="Shopify webhook signing secret is not configured")\n'
  '    from app.integrations.shopify import normalize_shopify_domain, verify_shopify_hmac\n'
  '    if not verify_shopify_hmac(secret, body, x_shopify_hmac_sha256):\n'
  '        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature")\n'
  '    try:\n'
  '        delivery_shop = normalize_shopify_domain(x_shopify_shop_domain)\n'
  '        configured_shop = normalize_shopify_domain(str(config.get("shop_domain") or ""))\n'
  '    except ValueError as exc:\n'
  '        raise HTTPException(status_code=400, detail="Invalid Shopify shop domain") from exc\n'
  '    if delivery_shop != configured_shop:\n'
  '        raise HTTPException(status_code=401, detail="Shopify webhook shop does not match integration")\n'),
 ('app/services/beta_readiness.py',
  '        shopify_secret = _credential_value(shopify.credential_ref)\n'
  '        webhook_ref = str((shopify.config or {}).get("webhook_secret_ref") or "")\n'
  '        webhook_secret = webhook_secret_value(webhook_ref) if webhook_ref else None\n',
  '        shopify_secret = _credential_value(shopify.credential_ref)\n'
  '        shopify_config = shopify.config or {}\n'
  '        if bool(shopify_config.get("oauth_managed")):\n'
  '            webhook_secret = settings.SHOPIFY_CLIENT_SECRET or None\n'
  '        else:\n'
  '            webhook_ref = str(shopify_config.get("webhook_secret_ref") or "")\n'
  '            webhook_secret = webhook_secret_value(webhook_ref) if webhook_ref else None\n')]

for rel, old, new in REPLACEMENTS:
    path = ROOT / rel
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"Expected source block not found in {rel}; refusing unsafe Shopify patch")
    path.write_text(text.replace(old, new, 1))

print("Shopify staging hardening patch applied")
