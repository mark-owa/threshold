from uuid import UUID

from app.db.session import SessionLocal
from app.workers.celery_app import celery_app
from app.workflows.engine import WorkflowEngine


@celery_app.task(name="threshold.process_event")
def process_event(
    organization_id: str,
    source: str,
    idempotency_key: str,
    payload: dict,
    request_id: str | None = None,
) -> str:
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


@celery_app.task(name="threshold.retry_due_actions")
def retry_due_actions(limit: int = 50) -> int:
    """Process actions whose exponential-backoff retry window has opened."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.models import ActionExecution, WorkflowExecution
    from app.models.enums import ActionStatus, WorkflowStatus

    db = SessionLocal()
    processed = 0
    try:
        now = datetime.now(UTC)
        rows = db.scalars(
            select(ActionExecution)
            .where(
                ActionExecution.status == ActionStatus.RETRYING,
                ActionExecution.next_retry_at.is_not(None),
                ActionExecution.next_retry_at <= now,
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
