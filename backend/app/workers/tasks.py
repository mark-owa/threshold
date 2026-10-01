from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    ActionExecution,
    AuditLogEntry,
    IncomingEvent,
    OutboxMessage,
    WorkflowExecution,
)
from app.models.enums import (
    ActionStatus,
    EventProcessingStatus,
    OutboxStatus,
    WorkflowStatus,
)
from app.services.outbox import enqueue_outbox, recover_stale_outbox
from app.services.outcomes import TOPIC, DeliveryError, deliver_outcome
from app.workers.celery_app import celery_app
from app.workflows.engine import WorkflowEngine

settings = get_settings()


@celery_app.task(name="threshold.process_event")
def process_event(
    organization_id: str,
    source: str,
    idempotency_key: str,
    payload: dict,
    request_id: str | None = None,
) -> str:
    """Legacy/demo queue path. Production webhook ingress uses the outbox."""
    db = SessionLocal()
    try:
        execution = WorkflowEngine(db).ingest_and_run(
            organization_id=UUID(organization_id),
            source=source,
            idempotency_key=idempotency_key,
            raw_payload=payload,
            request_id=request_id,
        )
        return str(execution.id)
    finally:
        db.close()


@celery_app.task(name="threshold.process_persisted_event", bind=True)
def process_persisted_event(self, event_id: str, organization_id: str) -> str:
    db = SessionLocal()
    try:
        event = db.scalar(
            select(IncomingEvent).where(
                IncomingEvent.id == UUID(event_id),
                IncomingEvent.organization_id == UUID(organization_id),
            )
        )
        if event is None:
            raise ValueError("Incoming event not found for tenant")
        try:
            execution = WorkflowEngine(db).process_persisted_event(event.id)
        except ValueError as exc:
            if str(exc) == "event_processing_lease_active":
                return "already_processing"
            raise
        return str(execution.id)
    finally:
        db.close()


@celery_app.task(name="threshold.sync_shopify_order")
def sync_shopify_order(event_id: str, organization_id: str) -> str:
    db = SessionLocal()
    try:
        event = db.scalar(
            select(IncomingEvent).where(
                IncomingEvent.id == UUID(event_id),
                IncomingEvent.organization_id == UUID(organization_id),
            )
        )
        if event is None:
            raise ValueError("Incoming event not found for tenant")
        if event.processing_status == EventProcessingStatus.COMPLETED:
            return "already_completed"
        wrapper = event.raw_payload or {}
        payload = wrapper.get("payload") if isinstance(wrapper, dict) else None
        if not isinstance(payload, dict):
            raise ValueError("Shopify event payload is invalid")
        from app.integrations.shopify import snapshot_from_webhook, upsert_shopify_order

        snapshot = snapshot_from_webhook(payload)
        order = upsert_shopify_order(db, event.organization_id, snapshot)
        event.normalized_payload = {
            "provider": "shopify",
            "topic": wrapper.get("shopify_topic"),
            "order_number": order.order_number,
            "external_order_id": order.external_order_id,
        }
        event.processing_status = EventProcessingStatus.COMPLETED
        event.completed_at = datetime.now(UTC)
        event.last_error = None
        db.add(
            AuditLogEntry(
                organization_id=event.organization_id,
                workflow_execution_id=None,
                event_type="shopify.order_cached",
                actor_type="system",
                payload={
                    "event_id": str(event.id),
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "external_order_id": order.external_order_id,
                },
            )
        )
        db.commit()
        return str(order.id)
    finally:
        db.close()


@celery_app.task(name="threshold.execute_action", bind=True)
def execute_action(self, action_id: str, organization_id: str) -> str:
    db = SessionLocal()
    try:
        action = db.scalar(
            select(ActionExecution).where(
                ActionExecution.id == UUID(action_id),
                ActionExecution.organization_id == UUID(organization_id),
            )
        )
        if action is None:
            raise ValueError("Action not found for tenant")
        action = WorkflowEngine(db).execute_queued_action(
            action.id, worker_id=f"celery:{self.request.id or 'unknown'}"
        )
        return action.status.value
    finally:
        db.close()


def _publish_message(row: OutboxMessage) -> None:
    payload = row.payload or {}
    if row.topic == TOPIC:
        deliver_outcome(row)
        return
    if row.topic == "process_incoming_event":
        celery_app.send_task(
            "threshold.process_persisted_event",
            args=[payload["event_id"], payload["organization_id"]],
        )
        return
    if row.topic == "execute_action":
        celery_app.send_task(
            "threshold.execute_action",
            args=[payload["action_id"], payload["organization_id"]],
        )
        return
    if row.topic == "sync_shopify_order":
        celery_app.send_task(
            "threshold.sync_shopify_order",
            args=[payload["event_id"], payload["organization_id"]],
        )
        return
    raise ValueError(f"Unsupported outbox topic: {row.topic}")


@celery_app.task(name="threshold.dispatch_outbox", bind=True)
def dispatch_outbox(self, limit: int | None = None) -> int:
    """Publish committed tasks or deliver n8n outcomes with stale-lease recovery.

    A crash after publish but before SENT is deliberately safe: the message may
    be published twice, and both consumers are idempotent.
    """
    batch_size = min(limit or settings.OUTBOX_BATCH_SIZE, settings.OUTBOX_BATCH_SIZE)
    # Broker redelivery can reuse a Celery task ID. Each publisher invocation
    # needs its own lease token so an old invocation cannot finish a newer lease.
    worker_id = f"outbox:{uuid4()}"
    published = 0
    db = SessionLocal()
    try:
        recovered = recover_stale_outbox(
            db, lease_seconds=settings.OUTBOX_LEASE_SECONDS, limit=batch_size * 2
        )
        if recovered:
            db.commit()

        ids = db.scalars(
            select(OutboxMessage.id)
            .where(
                OutboxMessage.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]),
                OutboxMessage.available_at <= datetime.now(UTC),
            )
            .order_by(OutboxMessage.available_at.asc(), OutboxMessage.created_at.asc())
            .limit(batch_size)
        ).all()
        for message_id in ids:
            row = db.scalar(
                select(OutboxMessage)
                .where(OutboxMessage.id == message_id)
                .with_for_update(skip_locked=True)
            )
            if row is None or row.status not in {OutboxStatus.PENDING, OutboxStatus.FAILED}:
                db.rollback()
                continue
            if row.available_at > datetime.now(UTC):
                db.rollback()
                continue
            row.status = OutboxStatus.PROCESSING
            row.attempt_count += 1
            row.locked_at = datetime.now(UTC)
            row.locked_by = worker_id
            db.commit()

            try:
                _publish_message(row)
            except Exception as exc:  # broker/topic failure, safe to retry publishing
                row = db.scalar(
                    select(OutboxMessage)
                    .where(OutboxMessage.id == message_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if (
                    row is not None
                    and row.status == OutboxStatus.PROCESSING
                    and row.locked_by == worker_id
                ):
                    row.last_error = str(exc)
                    row.locked_at = None
                    row.locked_by = None
                    if row.attempt_count >= row.max_attempts or (
                        isinstance(exc, DeliveryError) and not exc.retryable
                    ):
                        row.status = OutboxStatus.DEAD_LETTER
                    else:
                        row.status = OutboxStatus.FAILED
                        delay = max(
                            min(300, 2 ** min(row.attempt_count, 8)), getattr(exc, "retry_after", 0)
                        )
                        row.available_at = datetime.now(UTC) + timedelta(seconds=delay)
                    db.commit()
                else:
                    db.rollback()
                continue

            row = db.scalar(
                select(OutboxMessage)
                .where(OutboxMessage.id == message_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                row is not None
                and row.status == OutboxStatus.PROCESSING
                and row.locked_by == worker_id
            ):
                row.status = OutboxStatus.SENT
                row.sent_at = datetime.now(UTC)
                row.locked_at = None
                row.locked_by = None
                row.last_error = None
                db.commit()
                published += 1
            else:
                db.rollback()
        return published
    finally:
        db.close()


@celery_app.task(name="threshold.recover_stale_actions")
def recover_stale_actions(limit: int = 100) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.ACTION_EXECUTION_LEASE_SECONDS)
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(ActionExecution)
            .where(
                ActionExecution.status == ActionStatus.EXECUTING,
                ActionExecution.locked_at.is_not(None),
                ActionExecution.locked_at < cutoff,
            )
            .order_by(ActionExecution.locked_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for action in rows:
            action.status = ActionStatus.UNKNOWN
            action.error = "worker_lease_expired_provider_outcome_unknown"
            action.locked_at = None
            action.locked_by = None
            action.next_retry_at = None
            db.add(
                AuditLogEntry(
                    organization_id=action.organization_id,
                    workflow_execution_id=action.workflow_execution_id,
                    event_type="action.worker_lease_expired",
                    actor_type="system",
                    payload={"action_id": str(action.id), "requires_reconciliation": True},
                )
            )
        db.commit()
        return len(rows)
    finally:
        db.close()


@celery_app.task(name="threshold.recover_stale_events")
def recover_stale_events(limit: int = 100) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.EVENT_PROCESSING_LEASE_SECONDS)
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(IncomingEvent)
            .where(
                IncomingEvent.processing_status == EventProcessingStatus.PROCESSING,
                IncomingEvent.processing_started_at.is_not(None),
                IncomingEvent.processing_started_at < cutoff,
            )
            .order_by(IncomingEvent.processing_started_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for event in rows:
            execution = db.scalar(
                select(WorkflowExecution).where(WorkflowExecution.incoming_event_id == event.id)
            )
            event.processing_started_at = None
            event.last_error = "event_worker_lease_expired"
            if execution is not None:
                # A committed RUNNING execution cannot safely be reconstructed from
                # arbitrary mid-step state. Surface it instead of fabricating replay.
                if execution.status == WorkflowStatus.RUNNING:
                    execution.status = WorkflowStatus.FAILED
                    execution.error = "event_worker_lease_expired_manual_recovery_required"
                    execution.completed_at = datetime.now(UTC)
                    event.processing_status = EventProcessingStatus.DEAD_LETTER
                continue
            if event.processing_attempts >= event.max_processing_attempts:
                event.processing_status = EventProcessingStatus.DEAD_LETTER
                event.next_retry_at = None
            else:
                event.processing_status = EventProcessingStatus.FAILED
                event.next_retry_at = datetime.now(UTC)
                enqueue_outbox(
                    db,
                    organization_id=event.organization_id,
                    topic="process_incoming_event",
                    aggregate_type="incoming_event",
                    aggregate_id=event.id,
                    payload={
                        "event_id": str(event.id),
                        "organization_id": str(event.organization_id),
                    },
                    available_at=event.next_retry_at,
                )
        db.commit()
        return len(rows)
    finally:
        db.close()


@celery_app.task(name="threshold.retry_due_actions")
def retry_due_actions(limit: int = 50) -> int:
    """Legacy demo retry path. Live actions retry through the durable outbox."""
    db = SessionLocal()
    processed = 0
    try:
        rows = db.scalars(
            select(ActionExecution)
            .where(
                ActionExecution.status == ActionStatus.RETRYING,
                ActionExecution.next_retry_at.is_not(None),
                ActionExecution.next_retry_at <= datetime.now(UTC),
            )
            .order_by(ActionExecution.next_retry_at.asc())
            .limit(limit)
        ).all()
        for action in rows:
            execution = db.get(WorkflowExecution, action.workflow_execution_id)
            if execution is None or execution.status != WorkflowStatus.FAILED:
                continue
            try:
                WorkflowEngine(db).retry_failed_execution(execution, force=False)
            except ValueError:
                db.rollback()
                continue
            processed += 1
        return processed
    finally:
        db.close()
