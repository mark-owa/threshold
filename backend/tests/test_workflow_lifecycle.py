"""Exercise the seeded reference workflow through persisted state and authenticated APIs."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models import (
    ActionExecution,
    ApprovalRequest,
    AuditLogEntry,
    IncomingEvent,
    IntegrationConfig,
    Organization,
    OrganizationMember,
    User,
    WorkflowExecution,
)
from app.models.enums import ActionStatus, MemberRole, WorkflowStatus
from app.workflows.engine import WorkflowEngine
from scripts import seed_demo_org


@pytest.fixture
def demo(db_session, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(seed_demo_org, "SessionLocal", lambda: db_session)
        patch.setattr(db_session, "close", lambda: None)
        seed_demo_org.run()
    org = db_session.scalar(select(Organization).where(Organization.slug == "acme-demo"))
    user = db_session.scalar(select(User).where(User.email == "owner@acme-demo.example.com"))
    return org, {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_auto_refund_persists_and_deduplicates(client, db_session, demo):
    org, headers = demo
    url = "/api/v1/demo/orgs/acme-demo/events"
    body = {
        "idempotency_key": "refund-1",
        "payload": {
            "text": "Refund order #ORD-1002 for $65.00",
            "external_id": "external-1",
        },
    }
    response = client.post(url, json=body, headers={**headers, "X-Request-ID": "trace-1"})
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "completed"
    assert (
        client.post(url, json=body, headers=headers).json()["execution_id"]
        == result["execution_id"]
    )
    body["idempotency_key"] = "refund-2"
    body["payload"]["text"] = "Refund order #ORD-1002 for USD 65"
    assert client.post(url, json=body, headers=headers).json()["status"] == "completed"
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(ActionExecution)) == 1
    event = db_session.scalar(
        select(IncomingEvent).where(IncomingEvent.idempotency_key == "refund-1")
    )
    assert event.external_id == "external-1"
    assert event.request_id == "trace-1"
    assert event.signature_verified is False
    detail = client.get(
        f"/api/v1/ops/executions/{result['execution_id']}?org_id={org.id}", headers=headers
    ).json()
    assert [s["step_key"] for s in detail["steps"]] == [
        "classify",
        "extract",
        "policy",
        "rules",
        "risk",
        "approval",
        "execute",
        "verify",
    ]
    assert detail["context"]["verified"] is True
    assert db_session.scalar(select(func.count()).select_from(AuditLogEntry)) > 0
    feed = client.get(f"/api/v1/ops/audit?org_id={org.id}", headers=headers).json()
    assert feed[0]["event_type"] == "execution_verified"
    assert [row["created_at"] for row in feed] == sorted(
        [row["created_at"] for row in feed], reverse=True
    )


@pytest.mark.parametrize("amount", ["", " for $0", " for $1,000", " for $65.001"])
def test_incomplete_or_ineligible_refunds_never_auto_execute(db_session, demo, amount):
    org, _ = demo
    execution = WorkflowEngine(db_session).ingest_and_run(
        organization_id=org.id,
        source="api",
        idempotency_key="invalid-amount",
        raw_payload={"text": "Refund order #ORD-1002" + amount},
    )
    assert execution.status == WorkflowStatus.AWAITING_APPROVAL
    assert db_session.scalar(select(func.count()).select_from(ActionExecution)) == 0


@pytest.mark.parametrize(
    "decision,expected",
    [
        ("approved", "completed"),
        ("modified", "completed"),
        ("rejected", "cancelled"),
    ],
)
def test_approval_decision_lifecycle(client, db_session, demo, decision, expected):
    org, headers = demo
    execution = WorkflowEngine(db_session).ingest_and_run(
        organization_id=org.id,
        source="api",
        idempotency_key="review-refund",
        raw_payload={"text": "Refund order #ORD-1001 for $89.99"},
    )
    approval = db_session.scalar(select(ApprovalRequest))
    assert execution.status == WorkflowStatus.AWAITING_APPROVAL
    assert approval.step_execution_id is not None
    url = f"/api/v1/approvals/{approval.id}/decision?org_id={org.id}"
    payload = {"decision": decision}
    if decision == "modified":
        payload["modified_parameters"] = {"order_number": "ORD-1001", "amount_usd": 50}
    res = client.post(url, json=payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == expected
    assert client.post(url, json=payload, headers=headers).status_code == 409
    db_session.expire_all()
    assert execution.completed_at is not None
    action = db_session.scalar(select(ActionExecution))
    if decision == "rejected":
        assert action is None
    else:
        assert action.status == ActionStatus.SUCCEEDED
        assert action.approval_request_id == approval.id
        assert approval.final_execution_result["action_id"] == str(action.id)
        assert execution.current_step_key == "verify"
        if decision == "modified":
            assert action.request_payload["amount_usd"] == 50
    metrics = client.get(f"/api/v1/ops/metrics?org_id={org.id}", headers=headers).json()
    assert metrics["automation_rate_percent"] == 0


def test_modified_parameters_and_authorization_boundaries(client, db_session, demo):
    org, headers = demo
    WorkflowEngine(db_session).ingest_and_run(
        organization_id=org.id,
        source="api",
        idempotency_key="review",
        raw_payload={"text": "Refund order #ORD-1001 for $89.99"},
    )
    approval = db_session.scalar(select(ApprovalRequest))
    url = f"/api/v1/approvals/{approval.id}/decision?org_id={org.id}"
    bad = {"decision": "approved", "modified_parameters": {"amount_usd": 1}}
    assert client.post(url, json=bad, headers=headers).status_code == 422
    assert (
        client.post(
            url.replace("/approvals/", "/demo/approvals/"), json=bad, headers=headers
        ).status_code
        == 422
    )
    outsider = User(
        email="outsider@example.com", full_name="Test outsider", hashed_password="unused"
    )
    db_session.add(outsider)
    db_session.flush()
    other_headers = {"Authorization": f"Bearer {create_access_token(str(outsider.id))}"}
    assert (
        client.get(f"/api/v1/ops/executions?org_id={org.id}", headers=other_headers).status_code
        == 403
    )
    db_session.add(
        OrganizationMember(organization_id=org.id, user_id=outsider.id, role=MemberRole.VIEWER)
    )
    db_session.commit()
    assert client.post(url, json={"decision": "approved"}, headers=other_headers).status_code == 403
    result = client.post(
        url,
        json={
            "decision": "modified",
            "modified_parameters": {
                "order_number": "ORD-1001",
                "amount_usd": -1,
            },
        },
        headers=headers,
    )
    assert result.json()["status"] == "failed"
    assert db_session.scalar(select(func.count()).select_from(ActionExecution)) == 0


def test_failure_scheduling_retry_and_dead_letter(client, db_session, demo, monkeypatch):
    from app.workers import tasks

    org, headers = demo
    # A previous automatic refund must not swallow the independent failure scenario.
    for scenario in ["low_risk_refund", "failed_refund"]:
        res = client.post(
            f"/api/v1/demo/run?org_id={org.id}", json={"scenario": scenario}, headers=headers
        )
        assert res.status_code == 200
    execution = db_session.get(WorkflowExecution, UUID(res.json()["execution_id"]))
    assert execution.status == WorkflowStatus.FAILED
    assert execution.context["extracted"]["simulate_failure_once"] is True
    action = db_session.scalar(
        select(ActionExecution).where(ActionExecution.workflow_execution_id == execution.id)
    )
    action_id, key = action.id, action.idempotency_key
    assert action.status == ActionStatus.RETRYING
    action.next_retry_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.commit()
    WorkflowEngine(db_session).retry_failed_execution(execution)
    assert action.attempt_count == 1
    action.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    with monkeypatch.context() as patch:
        patch.setattr(tasks, "SessionLocal", lambda: db_session)
        patch.setattr(db_session, "close", lambda: None)
        assert tasks.retry_due_actions.run() == 1
    db_session.expire_all()
    assert execution.status == WorkflowStatus.COMPLETED
    assert execution.context["verified"] is True
    assert action.id == action_id and action.idempotency_key == key
    assert action.attempt_count == 2 and action.next_retry_at is None and action.error is None
    res = client.post(
        f"/api/v1/demo/run?org_id={org.id}", json={"scenario": "failed_refund"}, headers=headers
    )
    failed = db_session.get(WorkflowExecution, UUID(res.json()["execution_id"]))
    exhausted = db_session.scalar(
        select(ActionExecution).where(ActionExecution.workflow_execution_id == failed.id)
    )
    exhausted.attempt_count = exhausted.max_attempts
    db_session.commit()
    WorkflowEngine(db_session).retry_failed_execution(failed, force=True)
    assert exhausted.status == ActionStatus.DEAD_LETTER and exhausted.next_retry_at is None
    assert failed.status == WorkflowStatus.FAILED


def test_circuit_and_disabled_integration(db_session, demo):
    org, _ = demo
    runner = WorkflowEngine(db_session)
    execution = runner.ingest_and_run(
        organization_id=org.id,
        source="api",
        idempotency_key="timeout",
        raw_payload={"text": "Refund order #ORD-1002 for $65", "simulate_failure_once": True},
    )
    integration = db_session.scalar(select(IntegrationConfig))
    integration.circuit_open_until = datetime.now(UTC) + timedelta(minutes=1)
    db_session.commit()
    runner.retry_failed_execution(execution, force=True)
    assert execution.status == WorkflowStatus.FAILED
    integration.circuit_open_until = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    runner.retry_failed_execution(execution, force=True)
    assert integration.consecutive_failures == 0 and integration.circuit_open_until is None
    integration.is_enabled = False
    db_session.commit()
    execution = runner.ingest_and_run(
        organization_id=org.id,
        source="api",
        idempotency_key="disabled",
        raw_payload={"text": "Refund order #ORD-1002 for $20"},
    )
    assert execution.status == WorkflowStatus.FAILED
    assert execution.error == "Integration is disabled"
    assert db_session.scalar(select(func.count()).select_from(IntegrationConfig)) == 1
