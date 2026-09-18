from pathlib import Path

ROOT = Path("/app")
path = ROOT / "app/integrations/providers.py"

old = '''def _credential_value(reference: str | None) -> str | None:
    if not reference:
        return None
    return os.getenv(f"THRESHOLD_INTEGRATION_SECRET__{reference.upper()}")
'''

new = '''def _credential_value(reference: str | None) -> str | None:
    if not reference:
        return None

    env_value = os.getenv(f"THRESHOLD_INTEGRATION_SECRET__{reference.upper()}")
    if env_value:
        return env_value

    # OAuth-managed credentials are written to the server-side vault sink.
    # Read them back by opaque reference at runtime. The environment remains
    # the first-priority override for manually managed credentials.
    from app.core.config import get_settings

    settings = get_settings()
    vault_url = str(settings.OAUTH_SECRET_SINK_URL or "").strip()
    if not vault_url:
        return None

    try:
        validate_live_endpoint(vault_url)
    except ValueError:
        return None

    headers = {"Accept": "application/json"}
    auth_ref = str(settings.OAUTH_SECRET_SINK_AUTH_REF or "").strip()
    if auth_ref:
        auth_value = os.getenv(f"THRESHOLD_INTEGRATION_SECRET__{auth_ref.upper()}")
        if not auth_value:
            return None
        headers["Authorization"] = f"Bearer {auth_value}"

    try:
        with httpx.Client(timeout=5, follow_redirects=False) as client:
            response = client.get(
                vault_url,
                headers=headers,
                params={"reference": reference},
            )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None
    value = payload.get("secret")
    if not isinstance(value, str) or not value:
        return None
    return value
'''

text = path.read_text()
if old not in text:
    raise SystemExit("Expected _credential_value source block not found; refusing unsafe vault-read patch")
path.write_text(text.replace(old, new, 1))
print("OAuth vault runtime read patch applied")
