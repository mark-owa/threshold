from __future__ import annotations

import argparse
import json
from uuid import UUID

import httpx
from sqlalchemy import select

from app.db.session import SessionLocal
from app.integrations.providers import _credential_value, validate_live_endpoint
from app.integrations.shopify import ShopifyAdminClient
from app.models import IntegrationConfig
from app.models.enums import IntegrationProvider


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only connectivity probes for private-beta Shopify/Stripe integrations."
    )
    parser.add_argument("--org-id", required=True)
    parser.add_argument(
        "--allow-live-stripe-key",
        action="store_true",
        help="Permit a sk_live_ key. Off by default for beta safety.",
    )
    args = parser.parse_args()
    org_id = UUID(args.org_id)
    db = SessionLocal()
    results: list[dict] = []
    failures = 0
    try:
        rows = db.scalars(
            select(IntegrationConfig).where(
                IntegrationConfig.organization_id == org_id,
                IntegrationConfig.is_enabled.is_(True),
            )
        ).all()
        shopify = next((x for x in rows if x.provider == IntegrationProvider.SHOPIFY), None)
        stripe = next((x for x in rows if x.provider == IntegrationProvider.STRIPE), None)

        if shopify is None:
            results.append(
                {"provider": "shopify", "ok": False, "detail": "enabled integration missing"}
            )
            failures += 1
        else:
            try:
                client = ShopifyAdminClient(shopify)
                data = client._graphql(
                    "query ThresholdBetaProbe { shop { id name myshopifyDomain } }", {}
                )
                shop = data.get("shop") or {}
                results.append({"provider": "shopify", "ok": bool(shop.get("id")), "shop": shop})
                if not shop.get("id"):
                    failures += 1
            except Exception as exc:
                results.append(
                    {
                        "provider": "shopify",
                        "ok": False,
                        "detail": f"{exc.__class__.__name__}: {exc}",
                    }
                )
                failures += 1

        if stripe is None:
            results.append(
                {"provider": "stripe", "ok": False, "detail": "enabled integration missing"}
            )
            failures += 1
        else:
            secret = _credential_value(stripe.credential_ref)
            if not secret:
                results.append(
                    {
                        "provider": "stripe",
                        "ok": False,
                        "detail": "credential reference does not resolve",
                    }
                )
                failures += 1
            elif secret.startswith("sk_live_") and not args.allow_live_stripe_key:
                results.append(
                    {
                        "provider": "stripe",
                        "ok": False,
                        "detail": "live Stripe key refused; private-beta probe expects test mode",
                    }
                )
                failures += 1
            else:
                try:
                    url = "https://api.stripe.com/v1/account"
                    validate_live_endpoint(url)
                    with httpx.Client(timeout=10, follow_redirects=False) as client:
                        response = client.get(url, headers={"Authorization": f"Bearer {secret}"})
                    body = (
                        response.json()
                        if response.headers.get("content-type", "").startswith("application/json")
                        else {}
                    )
                    ok = response.status_code == 200 and bool(body.get("id"))
                    results.append(
                        {
                            "provider": "stripe",
                            "ok": ok,
                            "account_id": body.get("id"),
                            "http_status": response.status_code,
                        }
                    )
                    if not ok:
                        failures += 1
                except Exception as exc:
                    results.append(
                        {
                            "provider": "stripe",
                            "ok": False,
                            "detail": f"{exc.__class__.__name__}: {exc}",
                        }
                    )
                    failures += 1
    finally:
        db.close()

    print(
        json.dumps({"organization_id": str(org_id), "results": results}, indent=2, sort_keys=True)
    )
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
