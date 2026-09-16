from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    AIUsageLog,
    ApprovalRequest,
    AuditLogEntry,
    OrganizationMember,
    StepExecution,
    User,
    WorkflowExecution,
)
from app.models.enums import ApprovalStatus, WorkflowStatus
from app.workers.celery_app import celery_app
from app.workflows.engine import WorkflowEngine

router = APIRouter(prefix=f"{get_settings().API_V1_PREFIX}/ops", tags=["operations"])


def get_org_membership(org_id: UUID, user_id: UUID, db: Session) -> OrganizationMember:
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="User is not a member of this organization")
    return membership


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
    membership = get_org_membership(org_id, user.id, db)
    if membership.role.value not in {"owner", "admin", "reviewer"}:
        raise HTTPException(status_code=403, detail="Reviewer permission required")
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
    membership = get_org_membership(org_id, user.id, db)
    if membership.role.value not in {"owner", "admin", "reviewer"}:
        raise HTTPException(status_code=403, detail="Reviewer permission required")
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
    success_rate = round((completed / (total - awaiting)) * 100, 2) if (total - awaiting) else 0.0
    return {
        "total_executions": total,
        "completed": completed,
        "failed": failed,
        "awaiting_approval": awaiting,
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
