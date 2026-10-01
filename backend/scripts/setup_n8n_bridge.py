"""Create/reuse a signed ingress endpoint for an existing demo organization."""

import argparse
import json
import secrets

from sqlalchemy import select

from app.core.webhooks import webhook_secret_value
from app.db.session import SessionLocal
from app.models import Organization, WebhookEndpoint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-slug", default="acme-demo")
    parser.add_argument("--secret-ref", default="n8n_intake")
    args = parser.parse_args()
    secret = webhook_secret_value(args.secret_ref)
    if not secret or len(secret) < 32:
        parser.error(
            "Set THRESHOLD_WEBHOOK_SECRET__N8N_INTAKE to a random 32+ character secret first"
        )
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == args.org_slug))
        if org is None or org.plan != "demo":
            parser.error("This setup helper requires an existing demo workspace")
        row = db.scalar(
            select(WebhookEndpoint).where(
                WebhookEndpoint.organization_id == org.id,
                WebhookEndpoint.name == "n8n refund intake",
            )
        )
        if row is None:
            row = WebhookEndpoint(
                organization_id=org.id,
                name="n8n refund intake",
                endpoint_key=secrets.token_urlsafe(24),
                signing_secret_ref=args.secret_ref,
            )
            db.add(row)
            db.commit()
        if not row.is_active:
            parser.error("Existing endpoint is disabled; inspect it before re-enabling")
        print(
            json.dumps(
                {
                    "organization_id": str(org.id),
                    "webhook_path": "/api/v1/webhooks/" + row.endpoint_key,
                    "secret_reference": row.signing_secret_ref,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
