import asyncio
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.api.webhooks import receive_webhook
from app.core.config import get_settings
from app.core.webhooks import canonical_payload, compute_signature, verify_signature
from app.models.enums import WorkflowStatus
from app.services.outcomes import (
    DeliveryError,
    deliver_outcome,
    enqueue_final_outcome,
    outcome_payload,
)
from app.workflows.primitives import normalize_payload


@pytest.fixture
def configured(monkeypatch):
    org = uuid4()
    target = {
        "url": "https://n8n.example.com/webhook/threshold",
        "secret_ref": "outcome_test",
        "hubspot_portal_id": "123",
    }
    settings = get_settings()
    monkeypatch.setattr(settings, "N8N_OUTCOME_TARGETS", {str(org): target})
    monkeypatch.setattr(settings, "INTEGRATION_ALLOWED_HOSTS", "n8n.example.com")
    monkeypatch.setenv("THRESHOLD_WEBHOOK_SECRET__OUTCOME_TEST", "x" * 40)
    return org, target


def execution(org, status=WorkflowStatus.COMPLETED):
    return SimpleNamespace(
        id=uuid4(),
        organization_id=org,
        incoming_event_id=uuid4(),
        status=status,
        context={
            "category": "refund_request",
            "verified": True,
            "event": {
                "text": "private text",
                "sender": "private@example.com",
                "crm": {"provider": "hubspot", "portal_id": "123", "ticket_id": "456"},
            },
        },
    )


def test_correlation_survives_normalization(configured):
    org, _ = configured
    payload = execution(org).context["event"]
    assert normalize_payload(payload)["crm"] == payload["crm"]


@pytest.mark.parametrize(
    "crm",
    [
        None,
        [],
        {},
        {"provider": "ghl"},
        {"provider": "hubspot", "portal_id": "123", "ticket_id": 456},
        {"provider": "hubspot", "portal_id": "123", "ticket_id": "../456"},
        {
            "provider": "hubspot",
            "portal_id": "123",
            "ticket_id": "456",
            "callback_url": "https://evil.example",
        },
    ],
)
def test_invalid_correlation_is_rejected(crm):
    with pytest.raises(ValueError):
        normalize_payload({"text": "refund", "crm": crm})


def test_final_payload_is_stable_and_minimal(configured):
    org, target = configured
    ex = execution(org)
    first = outcome_payload(ex, target)
    assert first == outcome_payload(ex, target)
    assert "private" not in json.dumps(first)
    assert first["crm"]["ticket_id"] == "456"
    assert outcome_payload(execution(uuid4()), target)["delivery_id"] != first["delivery_id"]


@pytest.mark.parametrize(
    "status",
    [
        WorkflowStatus.RUNNING,
        WorkflowStatus.AWAITING_APPROVAL,
        WorkflowStatus.WAITING_EXTERNAL,
        WorkflowStatus.FAILED,
    ],
)
def test_nonfinal_states_do_not_emit(configured, status):
    org, target = configured
    assert outcome_payload(execution(org, status), target) is None


def test_completion_requires_verification_and_correct_portal(configured):
    org, target = configured
    ex = execution(org)
    ex.context["verified"] = False
    assert outcome_payload(ex, target) is None
    ex.status = WorkflowStatus.CANCELLED
    assert outcome_payload(ex, target)["status"] == "cancelled"
    assert outcome_payload(ex, {"hubspot_portal_id": "999"}) is None


def test_enqueue_uses_conflict_safe_insert_and_no_commit(configured):
    org, _ = configured
    statements = []
    enqueue_final_outcome(SimpleNamespace(execute=statements.append), execution(org))
    sql = str(statements[0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (id) DO NOTHING" in sql
    assert statements[0].compile().params["max_attempts"] == 8


def send(configured, handler):
    org, target = configured
    payload = outcome_payload(execution(org), target)
    row = SimpleNamespace(id=payload["delivery_id"], organization_id=org, payload=payload)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        deliver_outcome(row, client=client)


def test_delivery_signs_exact_bytes_and_requires_matching_ack(configured):
    def handler(request):
        assert verify_signature(
            secret="x" * 40,
            timestamp=request.headers["X-Threshold-Timestamp"],
            body=request.content,
            signature=request.headers["X-Threshold-Signature"],
        )
        assert request.headers["X-Threshold-Token"] == "x" * 40
        return httpx.Response(
            200, json={"ok": True, "delivery_id": json.loads(request.content)["delivery_id"]}
        )

    send(configured, handler)


@pytest.mark.parametrize(
    "status,retryable",
    [
        (400, False),
        (401, False),
        (403, False),
        (404, False),
        (409, False),
        (302, False),
        (429, True),
        (500, True),
        (502, True),
        (503, True),
        (504, True),
    ],
)
def test_delivery_classifies_http_failure(configured, status, retryable):
    with pytest.raises(DeliveryError) as result:
        send(configured, lambda request: httpx.Response(status, headers={"Retry-After": "60"}))
    assert result.value.retryable is retryable
    assert result.value.retry_after == 60


@pytest.mark.parametrize("ack", [{}, {"ok": True}, {"ok": True, "delivery_id": "wrong"}, []])
def test_http_200_without_matching_ack_is_not_success(configured, ack):
    with pytest.raises(DeliveryError, match="outcome_invalid_ack"):
        send(configured, lambda request: httpx.Response(200, json=ack))


def test_transport_timeout_is_retriable(configured):
    def handler(request):
        raise httpx.ReadTimeout("sensitive provider detail", request=request)

    with pytest.raises(DeliveryError, match="outcome_transport_error") as result:
        send(configured, handler)
    assert result.value.retryable is True
    assert "sensitive" not in str(result.value)


def test_disabled_destination_never_calls_network(configured):
    configured[1]["url"] = "https://untrusted.example/path"
    with pytest.raises(DeliveryError, match="outcome_configuration_invalid"):
        send(configured, lambda _: pytest.fail("network must not be called"))


def ingress(existing_payload, new_payload, monkeypatch):
    endpoint = SimpleNamespace(
        id=uuid4(),
        signing_secret_ref="ingress_test",
        allowed_clock_skew_seconds=300,
        organization_id=uuid4(),
    )
    existing = SimpleNamespace(
        raw_payload=existing_payload,
        id=uuid4(),
        processing_status=SimpleNamespace(value="received"),
    )
    values = iter([endpoint, existing])
    db = SimpleNamespace(scalar=lambda _: next(values), commit=lambda: None)
    raw = json.dumps(new_payload).encode()

    async def body():
        return raw

    request = SimpleNamespace(body=body)
    monkeypatch.setenv("THRESHOLD_WEBHOOK_SECRET__INGRESS_TEST", "i" * 40)
    timestamp = str(int(time.time()))
    return asyncio.run(
        receive_webhook(
            "endpoint",
            request,
            "stable-id",
            timestamp,
            compute_signature("i" * 40, timestamp, raw),
            db,
        )
    )


def test_same_event_same_payload_returns_duplicate(monkeypatch):
    result = ingress({"text": "hello", "count": 1}, {"count": 1, "text": "hello"}, monkeypatch)
    assert result.status_code == 202
    assert json.loads(result.body)["duplicate"] is True


def test_same_event_changed_payload_returns_conflict(monkeypatch):
    with pytest.raises(HTTPException) as result:
        ingress({"text": "refund $10"}, {"text": "refund $100"}, monkeypatch)
    assert result.value.status_code == 409
    assert result.value.detail == "EVENT_ID_CONFLICT"


def test_json_boolean_is_not_numeric_duplicate():
    assert canonical_payload({"x": True}) != canonical_payload({"x": 1})


@pytest.mark.parametrize(
    "failure,attempts,expected",
    [
        (None, 0, "sent"),
        (DeliveryError("outcome_http_503", retry_after=60), 0, "failed"),
        (DeliveryError("outcome_http_401", retryable=False), 0, "dead_letter"),
        (DeliveryError("outcome_http_503"), 7, "dead_letter"),
    ],
)
def test_dispatcher_records_delivery_result_without_refund_call(
    monkeypatch, failure, attempts, expected
):
    from datetime import UTC, datetime, timedelta

    from app.models.enums import OutboxStatus
    from app.workers import tasks

    row = SimpleNamespace(
        id=uuid4(),
        payload={},
        topic="deliver_n8n_outcome",
        status=OutboxStatus.PENDING,
        attempt_count=attempts,
        max_attempts=8,
        available_at=datetime.now(UTC) - timedelta(seconds=1),
        locked_by=None,
        locked_at=None,
        last_error=None,
        sent_at=None,
    )
    db = SimpleNamespace(
        scalars=lambda _: SimpleNamespace(all=lambda: [row.id]),
        scalar=lambda _: row,
        commit=lambda: None,
        rollback=lambda: None,
        close=lambda: None,
    )
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(tasks, "recover_stale_outbox", lambda *a, **k: 0)

    def deliver(_):
        if failure:
            raise failure

    monkeypatch.setattr(tasks, "deliver_outcome", deliver)
    monkeypatch.setattr(
        tasks.celery_app, "send_task", lambda *a, **k: pytest.fail("Must not queue a refund")
    )
    before = datetime.now(UTC)
    count = tasks.dispatch_outbox.run(limit=1)
    assert row.status.value == expected
    assert row.attempt_count == attempts + 1
    assert count == (1 if expected == "sent" else 0)
    if expected == "failed":
        assert row.available_at >= before + timedelta(seconds=60)


@pytest.mark.parametrize("fails", [False, True])
def test_dispatcher_cannot_finish_another_workers_lease(monkeypatch, fails):
    from datetime import UTC, datetime, timedelta

    from app.models.enums import OutboxStatus
    from app.workers import tasks

    row = SimpleNamespace(
        id=uuid4(),
        payload={},
        topic="deliver_n8n_outcome",
        status=OutboxStatus.PENDING,
        attempt_count=0,
        max_attempts=8,
        available_at=datetime.now(UTC) - timedelta(seconds=1),
        locked_by=None,
        locked_at=None,
        last_error=None,
        sent_at=None,
    )
    db = SimpleNamespace(
        scalars=lambda _: SimpleNamespace(all=lambda: [row.id]),
        scalar=lambda _: row,
        commit=lambda: None,
        rollback=lambda: None,
        close=lambda: None,
    )
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(tasks, "recover_stale_outbox", lambda *a, **k: 0)

    def deliver(_):
        row.locked_by = "another-worker"
        if fails:
            raise DeliveryError("outcome_http_503")

    monkeypatch.setattr(tasks, "deliver_outcome", deliver)
    assert tasks.dispatch_outbox.run(limit=1) == 0
    assert row.status == OutboxStatus.PROCESSING
    assert row.sent_at is None


def test_publisher_invocations_have_distinct_lease_tokens(monkeypatch):
    # Capture the generated token at the publishing boundary on successive
    # invocations (both direct invocations have the same absent Celery task ID).
    from datetime import UTC, datetime, timedelta

    from app.models.enums import OutboxStatus
    from app.workers import tasks

    row = SimpleNamespace(
        id=uuid4(),
        payload={},
        topic="deliver_n8n_outcome",
        status=OutboxStatus.PENDING,
        attempt_count=0,
        max_attempts=8,
        available_at=datetime.now(UTC) - timedelta(seconds=1),
        locked_by=None,
        locked_at=None,
        last_error=None,
        sent_at=None,
    )
    db = SimpleNamespace(
        scalars=lambda _: SimpleNamespace(all=lambda: [row.id]),
        scalar=lambda _: row,
        commit=lambda: None,
        rollback=lambda: None,
        close=lambda: None,
    )
    tokens = []
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(tasks, "recover_stale_outbox", lambda *a, **k: 0)
    monkeypatch.setattr(tasks, "deliver_outcome", lambda _: tokens.append(row.locked_by))
    assert tasks.dispatch_outbox.run(limit=1) == 1
    row.status = OutboxStatus.PENDING
    assert tasks.dispatch_outbox.run(limit=1) == 1
    assert len(set(tokens)) == 2
