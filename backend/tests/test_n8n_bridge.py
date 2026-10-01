"""PostgreSQL integration tests. Run using the project's disposable test database."""

import json
import time

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.webhooks import compute_signature
from app.models import ApprovalRequest, IncomingEvent, Organization, OutboxMessage, WebhookEndpoint
from app.services.outcomes import TOPIC, enqueue_final_outcome
from app.workflows.engine import WorkflowEngine
from scripts import seed_demo_org


@pytest.fixture
def bridge(db_session, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(seed_demo_org, "SessionLocal", lambda: db_session)
        patch.setattr(db_session, "close", lambda: None)
        seed_demo_org.run()
    org = db_session.scalar(select(Organization).where(Organization.slug == "acme-demo"))
    monkeypatch.setattr(
        get_settings(),
        "N8N_OUTCOME_TARGETS",
        {
            str(org.id): {
                "url": "https://n8n.example.com/webhook/test",
                "secret_ref": "bridge_test",
                "hubspot_portal_id": "123",
            }
        },
    )
    monkeypatch.setenv("THRESHOLD_WEBHOOK_SECRET__BRIDGE_TEST", "x" * 40)
    endpoint = WebhookEndpoint(
        organization_id=org.id,
        name="Bridge test",
        endpoint_key="bridge-test",
        signing_secret_ref="bridge_test",
    )
    db_session.add(endpoint)
    db_session.commit()
    return org


def payload(text="Refund order #ORD-1002 for $65.00"):
    return {
        "text": text,
        "external_id": "hubspot:123:ticket:456",
        "crm": {"provider": "hubspot", "portal_id": "123", "ticket_id": "456"},
    }


def post(client, body, *, headers=None, endpoint="bridge-test"):
    raw = json.dumps(body).encode()
    timestamp = str(int(time.time()))
    request_headers = {
        "Content-Type": "application/json",
        "X-Threshold-Event-Id": "hubspot:123:ticket:456",
        "X-Threshold-Timestamp": timestamp,
        "X-Threshold-Signature": compute_signature("x" * 40, timestamp, raw),
    }
    for key, value in (headers or {}).items():
        if value is None:
            request_headers.pop(key, None)
        else:
            request_headers[key] = value
    return client.post(
        f"/api/v1/webhooks/{endpoint}",
        content=raw,
        headers=request_headers,
    )


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"X-Threshold-Signature": "0" * 64}, 401),
        ({"X-Threshold-Event-Id": None}, 422),
        ({"X-Threshold-Event-Id": " "}, 422),
        ({"X-Threshold-Event-Id": "x" * 256}, 422),
    ],
)
def test_bad_headers_never_persist(client, db_session, bridge, headers, status):
    assert post(client, payload(), headers=headers).status_code == status
    assert not db_session.scalars(
        select(IncomingEvent).where(IncomingEvent.external_id == "hubspot:123:ticket:456")
    ).all()


def test_normal_webhook_without_crm_is_still_supported(client, db_session, bridge):
    response = post(client, {"text": "Hello support"})
    assert response.status_code == 202
    assert response.json()["duplicate"] is False
    event = db_session.scalar(select(IncomingEvent))
    assert event.organization_id == bridge.id
    assert event.signature_verified is True


def test_endpoint_cannot_accept_another_organizations_portal(client, db_session, bridge):
    other = Organization(name="Other workspace", slug="other-bridge", plan="demo")
    db_session.add(other)
    db_session.flush()
    db_session.add(
        WebhookEndpoint(
            organization_id=other.id,
            name="Other bridge",
            endpoint_key="other-bridge",
            signing_secret_ref="bridge_test",
        )
    )
    db_session.commit()
    # Even sharing a test secret must not bypass organization/portal configuration.
    assert post(client, payload(), endpoint="other-bridge").status_code == 422
    assert not db_session.scalars(
        select(IncomingEvent).where(IncomingEvent.organization_id == other.id)
    ).all()
    assert post(client, payload()).status_code == 202


def test_webhook_duplicate_and_conflict_preserve_original(client, db_session, bridge):
    assert post(client, payload()).status_code == 202
    assert post(client, payload()).json()["duplicate"] is True
    assert post(client, payload("Refund order #ORD-1002 for $10.00")).status_code == 409
    events = db_session.scalars(
        select(IncomingEvent).where(IncomingEvent.external_id == "hubspot:123:ticket:456")
    ).all()
    assert len(events) == 1
    assert events[0].raw_payload["text"].endswith("$65.00")


def test_success_enqueues_one_outcome_atomically(db_session, bridge):
    ex = WorkflowEngine(db_session).ingest_and_run(
        organization_id=bridge.id,
        source="api",
        idempotency_key="bridge-complete",
        raw_payload=payload(),
    )
    assert ex.status.value == "completed"
    enqueue_final_outcome(db_session, ex)
    db_session.flush()
    rows = db_session.scalars(select(OutboxMessage).where(OutboxMessage.topic == TOPIC)).all()
    assert len(rows) == 1
    assert rows[0].payload["verified"] is True
    assert rows[0].payload["crm"]["ticket_id"] == "456"


def test_wait_for_approval_then_rejection_emits_cancelled(db_session, bridge):
    ex = WorkflowEngine(db_session).ingest_and_run(
        organization_id=bridge.id,
        source="api",
        idempotency_key="bridge-reject",
        raw_payload=payload("Refund order #ORD-1001 for $89.99"),
    )
    assert ex.status.value == "awaiting_approval"
    assert not db_session.scalars(select(OutboxMessage).where(OutboxMessage.topic == TOPIC)).all()
    approval = db_session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.workflow_execution_id == ex.id)
    )
    from app.models import User
    from app.models.enums import ApprovalStatus

    approval.status = ApprovalStatus.REJECTED
    reviewer = db_session.scalar(select(User).where(User.email == "reviewer@acme-demo.example.com"))
    WorkflowEngine(db_session).resume_after_approval(approval, reviewer.id)
    row = db_session.scalar(select(OutboxMessage).where(OutboxMessage.topic == TOPIC))
    assert row.payload["status"] == "cancelled"


def test_portal_and_event_id_are_bound_before_persistence(client, bridge):
    bad = payload()
    bad["crm"]["portal_id"] = "999"
    assert post(client, bad).status_code == 422
    bad = payload()
    bad["external_id"] = "unbound-id"
    assert post(client, bad).status_code == 422
