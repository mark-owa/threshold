from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.prompts import resolve_prompt
from app.ai.providers import get_ai_provider
from app.core.config import get_settings
from app.integrations.providers import get_refund_provider
from app.models import (
    ActionAttempt,
    ActionExecution,
    AIUsageLog,
    ApprovalRequest,
    AuditLogEntry,
    IncomingEvent,
    IntegrationConfig,
    Order,
    Organization,
    Policy,
    StepExecution,
    WorkflowDefinition,
    WorkflowExecution,
)
from app.models.enums import (
    ActionStatus,
    ApprovalStatus,
    EventProcessingStatus,
    EventSource,
    IntegrationProvider,
    NotificationChannel,
    RequestCategory,
    RiskLevel,
    StepStatus,
    StepType,
    WorkflowStatus,
)
from app.services.commercial import assert_entitled, increment_usage
from app.services.outbox import enqueue_outbox
from app.workflows.primitives import (
    classify_text,
    extract_refund,
    normalize_payload,
    retry_delay_seconds,
)


@dataclass(frozen=True)
class StepResult:
    status: StepStatus
    output: dict
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_tokens: int | None = None
    ai_prompt_tokens: int | None = None
    ai_completion_tokens: int | None = None
    ai_cost_usd: float | None = None
    ai_latency_ms: int | None = None


class WorkflowEngine:
    """Small, deterministic workflow runner for the reference portfolio slice.

    The engine intentionally keeps the LLM boundary narrow: classification and
    extraction may be probabilistic, while policy evaluation, risk gating, and
    side effects are deterministic and persisted.
    """

    def __init__(self, db: Session):
        self.db = db

    def ingest_and_run(
        self,
        *,
        organization_id: uuid.UUID,
        source: str,
        idempotency_key: str,
        raw_payload: dict,
        request_id: str | None = None,
    ) -> WorkflowExecution:
        """Synchronous compatibility path used by the demo and tests.

        Production webhooks use the durable ingress/outbox path instead.
        """
        source = EventSource(source)
        org = self.db.scalar(
            select(Organization).where(Organization.id == organization_id).with_for_update()
        )
        if org is None or not org.is_active:
            raise ValueError("Organization not found or inactive")
        existing_event = self.db.scalar(
            select(IncomingEvent).where(
                IncomingEvent.organization_id == organization_id,
                IncomingEvent.idempotency_key == idempotency_key,
            )
        )
        if existing_event:
            existing_execution = self.db.scalar(
                select(WorkflowExecution).where(
                    WorkflowExecution.incoming_event_id == existing_event.id
                )
            )
            if existing_execution:
                return existing_execution
            event = existing_event
        else:
            event = IncomingEvent(
                organization_id=organization_id,
                source=source,
                idempotency_key=idempotency_key,
                request_id=request_id,
                raw_payload=raw_payload,
                signature_verified=False,
            )
            self.db.add(event)
            self.db.flush()
            self._audit(
                organization_id, None, "event_received", "system", {"event_id": str(event.id)}
            )
        return self._run_event_record(event)

    def process_persisted_event(self, event_id: uuid.UUID) -> WorkflowExecution:
        """Idempotently process an already committed inbound event.

        The event row is the durable source of truth; worker redelivery is safe.
        """
        event = self.db.scalar(
            select(IncomingEvent).where(IncomingEvent.id == event_id).with_for_update()
        )
        if event is None:
            raise ValueError("Incoming event not found")
        existing = self.db.scalar(
            select(WorkflowExecution).where(WorkflowExecution.incoming_event_id == event.id)
        )
        if existing is not None:
            if existing.status == WorkflowStatus.COMPLETED:
                event.processing_status = EventProcessingStatus.COMPLETED
                event.completed_at = existing.completed_at or datetime.now(UTC)
                event.last_error = None
                self.db.commit()
            return existing

        lease_cutoff = datetime.now(UTC) - timedelta(
            seconds=get_settings().EVENT_PROCESSING_LEASE_SECONDS
        )
        if (
            event.processing_status == EventProcessingStatus.PROCESSING
            and event.processing_started_at is not None
            and event.processing_started_at > lease_cutoff
        ):
            raise ValueError("event_processing_lease_active")

        event.processing_status = EventProcessingStatus.PROCESSING
        event.processing_attempts += 1
        event.processing_started_at = datetime.now(UTC)
        event.next_retry_at = None
        event.last_error = None
        self.db.commit()

        try:
            event = self.db.get(IncomingEvent, event_id)
            if event is None:
                raise ValueError("Incoming event disappeared during processing")
            return self._run_event_record(event)
        except Exception as exc:
            self.db.rollback()
            event = self.db.scalar(
                select(IncomingEvent).where(IncomingEvent.id == event_id).with_for_update()
            )
            if event is not None:
                event.last_error = str(exc)
                event.processing_started_at = None
                if event.processing_attempts >= event.max_processing_attempts:
                    event.processing_status = EventProcessingStatus.DEAD_LETTER
                    event.next_retry_at = None
                else:
                    event.processing_status = EventProcessingStatus.FAILED
                    event.next_retry_at = datetime.now(UTC) + timedelta(
                        seconds=self.retry_delay_seconds(event.processing_attempts, base=5, cap=300)
                    )
                    enqueue_outbox(
                        self.db,
                        organization_id=event.organization_id,
                        topic="process_incoming_event",
                        aggregate_type="incoming_event",
                        aggregate_id=event.id,
                        payload={
                            "event_id": str(event.id),
                            "organization_id": str(event.organization_id),
                        },
                        available_at=event.next_retry_at,
                    )
                self.db.commit()
            raise

    def _run_event_record(self, event: IncomingEvent) -> WorkflowExecution:
        normalized = self._normalize(event.raw_payload)
        event.external_id = event.external_id or normalized.get("external_id")
        event.normalized_payload = normalized
        event.processing_status = EventProcessingStatus.NORMALIZED
        self._audit(event.organization_id, None, "event_normalized", "system", normalized)

        category = self._classify(normalized.get("text", ""))
        event.processing_status = EventProcessingStatus.ROUTED
        workflow = self.db.scalar(
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.organization_id == event.organization_id,
                WorkflowDefinition.trigger_category == category,
                WorkflowDefinition.is_active.is_(True),
            )
            .order_by(WorkflowDefinition.version.desc())
        )
        if workflow is None:
            workflow = self.db.scalar(
                select(WorkflowDefinition)
                .where(
                    WorkflowDefinition.organization_id.is_(None),
                    WorkflowDefinition.trigger_category == category,
                    WorkflowDefinition.is_active.is_(True),
                )
                .order_by(WorkflowDefinition.version.desc())
            )
        if workflow is None:
            event.processing_status = EventProcessingStatus.FAILED
            event.last_error = f"No active workflow for category={category.value}"
            self.db.commit()
            raise ValueError(event.last_error)

        organization = self.db.get(Organization, event.organization_id)
        if organization is None:
            raise ValueError("Organization not found")
        assert_entitled(self.db, organization, "workflow_executions")

        execution = WorkflowExecution(
            organization_id=event.organization_id,
            workflow_definition_id=workflow.id,
            incoming_event_id=event.id,
            status=WorkflowStatus.RUNNING,
            context={"event": normalized, "category": category.value},
            started_at=datetime.now(UTC),
        )
        self.db.add(execution)
        self.db.flush()
        increment_usage(self.db, event.organization_id, "workflow_executions")
        self._audit(
            event.organization_id,
            execution.id,
            "workflow_selected",
            "system",
            {"workflow": workflow.key, "version": workflow.version},
        )
        self._run_execution(execution)
        self._sync_event_status(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution

    def _sync_event_status(self, execution: WorkflowExecution) -> None:
        event = self.db.get(IncomingEvent, execution.incoming_event_id)
        if event is None:
            return
        event.processing_started_at = None
        if execution.status == WorkflowStatus.COMPLETED:
            event.processing_status = EventProcessingStatus.COMPLETED
            event.completed_at = execution.completed_at or datetime.now(UTC)
            event.last_error = None
        elif execution.status == WorkflowStatus.FAILED:
            event.processing_status = EventProcessingStatus.FAILED
            event.last_error = execution.error
        else:
            event.processing_status = EventProcessingStatus.PROCESSING

    def resume_after_approval(
        self, approval: ApprovalRequest, reviewer_id: uuid.UUID
    ) -> WorkflowExecution:
        execution = self.db.get(WorkflowExecution, approval.workflow_execution_id)
        if execution is None:
            raise ValueError("Workflow execution not found")
        if execution.status != WorkflowStatus.AWAITING_APPROVAL:
            raise ValueError("Execution is not awaiting approval")
        if approval.status not in {
            ApprovalStatus.APPROVED,
            ApprovalStatus.MODIFIED,
            ApprovalStatus.REJECTED,
        }:
            raise ValueError("Approval has not been decided")
        if approval.status not in {
            ApprovalStatus.APPROVED,
            ApprovalStatus.MODIFIED,
        }:
            execution.status = WorkflowStatus.CANCELLED
            execution.completed_at = datetime.now(UTC)
            self._audit(
                approval.organization_id,
                execution.id,
                "approval_rejected",
                "human",
                {"approval_id": str(approval.id), "reviewer_id": str(reviewer_id)},
            )
            self.db.commit()
            return execution

        execution.context = {
            **execution.context,
            "approval": {
                "id": str(approval.id),
                "parameters": approval.modified_parameters or approval.generated_parameters,
            },
        }
        execution.status = WorkflowStatus.RUNNING
        execution.current_step_key = "execute"
        self._audit(
            approval.organization_id,
            execution.id,
            "approval_granted",
            "human",
            {"approval_id": str(approval.id), "reviewer_id": str(reviewer_id)},
        )
        started = time.perf_counter()
        execute_step = StepExecution(
            workflow_execution_id=execution.id,
            step_key="execute",
            step_type=StepType.ACTION_EXECUTE,
            status=StepStatus.RUNNING,
            input_data=execution.context,
            started_at=datetime.now(UTC),
        )
        self.db.add(execute_step)
        self.db.flush()
        try:
            parameters = dict(execution.context["approval"]["parameters"])
            if execution.context.get("event", {}).get("simulate_failure_once"):
                parameters["simulate_failure_once"] = True
            action_result = self._execute_action(execution, parameters)
            execute_step.status = StepStatus.SUCCEEDED
            execute_step.output_data = {"action_executed": True, "action_result": action_result}
            execute_step.completed_at = datetime.now(UTC)
            execute_step.latency_ms = int((time.perf_counter() - started) * 1000)

            approval.final_execution_result = action_result
            action_id = action_result.get("action_id")
            if action_id:
                action_row = self.db.get(ActionExecution, uuid.UUID(action_id))
                if action_row is not None and action_row.workflow_execution_id == execution.id:
                    action_row.approval_request_id = approval.id
            if action_result.get("status") == "queued":
                execute_step.output_data = {
                    "action_executed": False,
                    "action_result": action_result,
                }
                approval.final_execution_result = action_result
                execution.context = {
                    **execution.context,
                    "action_result": action_result,
                    "verified": False,
                }
                execution.status = WorkflowStatus.WAITING_EXTERNAL
                execution.error = None
                self._sync_event_status(execution)
                self.db.commit()
                self.db.refresh(execution)
                return execution
            execution.context = {
                **execution.context,
                "action_result": action_result,
                "verified": True,
            }

            verify_step = StepExecution(
                workflow_execution_id=execution.id,
                step_key="verify",
                step_type=StepType.VERIFICATION,
                status=StepStatus.SUCCEEDED,
                input_data=execution.context,
                output_data={"verified": True, "action_id": action_result.get("action_id")},
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                latency_ms=0,
            )
            self.db.add(verify_step)
            execution.current_step_key = "verify"
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now(UTC)
            self._audit(
                approval.organization_id,
                execution.id,
                "execution_verified",
                "system",
                {"action_id": action_result.get("action_id"), "via_approval": str(approval.id)},
            )
            self.db.commit()
            self.db.refresh(execution)
            return execution
        except Exception as exc:  # noqa: BLE001
            execute_step.status = StepStatus.FAILED
            execute_step.error = str(exc)
            execute_step.completed_at = datetime.now(UTC)
            execute_step.latency_ms = int((time.perf_counter() - started) * 1000)
            execution.status = WorkflowStatus.FAILED
            execution.error = str(exc)
            execution.completed_at = datetime.now(UTC)
            self._audit(
                approval.organization_id,
                execution.id,
                "workflow_failed",
                "system",
                {"step": "execute", "error": str(exc), "via_approval": str(approval.id)},
            )
            self.db.commit()
            self.db.refresh(execution)
            return execution

    def _run_execution(self, execution: WorkflowExecution) -> None:
        workflow = self.db.get(WorkflowDefinition, execution.workflow_definition_id)
        assert workflow is not None
        context = dict(execution.context)

        for step in workflow.steps:
            execution.current_step_key = step.step_key
            started = time.perf_counter()
            step_execution = StepExecution(
                workflow_execution_id=execution.id,
                step_key=step.step_key,
                step_type=step.step_type,
                status=StepStatus.RUNNING,
                input_data=context.copy(),
                started_at=datetime.now(UTC),
            )
            self.db.add(step_execution)
            self.db.flush()

            try:
                result = self._run_step(step.step_type, step.config, context, execution)
                step_execution.status = result.status
                step_execution.output_data = result.output
                step_execution.ai_model_used = result.ai_model
                step_execution.ai_tokens_used = result.ai_tokens
                step_execution.completed_at = datetime.now(UTC)
                step_execution.latency_ms = int((time.perf_counter() - started) * 1000)
                if result.ai_provider and result.ai_model:
                    self.db.add(
                        AIUsageLog(
                            organization_id=execution.organization_id,
                            workflow_execution_id=execution.id,
                            step_execution_id=step_execution.id,
                            provider=result.ai_provider,
                            model=result.ai_model,
                            prompt_tokens=result.ai_prompt_tokens or 0,
                            completion_tokens=result.ai_completion_tokens or 0,
                            cost_usd=result.ai_cost_usd or 0,
                            latency_ms=result.ai_latency_ms or step_execution.latency_ms,
                        )
                    )
                context.update(result.output)

                queued_action = result.output.get("action_result", {})
                if queued_action.get("status") == "queued":
                    execution.context = context
                    execution.status = WorkflowStatus.WAITING_EXTERNAL
                    execution.error = None
                    self._audit(
                        execution.organization_id,
                        execution.id,
                        "action_dispatch_queued",
                        "system",
                        {"action_id": queued_action.get("action_id")},
                    )
                    return

                if result.status == StepStatus.AWAITING_APPROVAL:
                    approval_id = result.output.get("approval_id")
                    if approval_id:
                        approval = self.db.get(ApprovalRequest, uuid.UUID(approval_id))
                        if approval is not None:
                            approval.step_execution_id = step_execution.id
                    execution.context = context
                    execution.status = WorkflowStatus.AWAITING_APPROVAL
                    return
            except Exception as exc:  # noqa: BLE001
                step_execution.status = StepStatus.FAILED
                step_execution.error = str(exc)
                step_execution.completed_at = datetime.now(UTC)
                execution.status = WorkflowStatus.FAILED
                execution.context = context
                execution.completed_at = datetime.now(UTC)
                step_execution.latency_ms = int((time.perf_counter() - started) * 1000)
                execution.error = str(exc)
                self._audit(
                    execution.organization_id,
                    execution.id,
                    "workflow_failed",
                    "system",
                    {"step": step.step_key, "error": str(exc)},
                )
                return

        execution.context = context
        execution.status = WorkflowStatus.COMPLETED
        execution.completed_at = datetime.now(UTC)
        self._audit(
            execution.organization_id, execution.id, "execution_verified", "system", context
        )

    def _run_step(
        self, step_type: StepType, config: dict, context: dict, execution: WorkflowExecution
    ) -> StepResult:
        if step_type == StepType.AI_CLASSIFY:
            text = context.get("event", {}).get("text", "")
            prompt = resolve_prompt(
                self.db,
                key=config.get("prompt_key", "classify_intent"),
                version=config.get("prompt_version"),
            )
            result = get_ai_provider().classify(
                text=text,
                model=config.get("model", get_settings().AI_MODEL or prompt["model"]),
                system_prompt=prompt["system"],
                user_prompt=prompt["user"],
            )
            value = result.value.model_dump()
            category = RequestCategory(value["category"])
            return StepResult(
                StepStatus.SUCCEEDED,
                {
                    "category": category.value,
                    "ai_confidence": value.get("confidence", 0),
                    "ai_rationale": value.get("rationale", ""),
                },
                ai_provider=result.provider,
                ai_model=result.model,
                ai_tokens=result.prompt_tokens + result.completion_tokens,
                ai_prompt_tokens=result.prompt_tokens,
                ai_completion_tokens=result.completion_tokens,
                ai_cost_usd=result.cost_usd,
                ai_latency_ms=result.latency_ms,
            )

        if step_type == StepType.AI_EXTRACT:
            text = context.get("event", {}).get("text", "")
            prompt = resolve_prompt(
                self.db,
                key=config.get("prompt_key", "extract_refund"),
                version=config.get("prompt_version"),
            )
            result = get_ai_provider().extract_refund(
                text=text,
                model=config.get("model", get_settings().AI_MODEL or prompt["model"]),
                system_prompt=prompt["system"],
                user_prompt=prompt["user"],
            )
            extracted = result.value.model_dump(exclude_none=True)
            if context.get("event", {}).get("simulate_failure_once"):
                extracted["simulate_failure_once"] = True
            return StepResult(
                StepStatus.SUCCEEDED,
                {"extracted": extracted},
                ai_provider=result.provider,
                ai_model=result.model,
                ai_tokens=result.prompt_tokens + result.completion_tokens,
                ai_prompt_tokens=result.prompt_tokens,
                ai_completion_tokens=result.completion_tokens,
                ai_cost_usd=result.cost_usd,
                ai_latency_ms=result.latency_ms,
            )

        if step_type == StepType.KNOWLEDGE_LOOKUP:
            category = RequestCategory(context["category"])
            policy = self.db.scalar(
                select(Policy).where(
                    Policy.organization_id == execution.organization_id,
                    Policy.category == category,
                )
            )
            if policy is None:
                raise ValueError(f"No policy configured for {category.value}")
            return StepResult(
                StepStatus.SUCCEEDED,
                {"policy": policy.structured_rules, "policy_title": policy.title},
            )

        if step_type == StepType.BUSINESS_RULE:
            extracted = context.get("extracted", {})
            policy = context.get("policy", {})
            order = self._find_order(execution.organization_id, extracted.get("order_number"))
            if order is None:
                return StepResult(
                    StepStatus.SUCCEEDED,
                    {"rule_result": {"allowed": False, "reason": "order_not_found"}},
                )
            age_days = (datetime.now(UTC) - order.ordered_at).days
            amount = extracted.get("amount_usd")
            allowed = (
                amount is not None
                and Decimal(str(amount)).is_finite()
                and 0 < Decimal(str(amount)) <= (order.amount_usd - order.refunded_amount_usd)
                and Decimal(str(amount)) == Decimal(str(amount)).quantize(Decimal("0.01"))
                and order.status == "completed"
                and 0 <= age_days <= int(policy.get("refund_window_days", 0))
            )
            return StepResult(
                StepStatus.SUCCEEDED,
                {
                    "order": {
                        "id": str(order.id),
                        "order_number": order.order_number,
                        "amount_usd": float(order.amount_usd),
                        "refunded_amount_usd": float(order.refunded_amount_usd),
                        "refundable_amount_usd": float(
                            max(Decimal("0.00"), order.amount_usd - order.refunded_amount_usd)
                        ),
                        "currency": order.currency,
                        "age_days": age_days,
                    },
                    "rule_result": {
                        "allowed": allowed,
                        "reason": "eligible" if allowed else "policy_failed",
                    },
                },
            )

        if step_type == StepType.RISK_ASSESSMENT:
            amount = Decimal(str(context.get("extracted", {}).get("amount_usd", 0)))
            max_auto = Decimal(str(context.get("policy", {}).get("max_auto_refund_usd", 0)))
            allowed = context.get("rule_result", {}).get("allowed", False)
            if not allowed:
                risk = RiskLevel.HIGH
                reasons = [context.get("rule_result", {}).get("reason", "rule_failed")]
            elif amount <= max_auto:
                risk = RiskLevel.LOW
                reasons = []
            else:
                risk = RiskLevel.HIGH
                reasons = ["amount_exceeds_auto_approval_limit"]
            return StepResult(
                StepStatus.SUCCEEDED,
                {"risk_level": risk.value, "risk_factors": reasons},
            )

        if step_type == StepType.APPROVAL_GATE:
            risk = RiskLevel(context.get("risk_level", RiskLevel.HIGH.value))
            if risk == RiskLevel.LOW and context.get("rule_result", {}).get("allowed"):
                return StepResult(StepStatus.SUCCEEDED, {"approval_required": False})
            approval = ApprovalRequest(
                organization_id=execution.organization_id,
                workflow_execution_id=execution.id,
                step_execution_id=None,
                proposed_action={"action_type": config.get("action_type", "refund")},
                reason="Deterministic policy/risk gate requires human review.",
                ai_confidence=float(context.get("ai_confidence", 0)),
                risk_level=risk,
                risk_factors={"factors": context.get("risk_factors", [])},
                source_context=context.get("event", {}),
                generated_parameters={
                    "order_number": context.get("extracted", {}).get("order_number"),
                    "amount_usd": context.get("extracted", {}).get("amount_usd"),
                },
            )
            self.db.add(approval)
            self.db.flush()
            self._audit(
                execution.organization_id,
                execution.id,
                "approval_requested",
                "system",
                {"approval_id": str(approval.id), "risk_level": risk.value},
            )
            return StepResult(
                StepStatus.AWAITING_APPROVAL,
                {"approval_required": True, "approval_id": str(approval.id)},
            )

        if step_type == StepType.ACTION_EXECUTE:
            action_result = self._execute_action(execution, context.get("extracted", {}))
            return StepResult(
                StepStatus.SUCCEEDED, {"action_executed": True, "action_result": action_result}
            )

        if step_type == StepType.VERIFICATION:
            action_id = context.get("action_result", {}).get("action_id")
            action = self.db.get(ActionExecution, uuid.UUID(action_id)) if action_id else None
            if action is None or action.status != ActionStatus.SUCCEEDED:
                raise ValueError("Action was not successfully executed")
            return StepResult(StepStatus.SUCCEEDED, {"verified": True, "action_id": str(action.id)})

        if step_type == StepType.NOTIFICATION:
            from app.models import NotificationLog

            recipient = context.get("event", {}).get("sender") or "demo@acme-demo.example.com"
            message = config.get("message", "Your request has been routed for follow-up.")
            notification = NotificationLog(
                organization_id=execution.organization_id,
                workflow_execution_id=execution.id,
                channel=NotificationChannel.EMAIL,
                recipient=recipient,
                subject=config.get("subject", "Threshold automation update"),
                body=message,
                status="sent",
            )
            self.db.add(notification)
            self.db.flush()
            return StepResult(
                StepStatus.SUCCEEDED,
                {
                    "notification": {
                        "status": "sent",
                        "notification_id": str(notification.id),
                        "recipient": recipient,
                    }
                },
            )

        raise ValueError(f"Unsupported step type: {step_type.value}")

    @staticmethod
    def retry_delay_seconds(attempt: int, base: int = 2, cap: int = 60) -> int:
        """Deterministic exponential backoff: 2^(attempt-1), capped."""
        return retry_delay_seconds(attempt, base, cap)

    def retry_failed_execution(
        self, execution: WorkflowExecution, *, force: bool = False
    ) -> WorkflowExecution:
        """Retry only outcomes known to be safe to retry.

        UNKNOWN provider outcomes are intentionally excluded. They must be
        reconciled first so a transport timeout cannot cause a duplicate refund.
        """
        execution = self.db.scalar(
            select(WorkflowExecution)
            .where(WorkflowExecution.id == execution.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if execution.status != WorkflowStatus.FAILED:
            raise ValueError("Only failed executions can be retried")
        action = self.db.scalar(
            select(ActionExecution)
            .where(ActionExecution.workflow_execution_id == execution.id)
            .order_by(ActionExecution.created_at.desc())
        )
        if action is None:
            raise ValueError("Execution has no retryable action")
        if action.status == ActionStatus.UNKNOWN:
            raise ValueError("Provider outcome is unknown; reconcile before retrying")
        if action.status not in {ActionStatus.FAILED, ActionStatus.RETRYING}:
            raise ValueError("Action is not retryable")
        if action.attempt_count >= action.max_attempts:
            action.status = ActionStatus.DEAD_LETTER
            action.next_retry_at = None
            self._audit(
                execution.organization_id,
                execution.id,
                "action_dead_lettered",
                "system",
                {"action_id": str(action.id), "attempts": action.attempt_count},
            )
            self.db.commit()
            return execution

        now = datetime.now(UTC)
        if not force and action.next_retry_at is not None and action.next_retry_at > now:
            return execution
        integration = self.db.get(IntegrationConfig, action.integration_config_id)
        if integration is None or not integration.is_enabled:
            raise ValueError("Integration is disabled or missing")
        if integration.circuit_open_until and integration.circuit_open_until > now:
            raise RuntimeError("integration_circuit_open")

        action.attempt_count += 1
        action.status = ActionStatus.EXECUTING
        action.error = None
        action.next_retry_at = None
        provider = get_refund_provider(integration)
        result = provider.execute_refund(
            integration,
            order_number=str(action.request_payload["order_number"]),
            amount_usd=Decimal(str(action.request_payload["amount_usd"])),
            idempotency_key=action.idempotency_key,
            external_order_id=action.request_payload.get("external_order_id"),
            payment_reference=action.request_payload.get("payment_reference"),
            payment_gateway=action.request_payload.get("payment_gateway"),
            currency=str(action.request_payload.get("currency") or "USD"),
        )
        self._record_action_attempt(action, integration, result, operation="retry")
        self._apply_provider_result(action, integration, result)

        if action.status == ActionStatus.SUCCEEDED:
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now(UTC)
            execution.error = None
            final = {
                "status": "succeeded",
                "action_id": str(action.id),
                "response": action.response_payload,
            }
            execution.context = {**execution.context, "action_result": final, "verified": True}
            if action.approval_request_id:
                approval = self.db.get(ApprovalRequest, action.approval_request_id)
                if approval is not None:
                    approval.final_execution_result = final
            self._audit(
                execution.organization_id,
                execution.id,
                "action_retried_and_verified",
                "system",
                {"action_id": str(action.id), "attempt": action.attempt_count},
            )
        else:
            execution.status = WorkflowStatus.FAILED
            execution.completed_at = datetime.now(UTC)
            execution.error = action.error or "provider_action_failed"
        self.db.commit()
        self.db.refresh(execution)
        return execution

    def reconcile_action(self, action: ActionExecution) -> ActionExecution:
        """Ask the provider what happened without issuing the side effect again."""
        action = self.db.scalar(
            select(ActionExecution)
            .where(ActionExecution.id == action.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if action is None:
            raise ValueError("Action not found")
        integration = self.db.get(IntegrationConfig, action.integration_config_id)
        if integration is None or not integration.is_enabled:
            raise ValueError("Integration is disabled or missing")
        provider = get_refund_provider(integration)
        provider_operation_id = None
        latest_attempt = self.db.scalar(
            select(ActionAttempt)
            .where(ActionAttempt.action_execution_id == action.id)
            .order_by(ActionAttempt.created_at.desc())
        )
        if latest_attempt is not None:
            provider_operation_id = latest_attempt.provider_operation_id
        result = provider.reconcile_refund(
            integration,
            idempotency_key=action.idempotency_key,
            provider_operation_id=provider_operation_id,
        )
        self._record_action_attempt(action, integration, result, operation="reconcile")
        if result.verified:
            self._apply_provider_result(action, integration, result)
            self._complete_external_action(action)
            self._audit(
                action.organization_id,
                action.workflow_execution_id,
                "action_reconciled",
                "system",
                {"action_id": str(action.id), "verified": True},
            )
        elif result.status == "not_found":
            action.status = ActionStatus.RETRYING
            action.error = "provider_confirmed_not_found"
            action.next_retry_at = datetime.now(UTC)
            enqueue_outbox(
                self.db,
                organization_id=action.organization_id,
                topic="execute_action",
                aggregate_type="action_execution",
                aggregate_id=action.id,
                payload={
                    "action_id": str(action.id),
                    "organization_id": str(action.organization_id),
                },
                available_at=action.next_retry_at,
            )
            self._audit(
                action.organization_id,
                action.workflow_execution_id,
                "action_reconciled",
                "system",
                {"action_id": str(action.id), "verified": False, "safe_to_retry": True},
            )
        else:
            action.status = ActionStatus.UNKNOWN
            action.error = result.error or "provider_outcome_unknown"
        self.db.commit()
        self.db.refresh(action)
        return action

    def _select_refund_integration(self, execution: WorkflowExecution) -> IntegrationConfig:
        organization = self.db.get(Organization, execution.organization_id)
        if organization is None:
            raise ValueError("Organization not found")
        if organization.plan == "demo":
            integration = self.db.scalar(
                select(IntegrationConfig).where(
                    IntegrationConfig.organization_id == execution.organization_id,
                    IntegrationConfig.provider == IntegrationProvider.MOCK_PAYMENTS,
                    IntegrationConfig.is_enabled.is_(True),
                )
            )
            if integration is None:
                integration = IntegrationConfig(
                    organization_id=execution.organization_id,
                    provider=IntegrationProvider.MOCK_PAYMENTS,
                    config={"mode": "demo", "refund_enabled": True},
                    is_enabled=True,
                )
                self.db.add(integration)
                self.db.flush()
            return integration

        candidates = self.db.scalars(
            select(IntegrationConfig).where(
                IntegrationConfig.organization_id == execution.organization_id,
                IntegrationConfig.provider.in_(
                    [
                        IntegrationProvider.STRIPE,
                        IntegrationProvider.SHOPIFY,
                        IntegrationProvider.GENERIC_REST,
                    ]
                ),
                IntegrationConfig.is_enabled.is_(True),
            )
        ).all()
        explicit = [row for row in candidates if bool((row.config or {}).get("refund_enabled"))]
        if len(explicit) > 1:
            raise ValueError("Multiple live refund integrations are marked as execution providers")
        if len(explicit) == 1:
            return explicit[0]
        generic = [row for row in candidates if row.provider == IntegrationProvider.GENERIC_REST]
        if len(candidates) == 1:
            return candidates[0]
        if len(generic) == 1:
            return generic[0]
        raise ValueError("No single live refund execution provider is configured")

    def _record_action_attempt(
        self, action: ActionExecution, integration: IntegrationConfig, result, *, operation: str
    ) -> ActionAttempt:
        attempt = ActionAttempt(
            organization_id=action.organization_id,
            action_execution_id=action.id,
            attempt_number=action.attempt_count,
            operation=operation,
            provider=integration.provider.value,
            provider_operation_id=result.provider_operation_id,
            request_payload=action.request_payload,
            response_payload=result.response,
            outcome=result.status,
            error=result.error,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self.db.add(attempt)
        return attempt

    def _apply_provider_result(
        self, action: ActionExecution, integration: IntegrationConfig, result
    ) -> None:
        action.response_payload = result.response
        if result.verified:
            action.status = ActionStatus.SUCCEEDED
            action.verified_at = datetime.now(UTC)
            action.error = None
            action.next_retry_at = None
            integration.consecutive_failures = 0
            integration.circuit_open_until = None
            return
        integration.consecutive_failures += 1
        if integration.consecutive_failures >= integration.failure_threshold:
            integration.circuit_open_until = datetime.now(UTC) + timedelta(
                seconds=integration.recovery_timeout_seconds
            )
        action.error = result.error or "provider_action_failed"
        if result.unknown:
            action.status = ActionStatus.UNKNOWN
            action.next_retry_at = None
        elif result.retryable and action.attempt_count < action.max_attempts:
            action.status = ActionStatus.RETRYING
            action.next_retry_at = datetime.now(UTC) + timedelta(
                seconds=self.retry_delay_seconds(action.attempt_count)
            )
        elif action.attempt_count >= action.max_attempts:
            action.status = ActionStatus.DEAD_LETTER
            action.next_retry_at = None
        else:
            action.status = ActionStatus.FAILED
            action.next_retry_at = None

    def execute_queued_action(
        self, action_id: uuid.UUID, *, worker_id: str = "celery"
    ) -> ActionExecution:
        """Execute one previously committed action intent.

        The EXECUTING lease is committed before the provider call. If the worker
        crashes after the provider sees the request, recovery changes the stale
        action to UNKNOWN so it must be reconciled instead of blindly retried.
        """
        from app.integrations.providers import ProviderResult

        action = self.db.scalar(
            select(ActionExecution).where(ActionExecution.id == action_id).with_for_update()
        )
        if action is None:
            raise ValueError("Action not found")
        now = datetime.now(UTC)
        if action.status == ActionStatus.SUCCEEDED:
            return action
        if action.status == ActionStatus.EXECUTING:
            # A duplicate at-least-once delivery can arrive while another worker
            # owns the lease. The recovery task handles genuinely stale leases.
            return action
        if action.status == ActionStatus.UNKNOWN:
            raise ValueError("Provider outcome is unknown; reconcile before retrying")
        if action.status in {
            ActionStatus.DEAD_LETTER,
            ActionStatus.FAILED,
            ActionStatus.ROLLED_BACK,
        }:
            raise ValueError(f"Action is not executable from status={action.status.value}")
        if (
            action.status == ActionStatus.RETRYING
            and action.next_retry_at
            and action.next_retry_at > now
        ):
            return action

        integration = self.db.get(IntegrationConfig, action.integration_config_id)
        if integration is None or not integration.is_enabled:
            raise ValueError("Integration is disabled or missing")
        execution = self.db.get(WorkflowExecution, action.workflow_execution_id)
        if execution is None:
            raise ValueError("Workflow execution not found")
        organization = self.db.get(Organization, action.organization_id)
        if organization is None:
            raise ValueError("Organization not found")
        if integration.provider != IntegrationProvider.MOCK_PAYMENTS and not bool(
            (organization.settings or {}).get("live_execution_enabled")
        ):
            action.status = ActionStatus.FAILED
            action.error = "live_execution_disabled"
            action.locked_at = None
            action.locked_by = None
            action.next_retry_at = None
            self._audit(
                action.organization_id,
                action.workflow_execution_id,
                "action_blocked_by_live_execution_kill_switch",
                "system",
                {"action_id": str(action.id), "provider": integration.provider.value},
            )
            self._fail_external_action(action)
            self.db.commit()
            return action
        if integration.circuit_open_until and integration.circuit_open_until > now:
            action.status = ActionStatus.RETRYING
            action.next_retry_at = integration.circuit_open_until
            enqueue_outbox(
                self.db,
                organization_id=action.organization_id,
                topic="execute_action",
                aggregate_type="action_execution",
                aggregate_id=action.id,
                payload={
                    "action_id": str(action.id),
                    "organization_id": str(action.organization_id),
                },
                available_at=action.next_retry_at,
            )
            self.db.commit()
            return action

        action.status = ActionStatus.EXECUTING
        action.attempt_count += 1
        action.next_retry_at = None
        action.locked_at = now
        action.locked_by = worker_id
        attempt = ActionAttempt(
            organization_id=action.organization_id,
            action_execution_id=action.id,
            attempt_number=action.attempt_count,
            operation="execute",
            provider=integration.provider.value,
            provider_operation_id=None,
            request_payload=action.request_payload,
            response_payload=None,
            outcome="in_progress",
            error=None,
            started_at=now,
            completed_at=None,
        )
        self.db.add(attempt)
        self.db.commit()

        try:
            provider = get_refund_provider(integration)
            result = provider.execute_refund(
                integration,
                order_number=str(action.request_payload["order_number"]),
                amount_usd=Decimal(str(action.request_payload["amount_usd"])),
                idempotency_key=action.idempotency_key,
                external_order_id=action.request_payload.get("external_order_id"),
                payment_reference=action.request_payload.get("payment_reference"),
                currency=str(action.request_payload.get("currency") or "USD"),
            )
        except Exception as exc:  # provider/config bugs are known local failures
            result = ProviderResult(
                status="failed",
                response={},
                retryable=False,
                error=f"provider_adapter_error:{exc.__class__.__name__}",
            )

        action = self.db.scalar(
            select(ActionExecution).where(ActionExecution.id == action_id).with_for_update()
        )
        if action is None:
            raise ValueError("Action disappeared after provider execution")
        integration = self.db.get(IntegrationConfig, action.integration_config_id)
        attempt = self.db.get(ActionAttempt, attempt.id)
        if integration is None or attempt is None:
            raise ValueError("Action execution state is incomplete")

        attempt.provider_operation_id = result.provider_operation_id
        attempt.response_payload = result.response
        attempt.outcome = result.status
        attempt.error = result.error
        attempt.completed_at = datetime.now(UTC)
        self._apply_provider_result(action, integration, result)
        action.locked_at = None
        action.locked_by = None
        self._audit(
            action.organization_id,
            action.workflow_execution_id,
            "action_provider_result",
            "system",
            {
                "action_id": str(action.id),
                "provider": integration.provider.value,
                "outcome": result.status,
                "verified": result.verified,
                "attempt": action.attempt_count,
            },
        )

        if action.status == ActionStatus.SUCCEEDED:
            self._complete_external_action(action)
        elif action.status == ActionStatus.RETRYING and action.next_retry_at is not None:
            enqueue_outbox(
                self.db,
                organization_id=action.organization_id,
                topic="execute_action",
                aggregate_type="action_execution",
                aggregate_id=action.id,
                payload={
                    "action_id": str(action.id),
                    "organization_id": str(action.organization_id),
                },
                available_at=action.next_retry_at,
            )
        elif action.status in {ActionStatus.FAILED, ActionStatus.DEAD_LETTER}:
            self._fail_external_action(action)
        self.db.commit()
        self.db.refresh(action)
        return action

    def _complete_external_action(self, action: ActionExecution) -> None:
        execution = self.db.get(WorkflowExecution, action.workflow_execution_id)
        if execution is None:
            return
        final = {
            "status": "succeeded",
            "action_id": str(action.id),
            "response": action.response_payload,
        }
        execution.context = {**execution.context, "action_result": final, "verified": True}
        existing_verify = self.db.scalar(
            select(StepExecution).where(
                StepExecution.workflow_execution_id == execution.id,
                StepExecution.step_key == "verify",
                StepExecution.status == StepStatus.SUCCEEDED,
            )
        )
        if existing_verify is None:
            now = datetime.now(UTC)
            self.db.add(
                StepExecution(
                    workflow_execution_id=execution.id,
                    step_key="verify",
                    step_type=StepType.VERIFICATION,
                    status=StepStatus.SUCCEEDED,
                    input_data=execution.context,
                    output_data={"verified": True, "action_id": str(action.id)},
                    started_at=now,
                    completed_at=now,
                    latency_ms=0,
                )
            )
        execution.current_step_key = "verify"
        execution.status = WorkflowStatus.COMPLETED
        execution.error = None
        execution.completed_at = datetime.now(UTC)
        if action.approval_request_id:
            approval = self.db.get(ApprovalRequest, action.approval_request_id)
            if approval is not None:
                approval.final_execution_result = final
        self._sync_event_status(execution)
        self._audit(
            execution.organization_id,
            execution.id,
            "execution_verified",
            "system",
            {"action_id": str(action.id), "durable_worker": True},
        )

    def _fail_external_action(self, action: ActionExecution) -> None:
        execution = self.db.get(WorkflowExecution, action.workflow_execution_id)
        if execution is None:
            return
        execution.status = WorkflowStatus.FAILED
        execution.error = action.error or "provider_action_failed"
        execution.completed_at = datetime.now(UTC)
        self._sync_event_status(execution)

    def _execute_action(self, execution: WorkflowExecution, parameters: dict) -> dict:
        order_number = parameters.get("order_number")
        amount = parameters.get("amount_usd")
        if not isinstance(order_number, str) or not order_number:
            raise ValueError("Refund requires an order number")
        if isinstance(amount, bool) or not isinstance(amount, (int, float, str)):
            raise ValueError("Refund requires a numeric amount")
        amount_decimal = Decimal(str(amount))
        if (
            not amount_decimal.is_finite()
            or amount_decimal <= 0
            or amount_decimal != amount_decimal.quantize(Decimal("0.01"))
        ):
            raise ValueError("Refund amount must be positive, finite, and in whole cents")
        order = self._find_order(execution.organization_id, order_number)
        refundable = (
            (order.amount_usd - order.refunded_amount_usd) if order is not None else Decimal("0.00")
        )
        if order is None or amount_decimal > refundable:
            raise ValueError(
                "Refund requires an existing order and cannot exceed its remaining refundable amount"
            )
        idem = f"refund:{execution.organization_id}:{order_number}:{amount_decimal:.2f}"
        existing = self.db.scalar(
            select(ActionExecution).where(ActionExecution.idempotency_key == idem)
        )
        if existing:
            if existing.status == ActionStatus.SUCCEEDED:
                return {
                    "status": "already_executed",
                    "action_id": str(existing.id),
                    "response": existing.response_payload,
                }
            if existing.status in {
                ActionStatus.PENDING,
                ActionStatus.RETRYING,
                ActionStatus.EXECUTING,
            }:
                return {"status": "queued", "action_id": str(existing.id), "response": None}
            if existing.status == ActionStatus.UNKNOWN:
                raise ValueError("Existing refund has unknown provider outcome; reconcile it first")
            raise ValueError(f"Existing refund action is not reusable: {existing.status.value}")

        integration = self._select_refund_integration(execution)
        now = datetime.now(UTC)
        if integration.circuit_open_until and integration.circuit_open_until > now:
            raise RuntimeError("integration_circuit_open")
        request_payload = {
            "order_number": order_number,
            "amount_usd": float(amount_decimal),
            "external_order_id": order.external_order_id,
            "payment_reference": order.payment_reference,
            "payment_gateway": order.payment_gateway,
            "currency": order.currency,
            "refundable_amount_usd": float(refundable),
        }

        # Demo keeps the immediate mock path so the portfolio sandbox remains
        # interactive. Live tenants use the durable action-intent/outbox path and
        # require the private-beta live-execution kill switch to be explicitly enabled.
        is_demo_provider = integration.provider == IntegrationProvider.MOCK_PAYMENTS
        organization = self.db.get(Organization, execution.organization_id)
        if organization is None:
            raise ValueError("Organization not found")
        if not is_demo_provider and not bool(
            (organization.settings or {}).get("live_execution_enabled")
        ):
            raise ValueError("live_execution_disabled")
        assert_entitled(self.db, organization, "external_actions")
        action = ActionExecution(
            organization_id=execution.organization_id,
            workflow_execution_id=execution.id,
            approval_request_id=(
                uuid.UUID(execution.context["approval"]["id"])
                if "approval" in execution.context
                else None
            ),
            action_type="refund",
            integration_config_id=integration.id,
            idempotency_key=idem,
            status=ActionStatus.EXECUTING if is_demo_provider else ActionStatus.PENDING,
            attempt_count=1 if is_demo_provider else 0,
            request_payload=request_payload,
            max_attempts=3,
        )
        self.db.add(action)
        self.db.flush()
        increment_usage(self.db, execution.organization_id, "external_actions")

        if not is_demo_provider:
            enqueue_outbox(
                self.db,
                organization_id=execution.organization_id,
                topic="execute_action",
                aggregate_type="action_execution",
                aggregate_id=action.id,
                payload={
                    "action_id": str(action.id),
                    "organization_id": str(execution.organization_id),
                },
            )
            self._audit(
                execution.organization_id,
                execution.id,
                "action_intent_created",
                "system",
                {"action_id": str(action.id), "provider": integration.provider.value},
            )
            return {"status": "queued", "action_id": str(action.id), "response": None}

        # Keep the intentionally failing demo scenario isolated from live providers.
        if parameters.get("simulate_failure_once"):
            from app.integrations.providers import ProviderResult

            result = ProviderResult(
                status="retryable_failure",
                response={},
                retryable=True,
                error="simulated_external_timeout",
            )
        else:
            provider = get_refund_provider(integration)
            result = provider.execute_refund(
                integration,
                order_number=order_number,
                amount_usd=amount_decimal,
                idempotency_key=idem,
                external_order_id=order.external_order_id,
                payment_reference=order.payment_reference,
                payment_gateway=order.payment_gateway,
                currency=order.currency,
            )
        self._record_action_attempt(action, integration, result, operation="execute")
        self._apply_provider_result(action, integration, result)
        self._audit(
            execution.organization_id,
            execution.id,
            "action_provider_result",
            "system",
            {
                "action_id": str(action.id),
                "provider": integration.provider.value,
                "outcome": result.status,
                "verified": result.verified,
            },
        )
        if action.status != ActionStatus.SUCCEEDED:
            if action.status == ActionStatus.UNKNOWN:
                raise RuntimeError("provider_outcome_unknown_reconciliation_required")
            raise RuntimeError(action.error or "provider_action_failed")
        return {
            "status": "succeeded",
            "action_id": str(action.id),
            "response": action.response_payload,
        }

    @staticmethod
    def _normalize(payload: dict) -> dict:
        return normalize_payload(payload)

    @staticmethod
    def _classify(text: str) -> RequestCategory:
        return classify_text(text)

    @staticmethod
    def _extract_refund(text: str) -> dict:
        return extract_refund(text)

    def _find_order(self, organization_id: uuid.UUID, order_number: str | None) -> Order | None:
        if not order_number:
            return None
        return self.db.scalar(
            select(Order).where(
                Order.organization_id == organization_id,
                Order.order_number == order_number,
            )
        )

    def _audit(self, organization_id, execution_id, event_type, actor_type, payload):
        self.db.add(
            AuditLogEntry(
                organization_id=organization_id,
                workflow_execution_id=execution_id,
                event_type=event_type,
                # PostgreSQL now() is fixed for an entire transaction; use the
                # event time so the audit feed preserves intra-workflow order.
                created_at=datetime.now(UTC),
                actor_type=actor_type,
                payload=payload,
            )
        )
