"""Populate the demo organization with realistic operational history.

Run after `python -m scripts.seed_demo_org`.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    Organization,
)
from app.workflows.engine import WorkflowEngine

DEMO_ORG = "acme-demo"


def run() -> None:
    db = SessionLocal()
    try:
        org = db.scalar(select(Organization).where(Organization.slug == DEMO_ORG))
        if org is None:
            raise RuntimeError("Seed the demo organization first")

        engine = WorkflowEngine(db)
        scenarios = [
            ("refund", "Please refund order #ORD-1002 for $65.00", "customer-a@example.com"),
            ("refund", "Please refund order #ORD-1001 for $89.99", "customer-b@example.com"),
            ("support", "My checkout is broken and I need support", "customer-c@example.com"),
            (
                "lead",
                "I am interested in the enterprise plan and want a quote",
                "prospect@example.com",
            ),
            ("invoice", "I have a question about my invoice", "finance@example.com"),
            ("customer", "What are your opening hours?", "visitor@example.com"),
        ]

        for idx, (_, text, sender) in enumerate(scenarios):
            engine.ingest_and_run(
                organization_id=org.id,
                source="api",
                idempotency_key=f"seed-history-{idx}-{uuid4().hex}",
                raw_payload={"text": text, "sender": sender},
            )

        # History leaves a high-risk refund pending. The dashboard has a separate
        # failure scenario for demonstrating recovery.

        db.commit()
        print(f"Seeded operational history for {org.slug}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
