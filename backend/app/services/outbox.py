from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OutboxMessage
from app.models.enums import OutboxStatus


def enqueue_outbox(
    db: Session,
    *,
    organization_id: uuid.UUID,
    topic: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload: dict,
    available_at: datetime | None = None,
    max_attempts: int = 10,
) -> OutboxMessage:
    row = OutboxMessage(
        organization_id=organization_id,
        topic=topic,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        status=OutboxStatus.PENDING,
        attempt_count=0,
        max_attempts=max_attempts,
        available_at=available_at or datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    return row


def recover_stale_outbox(db: Session, *, lease_seconds: int, limit: int = 200) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=lease_seconds)
    rows = db.scalars(
        select(OutboxMessage)
        .where(
            OutboxMessage.status == OutboxStatus.PROCESSING,
            OutboxMessage.locked_at.is_not(None),
            OutboxMessage.locked_at < cutoff,
        )
        .order_by(OutboxMessage.locked_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    for row in rows:
        row.status = OutboxStatus.PENDING
        row.locked_at = None
        row.locked_by = None
        row.last_error = "publisher_lease_expired"
        row.available_at = datetime.now(UTC)
    return len(rows)
