"""Authentication endpoints. Credentials never appear in response models or logs."""

from uuid import UUID

from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.user import User
from app.runtime.rate_limit import check_rate
from app.runtime.security import (
    PASSWORDS,
    Principal,
    authorize_request,
    get_security_db,
    issue_token,
    security_event,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
# Use the same password algorithm even when the account does not exist.
_DUMMY_HASH = PASSWORDS.hash("unused-login-timing-placeholder")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class IdentityResponse(BaseModel):
    user_id: UUID
    role: str
    permissions: list[str]
    company_ids: list[UUID]
    environment: str
    analytics_status: str = "NON_PRODUCTION_ANALYTICS"


@router.post("/token", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    session: Session | None = Depends(get_security_db),
) -> TokenResponse:
    settings = request.app.state.settings
    request_id = getattr(request.state, "request_id", "unknown")
    # Do not trust a client-supplied forwarding header for rate-limit identity.
    client = request.client.host if request.client else "unknown"
    try:
        check_rate(settings, request.app.state.rate_limits, client, "login")
    except AppError:
        security_event(session, "RATE_LIMIT_TRIGGERED", request_id)
        raise
    if session is None:
        raise AppError("DEPENDENCY_UNAVAILABLE", "Authentication unavailable", 503)
    user = session.scalar(select(User).where(User.email == body.email.strip().lower()))
    valid = False
    try:
        valid = PASSWORDS.verify(
            user.password_hash if user and user.password_hash else _DUMMY_HASH,
            body.password.get_secret_value(),
        )
    except VerificationError:
        pass
    if not user or not user.password_hash or not valid:
        security_event(session, "AUTHENTICATION_FAILED", request_id)
        raise AppError("AUTHENTICATION_REQUIRED", "Invalid credentials", 401)
    if not user.is_active or user.account_status != "ACTIVE":
        security_event(session, "USER_DISABLED_ACCESS_ATTEMPT", request_id, user.id)
        raise AppError("AUTHENTICATION_REQUIRED", "Invalid credentials", 401)
    if PASSWORDS.check_needs_rehash(user.password_hash):
        user.password_hash = PASSWORDS.hash(body.password.get_secret_value())
    token = issue_token(user, settings)
    security_event(session, "AUTHENTICATION_SUCCEEDED", request_id, user.id)
    return TokenResponse(access_token=token, expires_in=settings.access_token_minutes * 60)


@router.get("/me", response_model=IdentityResponse)
def identity(
    request: Request, principal: Principal = Depends(authorize_request)
) -> IdentityResponse:
    return IdentityResponse(
        user_id=principal.user_id,
        role=principal.role,
        permissions=sorted(principal.permissions),
        company_ids=sorted(principal.companies, key=str),
        environment=request.app.state.settings.app_env.value,
    )
