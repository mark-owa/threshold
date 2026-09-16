import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.base import GUID, TimestampMixin, UUIDPKMixin, enum_column
from app.models.enums import EventProcessingStatus, EventSource


class IncomingEvent(Base, UUIDPKMixin, TimestampMixin):
    """The raw, immutable record of something arriving from outside the
    system (a webhook delivery, an inbound email, a form submission).

    `idempotency_key` is unique per organization: a retried webhook
    delivery (which WILL happen -- that's how at-least-once delivery
    works) resolves to the same row instead of a new one, which is what
    stops the same customer request from spawning two workflow runs.
    """

    __tablename__ = "incoming_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_event_org_idempotency"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[EventSource] = mapped_column(enum_column(EventSource), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_status: Mapped[EventProcessingStatus] = mapped_column(
        enum_column(EventProcessingStatus),
        default=EventProcessingStatus.RECEIVED,
        nullable=False,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship()  # noqa: F821
    executions: Mapped[list["WorkflowExecution"]] = relationship(  # noqa: F821
        back_populates="incoming_event"
    )
