"""Shared tenant authorization helpers.

The browser may name a workspace, but it never grants access to it. Every
request resolves the authenticated user's membership against the database
before tenant-owned data is read or mutated.
"""

from collections.abc import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization, OrganizationMember
from app.models.enums import MemberRole


def get_org_membership(org_id: UUID, user_id: UUID, db: Session) -> OrganizationMember:
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this organization",
        )
    return membership


def require_org_roles(
    org_id: UUID,
    user_id: UUID,
    db: Session,
    allowed_roles: Iterable[MemberRole],
    *,
    detail: str = "Insufficient organization permission",
) -> OrganizationMember:
    membership = get_org_membership(org_id, user_id, db)
    allowed = set(allowed_roles)
    if membership.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return membership


def get_active_organization(org_id: UUID, user_id: UUID, db: Session) -> Organization:
    get_org_membership(org_id, user_id, db)
    organization = db.scalar(
        select(Organization).where(
            Organization.id == org_id,
            Organization.is_active.is_(True),
        )
    )
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


def require_demo_organization(org_id: UUID, user_id: UUID, db: Session) -> Organization:
    organization = get_active_organization(org_id, user_id, db)
    if organization.plan != "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo scenarios are only available inside demo workspaces",
        )
    return organization
