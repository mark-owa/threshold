import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.base import GUID, TimestampMixin, UUIDPKMixin, enum_column
from app.models.enums import ApprovalStatus, RiskLevel


class ApprovalRequest(Base, UUIDPKMixin, TimestampMixin):
    """A human approval gate hit by a workflow. Every field your spec
    required for an approval record is represented here: proposed action,
    reason, AI confidence, risk level, source context, generated
    parameters, reviewer + decision + modification, and the final
    execution result once it's carried out."""

    __tablename__ = "approval_requests"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_execution_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("step_executions.id", ondelete="SET NULL"), nullable=True
    )

    proposed_action: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(
        enum_column(RiskLevel), nullable=False, index=True
    )
    risk_factors: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source_context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    generated_parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    status: Mapped[ApprovalStatus] = mapped_column(
        enum_column(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_execution_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    workflow_execution: Mapped["WorkflowExecution"] = relationship()  # noqa: F821
    reviewer: Mapped["User | None"] = relationship()  # noqa: F821
