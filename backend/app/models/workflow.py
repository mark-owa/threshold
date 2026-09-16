import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.base import GUID, TimestampMixin, UUIDPKMixin, enum_column
from app.models.enums import RequestCategory, StepStatus, StepType, WorkflowStatus


class WorkflowDefinition(Base, UUIDPKMixin, TimestampMixin):
    """A configurable workflow "type", e.g. refund_request_v1. Its steps
    are data (WorkflowStep rows), not code -- that's what makes the engine
    extensible without a redeploy. `organization_id` is nullable: NULL
    means a global template usable by any org; set means an org-specific
    customization of it.
    """

    __tablename__ = "workflow_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", "version", name="uq_workflow_org_key_version"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    trigger_category: Mapped[RequestCategory] = mapped_column(
        enum_column(RequestCategory), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="workflow_definition",
        order_by="WorkflowStep.order_index",
        cascade="all, delete-orphan",
    )


class WorkflowStep(Base, UUIDPKMixin, TimestampMixin):
    """One configured step in a WorkflowDefinition. `step_type` selects
    which engine branch runs it; `config` is handler-specific settings
    (e.g. which prompt_template key + version an ai_extract step uses, or
    which policy fields a business_rule step checks)."""

    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_definition_id", "step_key", name="uq_step_workflow_key"),
    )

    workflow_definition_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    step_type: Mapped[StepType] = mapped_column(enum_column(StepType), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    workflow_definition: Mapped["WorkflowDefinition"] = relationship(back_populates="steps")


class WorkflowExecution(Base, UUIDPKMixin, TimestampMixin):
    """One run of a WorkflowDefinition against one IncomingEvent. The
    unique constraint on incoming_event_id IS the workflow-level
    idempotency guarantee: an event can only ever spawn one execution,
    no matter how many times its webhook is retried."""

    __tablename__ = "workflow_executions"
    __table_args__ = (UniqueConstraint("incoming_event_id", name="uq_execution_per_event"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_definition_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("workflow_definitions.id"), nullable=False, index=True
    )
    incoming_event_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("incoming_events.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[WorkflowStatus] = mapped_column(
        enum_column(WorkflowStatus), default=WorkflowStatus.PENDING, nullable=False, index=True
    )
    current_step_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    incoming_event: Mapped["IncomingEvent"] = relationship(back_populates="executions")  # noqa: F821
    workflow_definition: Mapped["WorkflowDefinition"] = relationship()
    step_executions: Mapped[list["StepExecution"]] = relationship(
        back_populates="workflow_execution",
        order_by="StepExecution.started_at",
        cascade="all, delete-orphan",
    )


class StepExecution(Base, UUIDPKMixin, TimestampMixin):
    """One step's run within a WorkflowExecution. This is the row that
    makes the "click a stage, see inputs/outputs/latency/errors" execution
    detail page possible -- every field the UI needs is captured here."""

    __tablename__ = "step_executions"

    workflow_execution_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    step_type: Mapped[StepType] = mapped_column(enum_column(StepType), nullable=False)
    status: Mapped[StepStatus] = mapped_column(
        enum_column(StepStatus), default=StepStatus.PENDING, nullable=False, index=True
    )

    input_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ai_model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    workflow_execution: Mapped["WorkflowExecution"] = relationship(back_populates="step_executions")
