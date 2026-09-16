"""Import every model module here so that a single
`import app.models` registers all tables on Base.metadata -- this is
what Alembic's env.py relies on for autogenerate to see the full schema.
"""

from app.db.base_class import Base
from app.models.action import ActionExecution, IntegrationConfig
from app.models.ai import AIUsageLog, PromptTemplate
from app.models.approval import ApprovalRequest
from app.models.audit import AuditLogEntry
from app.models.domain import Customer, Lead, NotificationLog, Order, Policy
from app.models.event import IncomingEvent
from app.models.organization import APIKey, Organization, OrganizationMember, User
from app.models.workflow import StepExecution, WorkflowDefinition, WorkflowExecution, WorkflowStep

__all__ = [
    "Base",
    "Organization",
    "User",
    "OrganizationMember",
    "APIKey",
    "IncomingEvent",
    "WorkflowDefinition",
    "WorkflowStep",
    "WorkflowExecution",
    "StepExecution",
    "ApprovalRequest",
    "IntegrationConfig",
    "ActionExecution",
    "AuditLogEntry",
    "PromptTemplate",
    "AIUsageLog",
    "Customer",
    "Order",
    "Policy",
    "Lead",
    "NotificationLog",
]
