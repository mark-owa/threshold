from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.approvals import DecisionRequest, decide
from app.api.auth import get_current_user
from app.api.ops import get_org_membership
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Order, Organization, User, WorkflowExecution
from app.models.enums import EventSource
from app.workers.tasks import process_event
from app.workflows.engine import WorkflowEngine

router = APIRouter(prefix=f"{get_settings().API_V1_PREFIX}/demo", tags=["demo"])


class EventRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=255)
    source: EventSource = EventSource.API
    payload: dict


@router.post("/orgs/{org_slug}/events")
def create_demo_event(
    org_slug: str,
    request: EventRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = db.scalar(
        select(Organization).where(Organization.slug == org_slug, Organization.is_active.is_(True))
    )
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    get_org_membership(org.id, user.id, db)
    try:
        execution = WorkflowEngine(db).ingest_and_run(
            organization_id=org.id,
            source=request.source,
            idempotency_key=request.idempotency_key,
            raw_payload=request.payload,
            request_id=http_request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "execution_id": str(execution.id),
        "status": execution.status.value,
        "context": execution.context,
        "current_step": execution.current_step_key,
    }


@router.post("/orgs/{org_slug}/events/queue", status_code=202)
def queue_demo_event(
    org_slug: str,
    request: EventRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = db.scalar(
        select(Organization).where(Organization.slug == org_slug, Organization.is_active.is_(True))
    )
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    get_org_membership(org.id, user.id, db)
    task = process_event.delay(
        str(org.id),
        request.source,
        request.idempotency_key,
        request.payload,
        http_request.state.request_id,
    )
    return {"task_id": task.id, "status": "queued", "organization_id": str(org.id)}


@router.get("/executions/{execution_id}")
def get_demo_execution(
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
        "current_step": execution.current_step_key,
        "context": execution.context,
        "steps": [
            {
                "step_key": s.step_key,
                "step_type": s.step_type.value,
                "status": s.status.value,
                "input": s.input_data,
                "output": s.output_data,
                "error": s.error,
                "latency_ms": s.latency_ms,
            }
            for s in execution.step_executions
        ],
    }


@router.post("/approvals/{approval_id}/decision")
def decide_demo_approval(
    approval_id: UUID,
    request: DecisionRequest,
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = decide(approval_id, request, org_id, db, user)
    return {"execution_id": result["execution_id"], "status": result["status"]}


class ScenarioRequest(BaseModel):
    scenario: str = Field(
        pattern=(
            "^(low_risk_refund|high_risk_refund|rejected_refund|failed_refund|"
            "support_inquiry|lead_inquiry)$"
        )
    )


@router.post("/run")
def run_demo_scenario(
    request: ScenarioRequest,
    org_id: UUID,
    http_request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    scenarios = {
        "low_risk_refund": {
            "text": "Please refund order #ORD-1002 for $65.00",
            "sender": "jordan@example.com",
        },
        "high_risk_refund": {
            "text": "Please refund order #ORD-1001 for $89.99",
            "sender": "jordan@example.com",
        },
        "failed_refund": {
            "text": "Please refund order #ORD-1002 for $65.00",
            "sender": "jordan@example.com",
            "simulate_failure_once": True,
        },
        "rejected_refund": {
            "text": "I want a refund for order #ORD-1001 for $150.00 because I changed my mind",
            "sender": "jordan@example.com",
        },
        "support_inquiry": {
            "text": "My account has a problem and I need support",
            "sender": "sam@example.com",
        },
        "lead_inquiry": {
            "text": "I am interested and would like a quote for the premium plan",
            "sender": "prospect@example.com",
        },
    }
    if request.scenario == "failed_refund":
        template = db.scalar(
            select(Order).where(Order.organization_id == org_id, Order.order_number == "ORD-1002")
        )
        if template is None:
            raise HTTPException(status_code=422, detail="Seed the demo orders first")
        order_number = f"DEMO-{uuid4().hex[:12]}"
        from datetime import UTC, datetime

        db.add(
            Order(
                organization_id=org_id,
                customer_id=template.customer_id,
                order_number=order_number,
                amount_usd=template.amount_usd,
                status="completed",
                ordered_at=datetime.now(UTC),
            )
        )
        db.flush()
        scenarios["failed_refund"]["text"] = f"Please refund order #{order_number} for $65.00"
    execution = WorkflowEngine(db).ingest_and_run(
        organization_id=org_id,
        source="api",
        idempotency_key=f"demo:{request.scenario}:{uuid4().hex}",
        raw_payload=scenarios[request.scenario],
        request_id=http_request.state.request_id,
    )
    return {
        "execution_id": str(execution.id),
        "status": execution.status.value,
        "scenario": request.scenario,
    }
