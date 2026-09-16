import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base import GUID, UUIDPKMixin


class AuditLogEntry(Base, UUIDPKMixin):
    """Append-only. Deliberately does NOT use TimestampMixin -- there is
    no updated_at, because audit entries are never updated, only created.
    The engine appends lifecycle events here; detailed classification
    and extraction results live in step_executions. Database-level
    immutability is not enforced.
    """

    __tablename__ = "audit_log_entries"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("workflow_executions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)  # system | ai | human
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
