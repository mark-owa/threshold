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
from app.models import (
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
        source = EventSource(source)
        normalized = self._normalize(raw_payload)
        # Serialize this small demo's ingestion per tenant so duplicate deliveries
        # resolve to the committed execution, including simultaneous submissions.
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

        event = IncomingEvent(
            organization_id=organization_id,
            source=source,
            idempotency_key=idempotency_key,
            request_id=request_id,
            raw_payload=raw_payload,
            external_id=normalized.get("external_id"),
            signature_verified=False,
        )
        self.db.add(event)
        self.db.flush()
        self._audit(organization_id, None, "event_received", "system", {"event_id": str(event.id)})

        event.normalized_payload = normalized
        event.processing_status = EventProcessingStatus.NORMALIZED
        self._audit(organization_id, None, "event_normalized", "system", normalized)

        category = self._classify(normalized.get("text", ""))
        event.processing_status = EventProcessingStatus.ROUTED

        workflow = self.db.scalar(
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.organization_id == organization_id,
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
            raise ValueError(f"No active workflow for category={category.value}")

        execution = WorkflowExecution(
            organization_id=organization_id,
            workflow_definition_id=workflow.id,
            incoming_event_id=event.id,
            status=WorkflowStatus.RUNNING,
            context={"event": normalized, "category": category.value},
            started_at=datetime.now(UTC),
        )
        self.db.add(execution)
        self.db.flush()
        self._audit(
            organization_id,
            execution.id,
            "workflow_selected",
            "system",
            {"workflow": workflow.key, "version": workflow.version},
        )

        self._run_execution(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution

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
                and 0 < Decimal(str(amount)) <= order.amount_usd
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
        """Retry a failed action with bounded exponential backoff.

        Automatic retries honor ``next_retry_at``; an authorized operator may
        force a manual retry. Once max attempts are exhausted the action is
        dead-lettered and remains observable for investigation.
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
            return execution

        action.attempt_count += 1
        action.status = ActionStatus.RETRYING
        delay_seconds = self.retry_delay_seconds(action.attempt_count)
        action.next_retry_at = now + timedelta(seconds=delay_seconds)
        self._audit(
            execution.organization_id,
            execution.id,
            "action_retry_scheduled",
            "system",
            {
                "action_id": str(action.id),
                "attempt": action.attempt_count,
                "delay_seconds": delay_seconds,
            },
        )
        try:
            action.status = ActionStatus.EXECUTING
            action.error = None
            retry_started = time.perf_counter()
            retry_step = StepExecution(
                workflow_execution_id=execution.id,
                step_key="execute.retry",
                step_type=StepType.ACTION_EXECUTE,
                status=StepStatus.RUNNING,
                input_data=action.request_payload,
                started_at=datetime.now(UTC),
            )
            self.db.add(retry_step)
            self.db.flush()
            # The demo timeout occurs only on the initial attempt. Retries reuse
            # the original action row; no second refund action is inserted.
            action.status = ActionStatus.SUCCEEDED
            action.next_retry_at = None
            integration.consecutive_failures = 0
            integration.circuit_open_until = None
            action.response_payload = action.response_payload or {
                "provider": "mock_payments",
                "refund_id": f"rf_{uuid.uuid4().hex[:12]}",
            }
            action.verified_at = datetime.now(UTC)
            retry_step.status = StepStatus.SUCCEEDED
            retry_step.output_data = {
                "action_retried": True,
                "action_id": str(action.id),
                "response": action.response_payload,
            }
            retry_step.completed_at = datetime.now(UTC)
            retry_step.latency_ms = int((time.perf_counter() - retry_started) * 1000)
            verify_step = StepExecution(
                workflow_execution_id=execution.id,
                step_key="verify.retry",
                step_type=StepType.VERIFICATION,
                status=StepStatus.SUCCEEDED,
                input_data={"action_id": str(action.id)},
                output_data={"verified": True, "action_id": str(action.id)},
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                latency_ms=0,
            )
            self.db.add(verify_step)
            execution.current_step_key = "verify.retry"
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now(UTC)
            execution.error = None
            result = {
                "status": "succeeded",
                "action_id": str(action.id),
                "response": action.response_payload,
            }
            execution.context = {**execution.context, "action_result": result, "verified": True}
            if action.approval_request_id:
                approval = self.db.get(ApprovalRequest, action.approval_request_id)
                approval.final_execution_result = result
            self._audit(
                execution.organization_id,
                execution.id,
                "action_retried_and_succeeded",
                "system",
                {"action_id": str(action.id), "attempt": action.attempt_count},
            )
        except Exception as exc:  # noqa: BLE001
            if "retry_step" in locals():
                retry_step.status = StepStatus.FAILED
                retry_step.error = str(exc)
                retry_step.completed_at = datetime.now(UTC)
                retry_step.latency_ms = int((time.perf_counter() - retry_started) * 1000)
            if action.attempt_count >= action.max_attempts:
                action.status = ActionStatus.DEAD_LETTER
                action.next_retry_at = None
                self._audit(
                    execution.organization_id,
                    execution.id,
                    "action_dead_lettered",
                    "system",
                    {
                        "action_id": str(action.id),
                        "attempts": action.attempt_count,
                        "error": str(exc),
                    },
                )
            else:
                action.status = ActionStatus.RETRYING
                delay_seconds = self.retry_delay_seconds(action.attempt_count + 1)
                action.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
            action.error = str(exc)
            execution.status = WorkflowStatus.FAILED
            execution.error = str(exc)
            execution.completed_at = datetime.now(UTC)
            self._audit(
                execution.organization_id,
                execution.id,
                "action_retry_failed",
                "system",
                {"action_id": str(action.id), "attempt": action.attempt_count, "error": str(exc)},
            )
        self.db.commit()
        self.db.refresh(execution)
        return execution

    def _execute_action(self, execution: WorkflowExecution, parameters: dict) -> dict:
        order_number = parameters.get("order_number")
        amount = parameters.get("amount_usd")
        if not isinstance(order_number, str) or not order_number:
            raise ValueError("Refund requires an order number")
        if isinstance(amount, bool) or not isinstance(amount, (int, float, str)):
            raise ValueError("Refund requires a numeric amount")
        amount = Decimal(str(amount))
        if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Refund amount must be positive, finite, and in whole cents")
        order = self._find_order(execution.organization_id, order_number)
        if order is None or amount > order.amount_usd:
            raise ValueError("Refund requires an existing order and cannot exceed its total")
        # Canonical cents prevent 65, 65.0 and 65.00 from producing distinct keys.
        idem = f"refund:{execution.organization_id}:{order_number}:{amount:.2f}"
        amount = float(amount)
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
            raise ValueError(f"Existing refund action is not reusable: {existing.status.value}")
        integration = self.db.scalar(
            select(IntegrationConfig).where(
                IntegrationConfig.organization_id == execution.organization_id,
                IntegrationConfig.provider == IntegrationProvider.MOCK_PAYMENTS,
            )
        )
        if integration is None:
            integration = IntegrationConfig(
                organization_id=execution.organization_id,
                provider=IntegrationProvider.MOCK_PAYMENTS,
                config={"mode": "demo"},
                is_enabled=True,
            )
            self.db.add(integration)
            self.db.flush()
        if not integration.is_enabled:
            raise ValueError("Integration is disabled")
        now = datetime.now(UTC)
        if integration.circuit_open_until and integration.circuit_open_until > now:
            raise RuntimeError("integration_circuit_open")
        request_payload = {"order_number": order_number, "amount_usd": amount}
        if parameters.get("simulate_failure_once"):
            request_payload["simulate_failure_once"] = True
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
            status=ActionStatus.EXECUTING,
            attempt_count=1,
            request_payload=request_payload,
            max_attempts=3,
        )
        self.db.add(action)
        self.db.flush()
        if request_payload.get("simulate_failure_once"):
            action.status = ActionStatus.RETRYING
            action.next_retry_at = datetime.now(UTC) + timedelta(
                seconds=self.retry_delay_seconds(1)
            )
            action.error = "simulated_external_timeout"
            integration.consecutive_failures += 1
            if integration.consecutive_failures >= integration.failure_threshold:
                integration.circuit_open_until = datetime.now(UTC) + timedelta(
                    seconds=integration.recovery_timeout_seconds
                )
            self._audit(
                execution.organization_id,
                execution.id,
                "action_failed",
                "system",
                {"action_id": str(action.id), "error": action.error},
            )
            raise RuntimeError(action.error)
        # Demo integration: persist the side effect rather than calling a real PSP.
        integration.consecutive_failures = 0
        integration.circuit_open_until = None
        action.status = ActionStatus.SUCCEEDED
        action.response_payload = {
            "provider": "mock_payments",
            "refund_id": f"rf_{uuid.uuid4().hex[:12]}",
        }
        action.verified_at = datetime.now(UTC)
        result = {
            "status": "succeeded",
            "action_id": str(action.id),
            "response": action.response_payload,
        }
        self._audit(
            execution.organization_id,
            execution.id,
            "action_executed",
            "system",
            {
                "action_id": str(action.id),
                "action_type": "refund",
                "request": action.request_payload,
            },
        )
        return result

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
