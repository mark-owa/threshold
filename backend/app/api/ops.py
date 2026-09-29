from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.tenancy import get_org_membership, require_org_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    ActionAttempt,
    ActionExecution,
    AIUsageLog,
    ApprovalRequest,
    AuditLogEntry,
    IncomingEvent,
    Organization,
    OutboxMessage,
    StepExecution,
    User,
    WorkflowExecution,
)
from app.models.enums import (
    ActionStatus,
    ApprovalStatus,
    EventProcessingStatus,
    MemberRole,
    OutboxStatus,
    WorkflowStatus,
)
from app.services.beta_readiness import build_beta_readiness
from app.services.outbox import enqueue_outbox
from app.workers.celery_app import celery_app
from app.workflows.engine import WorkflowEngine

router = APIRouter(prefix=f"{get_settings().API_V1_PREFIX}/ops", tags=["operations"])


class LiveExecutionRequest(BaseModel):
    enabled: bool


@router.get("/beta-readiness")
def beta_readiness(
    org_id: UUID,
    probe_runtime: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required",
    )
    return build_beta_readiness(db, org_id, probe_runtime=probe_runtime)


@router.post("/beta-readiness/live-execution")
def set_live_execution(
    request: LiveExecutionRequest,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required",
    )
    organization = db.get(Organization, org_id)
    if organization is None or not organization.is_active:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if request.enabled:
        if membership.role != MemberRole.OWNER:
            raise HTTPException(
                status_code=403, detail="Owner permission required to enable live execution"
            )
        report = build_beta_readiness(db, org_id, probe_runtime=True)
        if report["summary"]["block"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Private-beta readiness blockers must be resolved before enabling live execution",
                    "summary": report["summary"],
                    "blockers": [check for check in report["checks"] if check["level"] == "block"],
                },
            )

    organization.settings = {
        **(organization.settings or {}),
        "live_execution_enabled": request.enabled,
        "live_execution_changed_at": datetime.now(UTC).isoformat(),
        "live_execution_changed_by": str(user.id),
    }
    db.add(
        AuditLogEntry(
            organization_id=org_id,
            workflow_execution_id=None,
            event_type="workspace.live_execution_enabled"
            if request.enabled
            else "workspace.live_execution_disabled",
            actor_type="human",
            actor_id=str(user.id),
            payload={"enabled": request.enabled},
        )
    )
    db.commit()
    db.refresh(organization)
    return {
        "organization_id": str(org_id),
        "live_execution_enabled": bool((organization.settings or {}).get("live_execution_enabled")),
    }


@router.get("/tasks/{task_id}")
def task_status(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Celery task state contains no tenant identity, so this endpoint only
    # exposes coarse execution state; the resulting execution remains protected
    # by the tenant-scoped execution APIs.
    state = celery_app.AsyncResult(task_id).state
    return {"task_id": task_id, "state": state}


@router.get("/executions/{execution_id}")
def get_execution(
    execution_id: UUID,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    execution = db.scalar(
        select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.organization_id == org_id,
        )
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {
        "id": str(execution.id),
        "status": execution.status.value,
        "workflow_id": str(execution.workflow_definition_id),
        "current_step": execution.current_step_key,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "error": execution.error,
        "context": execution.context,
        "steps": [
            {
                "id": str(s.id),
                "step_key": s.step_key,
                "step_type": s.step_type.value,
                "status": s.status.value,
                "latency_ms": s.latency_ms,
                "input": s.input_data,
                "output": s.output_data,
                "error": s.error,
            }
            for s in execution.step_executions
        ],
    }


@router.post("/executions/{execution_id}/retry")
def retry_execution(
    execution_id: UUID,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.REVIEWER},
        detail="Reviewer permission required",
    )
    execution = db.scalar(
        select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.organization_id == org_id,
        )
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    try:
        execution = WorkflowEngine(db).retry_failed_execution(execution, force=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": str(execution.id), "status": execution.status.value, "error": execution.error}


@router.get("/executions")
def list_executions(
    org_id: UUID,
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    rows = db.scalars(
        select(WorkflowExecution)
        .where(WorkflowExecution.organization_id == org_id)
        .order_by(WorkflowExecution.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(e.id),
            "status": e.status.value,
            "workflow_id": str(e.workflow_definition_id),
            "current_step": e.current_step_key,
            "started_at": e.started_at,
            "completed_at": e.completed_at,
            "error": e.error,
        }
        for e in rows
    ]


@router.get("/approvals")
def list_approvals(
    org_id: UUID,
    status_filter: ApprovalStatus | None = Query(default=ApprovalStatus.PENDING, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.REVIEWER},
        detail="Reviewer permission required",
    )
    rows = db.scalars(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.organization_id == org_id,
            ApprovalRequest.status == status_filter,
        )
        .order_by(ApprovalRequest.created_at.asc())
    ).all()
    return [
        {
            "id": str(a.id),
            "execution_id": str(a.workflow_execution_id),
            "status": a.status.value,
            "risk_level": a.risk_level.value,
            "risk_factors": a.risk_factors,
            "reason": a.reason,
            "proposed_action": a.proposed_action,
            "generated_parameters": a.generated_parameters,
            "created_at": a.created_at,
        }
        for a in rows
    ]


@router.get("/metrics")
def metrics(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    total = (
        db.scalar(
            select(func.count())
            .select_from(WorkflowExecution)
            .where(WorkflowExecution.organization_id == org_id)
        )
        or 0
    )
    completed = (
        db.scalar(
            select(func.count())
            .select_from(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.status == WorkflowStatus.COMPLETED,
            )
        )
        or 0
    )
    failed = (
        db.scalar(
            select(func.count())
            .select_from(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.status == WorkflowStatus.FAILED,
            )
        )
        or 0
    )
    awaiting = (
        db.scalar(
            select(func.count())
            .select_from(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.status == WorkflowStatus.AWAITING_APPROVAL,
            )
        )
        or 0
    )
    waiting_external = (
        db.scalar(
            select(func.count())
            .select_from(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.status == WorkflowStatus.WAITING_EXTERNAL,
            )
        )
        or 0
    )
    approvals = (
        db.scalar(
            select(func.count())
            .select_from(ApprovalRequest)
            .where(ApprovalRequest.organization_id == org_id)
        )
        or 0
    )
    approved = (
        db.scalar(
            select(func.count())
            .select_from(ApprovalRequest)
            .where(
                ApprovalRequest.organization_id == org_id,
                ApprovalRequest.status.in_([ApprovalStatus.APPROVED, ApprovalStatus.MODIFIED]),
            )
        )
        or 0
    )
    automatic = (
        db.scalar(
            select(func.count())
            .select_from(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.status == WorkflowStatus.COMPLETED,
                ~select(ApprovalRequest.id)
                .where(ApprovalRequest.workflow_execution_id == WorkflowExecution.id)
                .exists(),
            )
        )
        or 0
    )
    automation_rate = round((automatic / total) * 100, 2) if total else 0.0
    approval_rate = round((approved / approvals) * 100, 2) if approvals else 0.0
    avg_latency_ms = (
        db.scalar(
            select(func.avg(StepExecution.latency_ms))
            .join(WorkflowExecution, WorkflowExecution.id == StepExecution.workflow_execution_id)
            .where(
                WorkflowExecution.organization_id == org_id,
                StepExecution.latency_ms.is_not(None),
            )
        )
        or 0
    )
    ai_cost = (
        db.scalar(
            select(func.coalesce(func.sum(AIUsageLog.cost_usd), 0)).where(
                AIUsageLog.organization_id == org_id
            )
        )
        or 0
    )
    estimated_hours_saved = round(automatic * 0.25, 2)
    settled = total - awaiting - waiting_external
    success_rate = round((completed / settled) * 100, 2) if settled else 0.0
    return {
        "total_executions": total,
        "completed": completed,
        "failed": failed,
        "awaiting_approval": awaiting,
        "waiting_external": waiting_external,
        "automation_rate_percent": automation_rate,
        "approval_rate_percent": approval_rate,
        "workflow_success_rate_percent": success_rate,
        "average_step_latency_ms": round(float(avg_latency_ms), 2),
        "estimated_ai_cost_usd": round(float(ai_cost), 4),
        "estimated_hours_saved": estimated_hours_saved,
    }


@router.get("/audit")
def audit_feed(
    org_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    rows = db.scalars(
        select(AuditLogEntry)
        .where(AuditLogEntry.organization_id == org_id)
        .order_by(AuditLogEntry.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(r.id),
            "execution_id": str(r.workflow_execution_id) if r.workflow_execution_id else None,
            "event_type": r.event_type,
            "actor_type": r.actor_type,
            "actor_id": r.actor_id,
            "payload": r.payload,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/actions")
def list_actions(
    org_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    rows = db.scalars(
        select(ActionExecution)
        .where(ActionExecution.organization_id == org_id)
        .order_by(ActionExecution.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(row.id),
            "execution_id": str(row.workflow_execution_id),
            "action_type": row.action_type,
            "status": row.status.value,
            "attempt_count": row.attempt_count,
            "max_attempts": row.max_attempts,
            "verified_at": row.verified_at,
            "next_retry_at": row.next_retry_at,
            "error": row.error,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/actions/{action_id}")
def get_action(
    action_id: UUID,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    row = db.scalar(
        select(ActionExecution).where(
            ActionExecution.id == action_id,
            ActionExecution.organization_id == org_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Action not found")
    attempts = db.scalars(
        select(ActionAttempt)
        .where(
            ActionAttempt.action_execution_id == row.id,
            ActionAttempt.organization_id == org_id,
        )
        .order_by(ActionAttempt.created_at.asc())
    ).all()
    return {
        "id": str(row.id),
        "execution_id": str(row.workflow_execution_id),
        "action_type": row.action_type,
        "status": row.status.value,
        "idempotency_key": row.idempotency_key,
        "request_payload": row.request_payload,
        "response_payload": row.response_payload,
        "verified_at": row.verified_at,
        "error": row.error,
        "attempts": [
            {
                "id": str(attempt.id),
                "attempt_number": attempt.attempt_number,
                "operation": attempt.operation,
                "provider": attempt.provider,
                "provider_operation_id": attempt.provider_operation_id,
                "outcome": attempt.outcome,
                "response_payload": attempt.response_payload,
                "error": attempt.error,
                "started_at": attempt.started_at,
                "completed_at": attempt.completed_at,
            }
            for attempt in attempts
        ],
    }


@router.post("/actions/{action_id}/reconcile")
def reconcile_action(
    action_id: UUID,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.REVIEWER},
        detail="Reviewer permission required",
    )
    action = db.scalar(
        select(ActionExecution).where(
            ActionExecution.id == action_id,
            ActionExecution.organization_id == org_id,
        )
    )
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    try:
        action = WorkflowEngine(db).reconcile_action(action)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": str(action.id),
        "status": action.status.value,
        "verified_at": action.verified_at,
        "next_retry_at": action.next_retry_at,
        "error": action.error,
    }


@router.get("/recovery")
def recovery_overview(
    org_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    events = db.scalars(
        select(IncomingEvent)
        .where(
            IncomingEvent.organization_id == org_id,
            IncomingEvent.processing_status.in_(
                [EventProcessingStatus.FAILED, EventProcessingStatus.DEAD_LETTER]
            ),
        )
        .order_by(IncomingEvent.updated_at.desc())
        .limit(limit)
    ).all()
    outbox = db.scalars(
        select(OutboxMessage)
        .where(
            OutboxMessage.organization_id == org_id,
            OutboxMessage.status.in_(
                [OutboxStatus.PROCESSING, OutboxStatus.FAILED, OutboxStatus.DEAD_LETTER]
            ),
        )
        .order_by(OutboxMessage.updated_at.desc())
        .limit(limit)
    ).all()
    actions = db.scalars(
        select(ActionExecution)
        .where(
            ActionExecution.organization_id == org_id,
            ActionExecution.status.in_(
                [
                    ActionStatus.UNKNOWN,
                    ActionStatus.RETRYING,
                    ActionStatus.DEAD_LETTER,
                    ActionStatus.FAILED,
                ]
            ),
        )
        .order_by(ActionExecution.updated_at.desc())
        .limit(limit)
    ).all()
    return {
        "events": [
            {
                "id": str(row.id),
                "external_id": row.external_id,
                "status": row.processing_status.value,
                "attempts": row.processing_attempts,
                "max_attempts": row.max_processing_attempts,
                "next_retry_at": row.next_retry_at,
                "error": row.last_error,
                "updated_at": row.updated_at,
            }
            for row in events
        ],
        "outbox": [
            {
                "id": str(row.id),
                "topic": row.topic,
                "aggregate_type": row.aggregate_type,
                "aggregate_id": str(row.aggregate_id),
                "status": row.status.value,
                "attempts": row.attempt_count,
                "max_attempts": row.max_attempts,
                "available_at": row.available_at,
                "locked_at": row.locked_at,
                "error": row.last_error,
                "updated_at": row.updated_at,
            }
            for row in outbox
        ],
        "actions": [
            {
                "id": str(row.id),
                "action_type": row.action_type,
                "status": row.status.value,
                "attempts": row.attempt_count,
                "max_attempts": row.max_attempts,
                "next_retry_at": row.next_retry_at,
                "locked_at": row.locked_at,
                "error": row.error,
                "updated_at": row.updated_at,
            }
            for row in actions
        ],
    }


@router.post("/events/{event_id}/replay")
def replay_event(
    event_id: UUID,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.REVIEWER},
        detail="Reviewer permission required",
    )
    event = db.scalar(
        select(IncomingEvent)
        .where(IncomingEvent.id == event_id, IncomingEvent.organization_id == org_id)
        .with_for_update()
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    execution = db.scalar(
        select(WorkflowExecution).where(WorkflowExecution.incoming_event_id == event.id)
    )
    if execution is not None:
        raise HTTPException(
            status_code=409,
            detail="Event already has an execution; recover the execution/action instead of replaying input",
        )
    if event.processing_status not in {
        EventProcessingStatus.FAILED,
        EventProcessingStatus.DEAD_LETTER,
    }:
        raise HTTPException(status_code=409, detail="Event is not in a replayable failure state")
    event.processing_status = EventProcessingStatus.RECEIVED
    event.processing_attempts = 0
    event.next_retry_at = None
    event.processing_started_at = None
    event.last_error = None
    enqueue_outbox(
        db,
        organization_id=org_id,
        topic="process_incoming_event",
        aggregate_type="incoming_event",
        aggregate_id=event.id,
        payload={"event_id": str(event.id), "organization_id": str(org_id)},
    )
    db.add(
        AuditLogEntry(
            organization_id=org_id,
            workflow_execution_id=None,
            event_type="event.manual_replay_queued",
            actor_type="human",
            actor_id=str(user.id),
            payload={"event_id": str(event.id)},
        )
    )
    db.commit()
    return {"event_id": str(event.id), "status": "queued"}


@router.post("/outbox/{message_id}/requeue")
def requeue_outbox(
    message_id: UUID,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required",
    )
    row = db.scalar(
        select(OutboxMessage)
        .where(OutboxMessage.id == message_id, OutboxMessage.organization_id == org_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Outbox message not found")
    if row.status not in {OutboxStatus.FAILED, OutboxStatus.DEAD_LETTER}:
        raise HTTPException(status_code=409, detail="Outbox message is not requeueable")
    row.status = OutboxStatus.PENDING
    row.attempt_count = 0
    row.available_at = datetime.now(UTC)
    row.locked_at = None
    row.locked_by = None
    row.last_error = None
    db.add(
        AuditLogEntry(
            organization_id=org_id,
            workflow_execution_id=None,
            event_type="outbox.manual_requeue",
            actor_type="human",
            actor_id=str(user.id),
            payload={"outbox_id": str(row.id), "topic": row.topic},
        )
    )
    db.commit()
    return {"outbox_id": str(row.id), "status": row.status.value}
