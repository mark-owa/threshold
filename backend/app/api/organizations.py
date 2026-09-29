import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.tenancy import get_active_organization, get_org_membership, require_org_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    AuditLogEntry,
    BillingAccount,
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    User,
)
from app.models.enums import MemberRole

router = APIRouter(prefix=f"{get_settings().API_V1_PREFIX}/organizations", tags=["organizations"])
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    role: MemberRole
    is_active: bool


class InvitationRequest(BaseModel):
    email: EmailStr
    role: MemberRole = MemberRole.REVIEWER


class UpdateMemberRoleRequest(BaseModel):
    role: MemberRole


def normalize_slug(value: str) -> str:
    slug = value.strip().lower()
    if not SLUG_RE.fullmatch(slug):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Slug must contain lowercase letters, numbers, and single hyphens only",
        )
    return slug


def _member_row(org_id: UUID, membership_id: UUID, db: Session) -> OrganizationMember:
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.id == membership_id,
            OrganizationMember.organization_id == org_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return membership


def _assert_role_change_allowed(
    actor: OrganizationMember,
    target: OrganizationMember,
    new_role: MemberRole,
    db: Session,
) -> None:
    if actor.role == MemberRole.ADMIN:
        if target.role in {MemberRole.OWNER, MemberRole.ADMIN} or new_role in {
            MemberRole.OWNER,
            MemberRole.ADMIN,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an owner can manage owner or admin roles",
            )
    if target.role == MemberRole.OWNER and new_role != MemberRole.OWNER:
        owner_count = db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == target.organization_id,
                OrganizationMember.role == MemberRole.OWNER,
            )
        ) or 0
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A workspace must always have at least one owner",
            )


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == user.id,
            Organization.is_active.is_(True),
        )
        .order_by(Organization.name.asc())
    ).all()
    return [
        OrganizationResponse(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            plan=organization.plan,
            role=membership.role,
            is_active=organization.is_active,
        )
        for organization, membership in rows
    ]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    request: CreateOrganizationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    slug = normalize_slug(request.slug)
    existing = db.scalar(select(Organization.id).where(Organization.slug == slug))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace slug already exists")

    organization = Organization(
        name=request.name.strip(),
        slug=slug,
        plan="trial",
        settings={"onboarding_completed": False},
    )
    db.add(organization)
    db.flush()
    membership = OrganizationMember(
        organization_id=organization.id,
        user_id=user.id,
        role=MemberRole.OWNER,
    )
    db.add(membership)
    db.add(
        BillingAccount(
            organization_id=organization.id,
            subscription_status="trialing",
            trial_ends_at=datetime.now(UTC) + timedelta(days=14),
        )
    )
    db.commit()
    db.refresh(organization)
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        plan=organization.plan,
        role=membership.role,
        is_active=organization.is_active,
    )


@router.get("/{org_id}", response_model=OrganizationResponse)
def get_organization(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    organization = get_active_organization(org_id, user.id, db)
    membership = get_org_membership(org_id, user.id, db)
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        plan=organization.plan,
        role=membership.role,
        is_active=organization.is_active,
    )


@router.get("/{org_id}/members")
def list_members(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_org_membership(org_id, user.id, db)
    rows = db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == org_id)
        .order_by(User.full_name.asc())
    ).all()
    return [
        {
            "membership_id": str(membership.id),
            "user_id": str(member.id),
            "email": member.email,
            "full_name": member.full_name,
            "role": membership.role.value,
        }
        for membership, member in rows
    ]


@router.get("/{org_id}/invitations")
def list_invitations(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required",
    )
    now = datetime.now(UTC)
    rows = db.scalars(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.organization_id == org_id)
        .order_by(OrganizationInvitation.created_at.desc())
    ).all()
    return [
        {
            "id": str(invite.id),
            "email": invite.email,
            "role": invite.role.value,
            "status": (
                "accepted"
                if invite.accepted_at
                else "revoked"
                if invite.revoked_at
                else "expired"
                if invite.expires_at <= now
                else "pending"
            ),
            "expires_at": invite.expires_at,
            "accepted_at": invite.accepted_at,
        }
        for invite in rows
    ]


@router.post("/{org_id}/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(
    org_id: UUID,
    request: InvitationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    actor = require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required",
    )
    if request.role == MemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Owner access must be granted by changing an existing member's role",
        )
    if actor.role == MemberRole.ADMIN and request.role == MemberRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner can invite another admin",
        )

    email = request.email.lower()
    existing_member = db.scalar(
        select(OrganizationMember.id)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == org_id, User.email == email)
    )
    if existing_member is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(days=7)
    invitation = db.scalar(
        select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == org_id,
            OrganizationInvitation.email == email,
        )
    )
    if invitation is None:
        invitation = OrganizationInvitation(
            organization_id=org_id,
            email=email,
            role=request.role,
            token_hash=token_hash,
            invited_by_id=user.id,
            expires_at=expires_at,
        )
        db.add(invitation)
    else:
        invitation.role = request.role
        invitation.token_hash = token_hash
        invitation.invited_by_id = user.id
        invitation.expires_at = expires_at
        invitation.accepted_at = None
        invitation.revoked_at = None

    db.add(
        AuditLogEntry(
            organization_id=org_id,
            workflow_execution_id=None,
            event_type="team.invitation_created",
            actor_type="human",
            actor_id=str(user.id),
            payload={"email": email, "role": request.role.value},
        )
    )
    db.commit()
    db.refresh(invitation)
    return {
        "id": str(invitation.id),
        "email": invitation.email,
        "role": invitation.role.value,
        "expires_at": invitation.expires_at,
        "invitation_token": raw_token,
        "delivery": "manual",
    }


@router.delete("/{org_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    org_id: UUID,
    invitation_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required",
    )
    invitation = db.scalar(
        select(OrganizationInvitation).where(
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == org_id,
        )
    )
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation is already accepted")
    invitation.revoked_at = datetime.now(UTC)
    db.add(
        AuditLogEntry(
            organization_id=org_id,
            workflow_execution_id=None,
            event_type="team.invitation_revoked",
            actor_type="human",
            actor_id=str(user.id),
            payload={"email": invitation.email},
        )
    )
    db.commit()


@router.patch("/{org_id}/members/{membership_id}")
def update_member_role(
    org_id: UUID,
    membership_id: UUID,
    request: UpdateMemberRoleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    actor = require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required",
    )
    target = _member_row(org_id, membership_id, db)
    previous_role = target.role
    _assert_role_change_allowed(actor, target, request.role, db)
    target.role = request.role
    db.add(
        AuditLogEntry(
            organization_id=org_id,
            workflow_execution_id=None,
            event_type="team.role_changed",
            actor_type="human",
            actor_id=str(user.id),
            payload={
                "membership_id": str(target.id),
                "user_id": str(target.user_id),
                "from": previous_role.value,
                "to": request.role.value,
            },
        )
    )
    db.commit()
    return {"membership_id": str(target.id), "role": target.role.value}


@router.delete("/{org_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    org_id: UUID,
    membership_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    actor = require_org_roles(
        org_id,
        user.id,
        db,
        {MemberRole.OWNER, MemberRole.ADMIN},
        detail="Admin permission required",
    )
    target = _member_row(org_id, membership_id, db)
    if actor.role == MemberRole.ADMIN and target.role in {MemberRole.OWNER, MemberRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner can remove an owner or admin",
        )
    if target.role == MemberRole.OWNER:
        owner_count = db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.role == MemberRole.OWNER,
            )
        ) or 0
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A workspace must always have at least one owner",
            )
    if target.user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Use a dedicated leave-workspace flow to remove your own membership",
        )

    removed_user_id = target.user_id
    removed_role = target.role.value
    db.delete(target)
    db.add(
        AuditLogEntry(
            organization_id=org_id,
            workflow_execution_id=None,
            event_type="team.member_removed",
            actor_type="human",
            actor_id=str(user.id),
            payload={"user_id": str(removed_user_id), "role": removed_role},
        )
    )
    db.commit()
