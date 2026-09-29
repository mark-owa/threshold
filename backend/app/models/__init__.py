"""Import every model module here so that a single
`import app.models` registers all tables on Base.metadata -- this is
what Alembic's env.py relies on for autogenerate to see the full schema.
"""

from app.db.base_class import Base
from app.models.action import ActionAttempt, ActionExecution, IntegrationConfig
from app.models.ai import AIUsageLog, PromptTemplate
from app.models.approval import ApprovalRequest
from app.models.billing import BillingAccount, UsageCounter
from app.models.audit import AuditLogEntry
from app.models.delivery import OutboxMessage, WebhookEndpoint
from app.models.domain import Customer, Lead, NotificationLog, Order, Policy
from app.models.event import IncomingEvent
from app.models.security import ExternalWebhookReceipt, OAuthStateNonce
from app.models.organization import (
    APIKey,
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    User,
)
from app.models.workflow import StepExecution, WorkflowDefinition, WorkflowExecution, WorkflowStep

__all__ = [
    "Base",
    "Organization",
    "User",
    "OrganizationMember",
    "OrganizationInvitation",
    "APIKey",
    "IncomingEvent",
    "WorkflowDefinition",
    "WorkflowStep",
    "WorkflowExecution",
    "StepExecution",
    "ApprovalRequest",
    "BillingAccount",
    "UsageCounter",
    "IntegrationConfig",
    "ActionExecution",
    "ActionAttempt",
    "OutboxMessage",
    "WebhookEndpoint",
    "AuditLogEntry",
    "PromptTemplate",
    "AIUsageLog",
    "Customer",
    "Order",
    "Policy",
    "Lead",
    "NotificationLog",
    "ExternalWebhookReceipt",
    "OAuthStateNonce",
]
