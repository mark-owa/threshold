from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BillingAccount, Organization, UsageCounter

PLAN_CATALOG = {
    "trial": {
        "name": "Trial",
        "monthly_price_usd": 0,
        "limits": {"workflow_executions": 500, "external_actions": 100, "team_members": 3},
        "features": ["refund_workflow", "approvals", "shopify", "stripe", "audit"],
    },
    "starter": {
        "name": "Starter",
        "monthly_price_usd": 49,
        "limits": {"workflow_executions": 5000, "external_actions": 1000, "team_members": 5},
        "features": ["refund_workflow", "approvals", "shopify", "stripe", "audit", "recovery"],
    },
    "business": {
        "name": "Business",
        "monthly_price_usd": 199,
        "limits": {"workflow_executions": 25000, "external_actions": 10000, "team_members": 25},
        "features": [
            "refund_workflow",
            "approvals",
            "shopify",
            "stripe",
            "audit",
            "recovery",
            "priority_support",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly_price_usd": None,
        "limits": {"workflow_executions": None, "external_actions": None, "team_members": None},
        "features": [
            "refund_workflow",
            "approvals",
            "shopify",
            "stripe",
            "audit",
            "recovery",
            "priority_support",
            "custom_retention",
            "sso_ready",
        ],
    },
    "demo": {
        "name": "Demo",
        "monthly_price_usd": 0,
        "limits": {"workflow_executions": None, "external_actions": None, "team_members": None},
        "features": ["sandbox"],
    },
}


def current_period_key(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return now.strftime("%Y-%m")


def get_plan(organization: Organization) -> dict:
    return PLAN_CATALOG.get(organization.plan, PLAN_CATALOG["trial"])


def get_or_create_billing_account(db: Session, organization: Organization) -> BillingAccount:
    row = db.scalar(select(BillingAccount).where(BillingAccount.organization_id == organization.id))
    if row is None:
        row = BillingAccount(
            organization_id=organization.id,
            subscription_status="trialing",
            trial_ends_at=datetime.now(UTC) + timedelta(days=14),
        )
        db.add(row)
        db.flush()
    return row


def usage_quantity(db: Session, org_id: UUID, metric: str, period_key: str | None = None) -> int:
    period_key = period_key or current_period_key()
    row = db.scalar(
        select(UsageCounter).where(
            UsageCounter.organization_id == org_id,
            UsageCounter.period_key == period_key,
            UsageCounter.metric == metric,
        )
    )
    return row.quantity if row else 0


def increment_usage(db: Session, org_id: UUID, metric: str, amount: int = 1) -> UsageCounter:
    period_key = current_period_key()
    row = db.scalar(
        select(UsageCounter).where(
            UsageCounter.organization_id == org_id,
            UsageCounter.period_key == period_key,
            UsageCounter.metric == metric,
        )
    )
    if row is None:
        row = UsageCounter(
            organization_id=org_id,
            period_key=period_key,
            metric=metric,
            quantity=0,
        )
        db.add(row)
        db.flush()
    row.quantity += amount
    return row


def assert_entitled(db: Session, organization: Organization, metric: str) -> None:
    if organization.plan == "demo":
        return
    billing = get_or_create_billing_account(db, organization)
    now = datetime.now(UTC)
    if billing.subscription_status in {"past_due", "unpaid", "canceled", "incomplete_expired"}:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Billing is not active for this workspace",
        )
    if (
        billing.trial_ends_at
        and billing.subscription_status == "trialing"
        and billing.trial_ends_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Trial expired. Choose a plan to continue live execution.",
        )
    limit = get_plan(organization)["limits"].get(metric)
    if limit is not None and usage_quantity(db, organization.id, metric) >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Plan limit reached for {metric}",
        )
