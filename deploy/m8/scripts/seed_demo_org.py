"""Seed a demo organization with sample data for local development.

Run with: python -m scripts.seed_demo_org
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    Customer,
    Lead,
    Order,
    Organization,
    OrganizationMember,
    Policy,
    PromptTemplate,
    User,
    WorkflowDefinition,
    WorkflowStep,
)
from app.models.enums import MemberRole, RequestCategory, StepType

DEMO_ORG_SLUG = "acme-demo"


def run() -> None:
    db = SessionLocal()
    try:
        existing = db.query(Organization).filter_by(slug=DEMO_ORG_SLUG).first()
        if existing:
            print(f"Demo org '{DEMO_ORG_SLUG}' already exists ({existing.id}); skipping.")
            return

        org = Organization(name="Acme Retail Co.", slug=DEMO_ORG_SLUG, plan="demo")
        db.add(org)
        db.flush()

        owner = User(
            email="owner@acme-demo.example.com",
            hashed_password=hash_password("demo1234"),
            full_name="Ada Owner",
        )
        reviewer = User(
            email="reviewer@acme-demo.example.com",
            hashed_password=hash_password("demo1234"),
            full_name="Rae Reviewer",
        )
        db.add_all([owner, reviewer])
        db.flush()

        db.add_all(
            [
                OrganizationMember(organization_id=org.id, user_id=owner.id, role=MemberRole.OWNER),
                OrganizationMember(
                    organization_id=org.id, user_id=reviewer.id, role=MemberRole.REVIEWER
                ),
            ]
        )

        customer = Customer(
            organization_id=org.id,
            name="Jordan Rivera",
            email="jordan@example.com",
            tier="standard",
        )
        db.add(customer)
        db.flush()

        db.add_all(
            [
                Order(
                    organization_id=org.id,
                    customer_id=customer.id,
                    order_number="ORD-1001",
                    amount_usd=Decimal("89.99"),
                    status="completed",
                    ordered_at=datetime.now(UTC) - timedelta(days=5),
                ),
                Order(
                    organization_id=org.id,
                    customer_id=customer.id,
                    order_number="ORD-1002",
                    amount_usd=Decimal("65.00"),
                    status="completed",
                    ordered_at=datetime.now(UTC) - timedelta(days=4),
                ),
            ]
        )

        refund_workflow = WorkflowDefinition(
            organization_id=org.id,
            key="refund_request_v1",
            name="Refund Request",
            description=(
                "Classify a refund request, validate policy, gate risk, and execute a mock refund."
            ),
            version=1,
            trigger_category=RequestCategory.REFUND_REQUEST,
        )
        db.add(refund_workflow)
        db.flush()
        db.add_all(
            [
                WorkflowStep(
                    workflow_definition_id=refund_workflow.id,
                    step_key="classify",
                    step_type=StepType.AI_CLASSIFY,
                    order_index=10,
                    config={"prompt_key": "classify_intent"},
                ),
                WorkflowStep(
                    workflow_definition_id=refund_workflow.id,
                    step_key="extract",
                    step_type=StepType.AI_EXTRACT,
                    order_index=20,
                    config={"prompt_key": "extract_refund"},
                ),
                WorkflowStep(
                    workflow_definition_id=refund_workflow.id,
                    step_key="policy",
                    step_type=StepType.KNOWLEDGE_LOOKUP,
                    order_index=30,
                ),
                WorkflowStep(
                    workflow_definition_id=refund_workflow.id,
                    step_key="rules",
                    step_type=StepType.BUSINESS_RULE,
                    order_index=40,
                ),
                WorkflowStep(
                    workflow_definition_id=refund_workflow.id,
                    step_key="risk",
                    step_type=StepType.RISK_ASSESSMENT,
                    order_index=50,
                ),
                WorkflowStep(
                    workflow_definition_id=refund_workflow.id,
                    step_key="approval",
                    step_type=StepType.APPROVAL_GATE,
                    order_index=60,
                    config={"action_type": "refund"},
                ),
                WorkflowStep(
                    workflow_definition_id=refund_workflow.id,
                    step_key="execute",
                    step_type=StepType.ACTION_EXECUTE,
                    order_index=70,
                ),
                WorkflowStep(
                    workflow_definition_id=refund_workflow.id,
                    step_key="verify",
                    step_type=StepType.VERIFICATION,
                    order_index=80,
                ),
            ]
        )

        demo_workflows = [
            (
                RequestCategory.CUSTOMER_INQUIRY,
                "customer_inquiry_v1",
                "Customer Inquiry",
                "Route customer questions to the support queue.",
            ),
            (
                RequestCategory.LEAD_INQUIRY,
                "lead_inquiry_v1",
                "Lead Inquiry",
                "Route qualified prospects to sales.",
            ),
            (
                RequestCategory.SUPPORT_REQUEST,
                "support_request_v1",
                "Support Request",
                "Route support issues to the support team.",
            ),
            (
                RequestCategory.INVOICE_ORDER,
                "invoice_order_v1",
                "Invoice / Order Request",
                "Route invoice and order operations requests.",
            ),
        ]
        for category, key, name, description in demo_workflows:
            workflow = WorkflowDefinition(
                organization_id=org.id,
                key=key,
                name=name,
                description=description,
                version=1,
                trigger_category=category,
            )
            db.add(workflow)
            db.flush()
            db.add_all(
                [
                    WorkflowStep(
                        workflow_definition_id=workflow.id,
                        step_key="classify",
                        step_type=StepType.AI_CLASSIFY,
                        order_index=10,
                        config={"prompt_key": "classify_intent"},
                    ),
                    WorkflowStep(
                        workflow_definition_id=workflow.id,
                        step_key="notify",
                        step_type=StepType.NOTIFICATION,
                        order_index=20,
                        config={
                            "subject": name,
                            "message": (
                                f"Threshold routed a {category.value} request "
                                "to the appropriate team."
                            ),
                        },
                    ),
                ]
            )

        db.add(
            Policy(
                organization_id=org.id,
                category=RequestCategory.REFUND_REQUEST,
                title="Refund Policy",
                content=(
                    "Customers may request a refund within 30 days of purchase for unused "
                    "items. Refunds under $75 are auto-approved if the order qualifies. "
                    "Larger refunds require manual review."
                ),
                structured_rules={"refund_window_days": 30, "max_auto_refund_usd": 75},
            )
        )

        from scripts.seed_prompts import PROMPTS

        for payload in PROMPTS:
            if (
                not db.query(PromptTemplate)
                .filter_by(key=payload["key"], version=payload["version"])
                .first()
            ):
                db.add(PromptTemplate(**payload, is_active=True))

        db.add_all(
            [
                Policy(
                    organization_id=org.id,
                    category=RequestCategory.CUSTOMER_INQUIRY,
                    title="Customer Inquiry Routing",
                    content="Customer questions can be routed to support for human follow-up.",
                    structured_rules={"route": "support"},
                ),
                Policy(
                    organization_id=org.id,
                    category=RequestCategory.LEAD_INQUIRY,
                    title="Lead Routing",
                    content="Interested prospects can be routed to sales.",
                    structured_rules={"route": "sales"},
                ),
                Policy(
                    organization_id=org.id,
                    category=RequestCategory.SUPPORT_REQUEST,
                    title="Support Routing",
                    content="Support issues should be routed to the support team.",
                    structured_rules={"route": "support"},
                ),
                Policy(
                    organization_id=org.id,
                    category=RequestCategory.INVOICE_ORDER,
                    title="Invoice / Order Routing",
                    content="Invoice and order requests should be routed to operations.",
                    structured_rules={"route": "operations"},
                ),
            ]
        )

        db.add(
            Lead(
                organization_id=org.id,
                name="Morgan Lee",
                email="morgan@prospect.com",
                company="Lee Consulting",
                source="website_form",
                status="new",
            )
        )

        db.commit()
        print(f"Seeded demo organization '{org.slug}' ({org.id})")
        print("  owner:    owner@acme-demo.example.com    / demo1234")
        print("  reviewer: reviewer@acme-demo.example.com  / demo1234")
    finally:
        db.close()


if __name__ == "__main__":
    run()
