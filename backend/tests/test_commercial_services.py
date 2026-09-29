from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models import Organization, OutboxMessage
from app.models.enums import OutboxStatus
from app.services.commercial import (
    assert_entitled,
    current_period_key,
    get_or_create_billing_account,
    get_plan,
    increment_usage,
    usage_quantity,
)
from app.services.outbox import enqueue_outbox, recover_stale_outbox


def make_org(db_session, slug, plan="trial"):
    org = Organization(name=slug.title(), slug=slug, plan=plan)
    db_session.add(org)
    db_session.flush()
    return org


def test_commercial_period_plan_billing_and_usage(db_session):
    assert current_period_key(datetime(2026, 9, 1, tzinfo=UTC)) == "2026-09"
    org = make_org(db_session, "billing-service")
    assert get_plan(org)["name"] == "Trial"
    org.plan = "does-not-exist"
    assert get_plan(org)["name"] == "Trial"
    org.plan = "trial"

    billing = get_or_create_billing_account(db_session, org)
    assert billing.organization_id == org.id
    assert get_or_create_billing_account(db_session, org).id == billing.id

    assert usage_quantity(db_session, org.id, "workflow_executions") == 0
    counter = increment_usage(db_session, org.id, "workflow_executions", 2)
    assert counter.quantity == 2
    assert usage_quantity(db_session, org.id, "workflow_executions") == 2
    assert increment_usage(db_session, org.id, "workflow_executions").quantity == 3


def test_assert_entitled_branches(db_session):
    demo = make_org(db_session, "entitlement-demo", plan="demo")
    assert_entitled(db_session, demo, "external_actions")

    inactive = make_org(db_session, "entitlement-inactive")
    billing = get_or_create_billing_account(db_session, inactive)
    billing.subscription_status = "past_due"
    with pytest.raises(HTTPException) as exc:
        assert_entitled(db_session, inactive, "external_actions")
    assert exc.value.status_code == 402

    expired = make_org(db_session, "entitlement-expired")
    billing = get_or_create_billing_account(db_session, expired)
    billing.subscription_status = "trialing"
    billing.trial_ends_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(HTTPException, match="Trial expired"):
        assert_entitled(db_session, expired, "external_actions")

    limited = make_org(db_session, "entitlement-limited")
    billing = get_or_create_billing_account(db_session, limited)
    billing.subscription_status = "active"
    increment_usage(db_session, limited.id, "team_members", 3)
    with pytest.raises(HTTPException, match="Plan limit"):
        assert_entitled(db_session, limited, "team_members")

    active = make_org(db_session, "entitlement-active", plan="enterprise")
    billing = get_or_create_billing_account(db_session, active)
    billing.subscription_status = "active"
    assert_entitled(db_session, active, "external_actions")


def test_outbox_enqueue_and_recover_stale(db_session):
    org = make_org(db_session, "outbox-service")
    aggregate_id = uuid4()
    row = enqueue_outbox(
        db_session,
        organization_id=org.id,
        topic="execute_action",
        aggregate_type="action",
        aggregate_id=aggregate_id,
        payload={"action_id": str(aggregate_id)},
    )
    assert row.status == OutboxStatus.PENDING
    assert row.attempt_count == 0

    row.status = OutboxStatus.PROCESSING
    row.locked_at = datetime.now(UTC) - timedelta(minutes=5)
    row.locked_by = "dead-worker"
    db_session.flush()
    assert recover_stale_outbox(db_session, lease_seconds=30) == 1
    assert row.status == OutboxStatus.PENDING
    assert row.locked_at is None
    assert row.locked_by is None
    assert row.last_error == "publisher_lease_expired"

    fresh = OutboxMessage(
        organization_id=org.id,
        topic="execute_action",
        aggregate_type="action",
        aggregate_id=uuid4(),
        payload={},
        status=OutboxStatus.PROCESSING,
        attempt_count=0,
        max_attempts=3,
        available_at=datetime.now(UTC),
        locked_at=datetime.now(UTC),
        locked_by="healthy-worker",
    )
    db_session.add(fresh)
    db_session.flush()
    assert recover_stale_outbox(db_session, lease_seconds=30) == 0
