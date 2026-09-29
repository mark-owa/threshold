import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models import BillingAccount, Organization, OrganizationInvitation, OrganizationMember, User
from app.models.enums import MemberRole

router = APIRouter(prefix=f"{get_settings().API_V1_PREFIX}/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=255)
    organization_name: str = Field(min_length=2, max_length=255)
    organization_slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )


class RegisterResponse(TokenResponse):
    organization_id: UUID


class JoinInvitationRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    invitation_token: str = Field(min_length=20, max_length=512)
    full_name: str | None = Field(default=None, min_length=2, max_length=255)


class JoinInvitationResponse(TokenResponse):
    organization_id: UUID
    role: MemberRole


class MeResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str
    memberships: list[dict]


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    try:
        payload = decode_token(credentials.credentials)
        user_id = UUID(str(payload.get("sub")))
        if payload.get("type") != "access":
            raise ValueError("invalid token type")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )
    return user


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    email = request.email.lower()
    slug = request.organization_slug.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        )
    if db.scalar(select(Organization.id).where(Organization.slug == slug)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Workspace slug already exists"
        )

    user = User(
        email=email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name.strip(),
    )
    organization = Organization(
        name=request.organization_name.strip(),
        slug=slug,
        plan="trial",
        settings={"onboarding_completed": False},
    )
    db.add_all([user, organization])
    try:
        db.flush()
        db.add(
            OrganizationMember(
                organization_id=organization.id,
                user_id=user.id,
                role=MemberRole.OWNER,
            )
        )
        db.add(
            BillingAccount(
                organization_id=organization.id,
                subscription_status="trialing",
                trial_ends_at=datetime.now(UTC) + timedelta(days=14),
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account or workspace already exists"
        ) from exc

    return RegisterResponse(
        access_token=create_access_token(str(user.id)),
        organization_id=organization.id,
    )


@router.post("/join", response_model=JoinInvitationResponse)
def join_invited_workspace(request: JoinInvitationRequest, db: Session = Depends(get_db)):
    email = request.email.lower()
    token_hash = hashlib.sha256(request.invitation_token.encode("utf-8")).hexdigest()
    invitation = db.scalar(
        select(OrganizationInvitation).where(OrganizationInvitation.token_hash == token_hash)
    )
    if (
        invitation is None
        or invitation.email.lower() != email
        or invitation.revoked_at is not None
        or invitation.accepted_at is not None
        or invitation.expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation is invalid or expired"
        )

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        if not request.full_name or not request.full_name.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Full name is required for a new account",
            )
        user = User(
            email=email,
            hashed_password=hash_password(request.password),
            full_name=request.full_name.strip(),
        )
        db.add(user)
        db.flush()
    elif not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    existing = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == invitation.organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    if existing is None:
        db.add(
            OrganizationMember(
                organization_id=invitation.organization_id,
                user_id=user.id,
                role=invitation.role,
            )
        )

    invitation.accepted_at = datetime.now(UTC)
    db.commit()
    return JoinInvitationResponse(
        access_token=create_access_token(str(user.id)),
        organization_id=invitation.organization_id,
        role=invitation.role,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == request.email.lower()))
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = db.scalars(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    ).all()
    return MeResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        memberships=[
            {"organization_id": str(m.organization_id), "role": m.role.value} for m in memberships
        ],
    )
