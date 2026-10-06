from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.company import Company
from app.models.runtime import BackgroundJob, CompanyAccess
from app.models.user import User
from app.runtime.health import dependency_status
from app.runtime.security import Principal, authorize_request, require_permission, security_event

router = APIRouter(prefix="/admin/runtime", tags=["Runtime administration"])


@router.get("/security")
def security_status(request: Request, principal: Principal = Depends(authorize_request)):
    require_permission(principal, "ADMIN_RUNTIME")
    settings = request.app.state.settings
    return {
        "authentication_required": True,
        "authentication_configured": settings.auth_signing_key is not None,
        "authorization_policy": "authorization_policy_v1",
        "company_access_enforced": True,
        "shared_rate_limits": settings.rate_limit_backend == "redis",
        "development_providers_blocked": settings.controlled_environment,
        "debug_enabled": settings.debug,
        "analytics_status": "NON_PRODUCTION_ANALYTICS",
        "production_stock_prediction": False,
        "autonomous_credit_approval": False,
        "automated_trading": False,
    }


@router.get("")
def runtime(request: Request, principal: Principal = Depends(authorize_request)):
    require_permission(principal, "ADMIN_RUNTIME")
    settings = request.app.state.settings
    return {
        "environment": settings.app_env.value,
        "dependencies": dependency_status(settings),
        "queue_backend": settings.queue_backend,
        "rate_limit_backend": settings.rate_limit_backend,
        "analytics_status": "NON_PRODUCTION_ANALYTICS",
        "production_prediction_enabled": False,
    }


@router.get("/jobs")
def summary(principal: Principal = Depends(authorize_request), session: Session = Depends(get_db)):
    require_permission(principal, "ADMIN_RUNTIME")
    return {
        status: count
        for status, count in session.execute(
            select(BackgroundJob.status, func.count()).group_by(BackgroundJob.status)
        )
    }


class AccountState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ACTIVE", "DISABLED", "LOCKED", "PENDING"]


@router.post("/users/{user_id}/state")
def account_state(
    user_id: UUID,
    body: AccountState,
    request: Request,
    principal: Principal = Depends(authorize_request),
    session: Session = Depends(get_db),
):
    require_permission(principal, "ADMIN_RUNTIME")
    user = session.get(User, user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found", 404)
    user.account_status = body.status
    user.is_active = body.status == "ACTIVE"
    user.token_version += 1
    security_event(
        session, "ADMIN_ACCOUNT_STATE_CHANGED", request.state.request_id, principal.user_id
    )
    return {"user_id": user.id, "status": user.account_status}


class AccessGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: UUID
    granted: bool


@router.post("/users/{user_id}/companies")
def company_access(
    user_id: UUID,
    body: AccessGrant,
    request: Request,
    principal: Principal = Depends(authorize_request),
    session: Session = Depends(get_db),
):
    require_permission(principal, "ADMIN_RUNTIME")
    user = session.get(User, user_id, with_for_update=True)
    if user is None or session.get(Company, body.company_id) is None:
        raise AppError("NOT_FOUND", "User or company not found", 404)
    grant = session.scalar(
        select(CompanyAccess).where(
            CompanyAccess.user_id == user_id, CompanyAccess.company_id == body.company_id
        )
    )
    if body.granted and grant is None:
        session.add(CompanyAccess(user_id=user_id, company_id=body.company_id))
    elif not body.granted and grant is not None:
        session.delete(grant)
    security_event(
        session, "ADMIN_COMPANY_ACCESS_CHANGED", request.state.request_id, principal.user_id
    )
    return {"user_id": user_id, "company_id": body.company_id, "granted": body.granted}
