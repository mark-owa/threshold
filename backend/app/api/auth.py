from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, decode_token, verify_password
from app.db.session import get_db
from app.models import OrganizationMember, User

router = APIRouter(prefix=f"{get_settings().API_V1_PREFIX}/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == request.email))
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
