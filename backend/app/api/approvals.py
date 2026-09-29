from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.tenancy import require_org_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.models import ApprovalRequest, User
from app.models.enums import ApprovalStatus, MemberRole
from app.workflows.engine import WorkflowEngine

router = APIRouter(prefix=f"{get_settings().API_V1_PREFIX}/approvals", tags=["approvals"])


class DecisionRequest(BaseModel):
    decision: ApprovalStatus
    notes: str | None = None
    modified_parameters: dict | None = None



@router.post("/{approval_id}/decision")
def decide(
    approval_id: UUID,
    request: DecisionRequest,
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
    approval = db.scalar(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.organization_id == org_id,
        )
        .with_for_update()
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail="Approval already decided")
    if request.decision not in {
        ApprovalStatus.APPROVED,
        ApprovalStatus.MODIFIED,
        ApprovalStatus.REJECTED,
    }:
        raise HTTPException(
            status_code=422, detail="Decision must be approved, modified, or rejected"
        )
    if request.decision == ApprovalStatus.MODIFIED and not request.modified_parameters:
        raise HTTPException(
            status_code=422, detail="modified_parameters required for modified decisions"
        )

    if request.decision != ApprovalStatus.MODIFIED and request.modified_parameters is not None:
        raise HTTPException(status_code=422, detail="Parameters require a modified decision")

    approval.status = request.decision
    approval.reviewer_id = user.id
    approval.reviewer_notes = request.notes
    approval.modified_parameters = request.modified_parameters
    from datetime import UTC, datetime

    approval.decided_at = datetime.now(UTC)

    execution = WorkflowEngine(db).resume_after_approval(approval, user.id)
    return {
        "approval_id": str(approval.id),
        "execution_id": str(execution.id),
        "status": execution.status.value,
        "reviewer_id": str(user.id),
    }
