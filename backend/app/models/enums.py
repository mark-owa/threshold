"""Enums shared by ORM models, business logic, and (later) API schemas.

Using `enum.StrEnum` (Python 3.11+) rather than the older `class X(str, Enum)`
mixin pattern -- it's the current standard-library way to get "acts like a
string, is still a real enum" and needs no extra base classes.
"""

from enum import StrEnum


class MemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class EventSource(StrEnum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    API = "api"
    FORM = "form"


class EventProcessingStatus(StrEnum):
    RECEIVED = "received"
    NORMALIZED = "normalized"
    ROUTED = "routed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class RequestCategory(StrEnum):
    CUSTOMER_INQUIRY = "customer_inquiry"
    REFUND_REQUEST = "refund_request"
    LEAD_INQUIRY = "lead_inquiry"
    SUPPORT_REQUEST = "support_request"
    INVOICE_ORDER = "invoice_order"
    UNCLASSIFIED = "unclassified"


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(StrEnum):
    AI_CLASSIFY = "ai_classify"
    AI_EXTRACT = "ai_extract"
    KNOWLEDGE_LOOKUP = "knowledge_lookup"
    BUSINESS_RULE = "business_rule"
    RISK_ASSESSMENT = "risk_assessment"
    APPROVAL_GATE = "approval_gate"
    ACTION_EXECUTE = "action_execute"
    VERIFICATION = "verification"
    NOTIFICATION = "notification"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class ActionStatus(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"
    ROLLED_BACK = "rolled_back"


class IntegrationProvider(StrEnum):
    MOCK_EMAIL = "mock_email"
    MOCK_CRM = "mock_crm"
    MOCK_SLACK = "mock_slack"
    MOCK_PAYMENTS = "mock_payments"
    GENERIC_REST = "generic_rest"


class AIProvider(StrEnum):
    MOCK = "mock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class NotificationChannel(StrEnum):
    EMAIL = "email"
    SLACK = "slack"
