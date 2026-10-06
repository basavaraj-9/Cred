from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import literal, select, union_all
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.database.base import Base
from app.database.repositories.audit_log import write_audit_log
from app.database.session import get_db
from app.models.company import Company
from app.models.runtime import CompanyAccess
from app.models.user import User
from app.runtime.observability import context
from app.runtime.rate_limit import check_rate

POLICY = json.loads((Path(__file__).parent / "authorization_policy_v1.json").read_text())
PASSWORDS = PasswordHasher()
BEARER = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    role: str
    companies: frozenset[UUID]

    @property
    def permissions(self) -> frozenset[str]:
        return frozenset(POLICY["roles"].get(self.role, []))

    def company(self, company_id: UUID) -> None:
        if self.role != "ADMIN" and company_id not in self.companies:
            raise AppError("AUTHORIZATION_DENIED", "Access denied", 403)


def issue_token(user: User, settings: Settings) -> str:
    if not settings.auth_signing_key:
        raise AppError("DEPENDENCY_UNAVAILABLE", "Authentication is not configured", 503)
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.reviewer_role,
            "ver": user.token_version,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
            "jti": str(uuid4()),
            "iss": settings.auth_issuer,
            "aud": settings.auth_audience,
        },
        settings.auth_signing_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    if not settings.auth_signing_key:
        raise AppError("AUTHENTICATION_REQUIRED", "Authentication required", 401)
    try:
        return jwt.decode(
            token,
            settings.auth_signing_key.get_secret_value(),
            algorithms=["HS256"],
            audience=settings.auth_audience,
            issuer=settings.auth_issuer,
            options={"require": ["sub", "exp", "iat", "nbf", "jti", "ver", "role", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise AppError("AUTHENTICATION_REQUIRED", "Invalid or expired access token", 401) from exc


def security_event(
    session: Session | None, event: str, request_id: str, user_id: UUID | None = None
) -> None:
    if session is None:
        return
    write_audit_log(
        session,
        entity_type="runtime_security",
        entity_id=uuid4(),
        action=event,
        event_type=event,
        user_id=user_id,
        metadata_json={"request_id": request_id, "authorization_policy": POLICY["version"]},
    )
    session.commit()


def permission_for(path: str, method: str) -> str:
    read = method in {"GET", "HEAD"}
    if "/admin/" in path or path.endswith("/metrics"):
        return "ADMIN_RUNTIME"
    if "/jobs" in path or "/auth/me" in path:
        return "AUTHENTICATED"
    if "/stock" in path or "/peer" in path or "/listed" in path:
        if "monitoring" in path and read:
            return "MONITORING_READ"
        return "STOCK_RESEARCH_READ" if read else "STOCK_RESEARCH_BUILD"
    if "report" in path:
        return (
            "REPORT_READ"
            if read
            else "REPORT_FINALIZE"
            if any(x in path for x in ("finalize", "supersede"))
            else "REPORT_GENERATE"
        )
    if any(x in path for x in ("credit-review", "credit-committee", "review-cases")):
        return (
            "CREDIT_REVIEW"
            if read or not any(x in path for x in ("decision", "override", "approve", "committee"))
            else "CREDIT_DECIDE"
        )
    if "/documents/upload" in path:
        return "DOCUMENT_UPLOAD"
    if "/documents" in path or "/analysis/" in path or "/company-profiles" in path:
        return "DOCUMENT_READ" if read else "CREDIT_ANALYZE"
    if any(
        x in path
        for x in (
            "/credit",
            "/financial",
            "/five-cs",
            "/rag",
            "/analyst",
            "/research",
            "/domain",
            "/companies",
        )
    ):
        return "COMPANY_READ" if read else "CREDIT_ANALYZE"
    if path.endswith(("/status", "/health")):
        return "COMPANY_READ"
    # New, unclassified routes are restricted until explicitly reviewed.
    return "ADMIN_RUNTIME"


def require_permission(principal: Principal, permission: str) -> None:
    if permission != "AUTHENTICATED" and permission not in principal.permissions:
        raise AppError("AUTHORIZATION_DENIED", "Permission denied", 403)


def check_resource(session: Session, principal: Principal, reference: UUID) -> None:
    """Central company-access hook, including child objects addressed by opaque IDs."""
    if principal.role == "ADMIN":
        return
    mappers = {
        mapper.class_.__tablename__: mapper.class_
        for mapper in Base.registry.mappers
        if hasattr(mapper.class_, "id")
    }
    query = union_all(
        *(
            select(literal(name).label("kind")).where(model.id == reference)
            for name, model in mappers.items()
        )
    )
    names = list(session.scalars(query))
    if not names:
        raise AppError("NOT_FOUND", "Resource not found", 404)
    visited: set[tuple[str, UUID]] = set()

    def inspect_resource(name: str, resource_id: UUID, depth: int = 0) -> None:
        if depth > 8:
            raise AppError("AUTHORIZATION_DENIED", "Resource lineage exceeds access bounds", 403)
        if (name, resource_id) in visited:
            return
        visited.add((name, resource_id))
        model = mappers[name]
        row = session.get(model, resource_id)
        if row is None:
            return
        company_id = row.id if model is Company else getattr(row, "company_id", None)
        if company_id:
            principal.company(company_id)
        owner = (
            getattr(row, "user_id", None)
            if name.startswith("analyst_chat")
            else getattr(row, "created_by", None)
            if name == "background_jobs"
            else None
        )
        if owner and owner != principal.user_id:
            raise AppError("AUTHORIZATION_DENIED", "Access denied", 403)
        if company_id:
            return
        for column in model.__table__.columns:
            if column.name in {
                "user_id",
                "created_by",
                "created_by_user_id",
                "generated_by_user_id",
                "model_id",
                "dataset_id",
            }:
                continue
            value = getattr(row, column.name)
            for foreign in column.foreign_keys:
                target = foreign.column.table.name
                if value and target in mappers and target != "users":
                    inspect_resource(target, value, depth + 1)

    for name in names:
        inspect_resource(name, reference)


def references(value: Any, key: str = "", depth: int = 0) -> list[tuple[str, UUID]]:
    if depth > 20:
        raise AppError("VALIDATION_ERROR", "Request nesting exceeds allowed bounds", 422)
    result = []
    if isinstance(value, dict):
        for name, item in value.items():
            result.extend(references(item, name, depth + 1))
    elif isinstance(value, list):
        if len(value) > 100:
            raise AppError("VALIDATION_ERROR", "Too many input references", 422)
        for item in value:
            result.extend(references(item, key, depth + 1))
    elif isinstance(value, (str, UUID)) and (
        key.endswith(("_id", "_ids")) or key in {"company", "id"}
    ):
        try:
            result.append((key, UUID(str(value))))
        except ValueError:
            pass  # Typed endpoint validation handles malformed UUIDs.
    return result


def get_security_db(request: Request) -> Generator[Session | None, None, None]:
    if not request.app.state.settings.database_url:
        yield None
        return
    yield from get_db(request)


async def authorize_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(BEARER),
    session: Session | None = Depends(get_security_db),
) -> Principal:
    settings = request.app.state.settings
    principal: Principal | None = None
    request_id = getattr(request.state, "request_id", str(uuid4()))
    try:
        check_rate(
            settings,
            request.app.state.rate_limits,
            "ip:" + (request.client.host if request.client else "unknown"),
            "normal",
        )
        if not credentials:
            raise AppError("AUTHENTICATION_REQUIRED", "Authentication required", 401)
        claims = decode_token(credentials.credentials, settings)
        try:
            user_id = UUID(claims["sub"])
        except (ValueError, TypeError) as exc:
            raise AppError("AUTHENTICATION_REQUIRED", "Invalid access token", 401) from exc
        if session is None:
            raise AppError("DEPENDENCY_UNAVAILABLE", "Authentication store unavailable", 503)
        user = session.get(User, user_id)
        if not user or claims["ver"] != user.token_version or claims["role"] != user.reviewer_role:
            raise AppError("AUTHENTICATION_REQUIRED", "Invalid access token", 401)
        if not user.is_active or user.account_status != "ACTIVE":
            security_event(session, "USER_DISABLED_ACCESS_ATTEMPT", request_id, user.id)
            raise AppError("AUTHENTICATION_REQUIRED", "Account unavailable", 401)
        principal = Principal(
            user.id,
            user.reviewer_role,
            frozenset(
                session.scalars(
                    select(CompanyAccess.company_id).where(CompanyAccess.user_id == user.id)
                )
            ),
        )
        require_permission(principal, permission_for(request.url.path, request.method))
        if len(request.query_params) > 100 or any(
            len(value) > 2000 for _, value in request.query_params.multi_items()
        ):
            raise AppError("VALIDATION_ERROR", "Query exceeds allowed bounds", 422)
        data: dict[str, Any] = {**dict(request.query_params), **request.path_params}
        resource_inputs: list[Any] = [dict(request.query_params), request.path_params]
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                body = await request.json()
            except (ValueError, UnicodeError) as exc:
                raise AppError("VALIDATION_ERROR", "Malformed JSON", 422) from exc
            if isinstance(body, dict):
                data.update(body)
            resource_inputs.append(body)
        for key, value in references(resource_inputs):
            if key in {"actor_user_id", "actor_id"}:
                if value != principal.user_id:
                    raise AppError(
                        "AUTHORIZATION_DENIED", "Actor does not match authenticated user", 403
                    )
            elif "user" not in key and key not in {"request_id", "idempotency_key"}:
                check_resource(session, principal, value)
        for key in ("limit", "page_size", "page", "offset"):
            if key in data:
                try:
                    amount = int(data[key])
                except (TypeError, ValueError) as exc:
                    raise AppError("VALIDATION_ERROR", "Invalid pagination", 422) from exc
                if amount < 0 or amount > (200 if key in {"limit", "page_size"} else 100000):
                    raise AppError("VALIDATION_ERROR", "Pagination exceeds allowed bounds", 422)
        check_rate(
            settings,
            request.app.state.rate_limits,
            str(user.id),
            "expensive" if request.method == "POST" else "normal",
        )
        if settings.controlled_environment and request.method == "POST":
            path = request.url.path
            synchronous_expensive = path.endswith(
                ("/research", "/parse", "/datasets/build", "/train", "/runs/build")
            ) or path.rstrip("/").endswith("/company-intelligence-reports")
            if synchronous_expensive:
                raise AppError(
                    "ASYNC_JOB_REQUIRED", "Submit this operation through the jobs API", 409
                )
        request.state.principal = principal
        context.set({**context.get(), "user_id": str(user.id)})
        if principal.role == "ADMIN" and request.method == "POST" and "/admin/" in request.url.path:
            security_event(session, "ADMIN_ACTION", request_id, user.id)
        return principal
    except AppError as exc:
        event = (
            "RATE_LIMIT_TRIGGERED"
            if exc.status_code == 429
            else "ARTIFACT_ACCESS_DENIED"
            if "artifact" in request.url.path
            else "AUTHORIZATION_DENIED"
        )
        security_event(session, event, request_id, principal.user_id if principal else None)
        raise


def install_security(app: Any) -> None:
    """Single dependency boundary; tests override this dependency explicitly."""
    from app.api.v1.router import router

    app.include_router(
        router, prefix=app.state.settings.api_v1_prefix, dependencies=[Depends(authorize_request)]
    )
