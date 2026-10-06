"""One isolated execution process; invoked only by the supervisor with a database lease."""

import logging
import sys
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.database.session import get_engine
from app.models.runtime import BackgroundJob, CompanyAccess
from app.models.user import User
from app.runtime.job_handlers import execute
from app.runtime.jobs import JOB_PERMISSIONS, finish
from app.runtime.observability import context
from app.runtime.security import Principal, check_resource, references, require_permission


def run(job_id: UUID, lease_id: UUID) -> None:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("Worker database is not configured")
    engine = get_engine(settings.database_url)
    result = None
    error_code = None
    try:
        with Session(engine, expire_on_commit=False) as session:
            job = session.get(BackgroundJob, job_id)
            if job is None or job.status != "RUNNING" or job.lease_id != lease_id:
                return
            context.set(
                {
                    "job_id": str(job.id),
                    "request_id": job.request_id,
                    "user_id": str(job.created_by),
                    "environment": settings.app_env.value,
                }
            )
            user = session.get(User, job.created_by)
            if user is None or not user.is_active or user.account_status != "ACTIVE":
                raise AppError("AUTHORIZATION_DENIED", "Account unavailable", 403)
            principal = Principal(
                user.id,
                user.reviewer_role,
                frozenset(
                    session.scalars(
                        select(CompanyAccess.company_id).where(CompanyAccess.user_id == user.id)
                    )
                ),
            )
            require_permission(principal, JOB_PERMISSIONS[job.job_type])
            if job.company_id:
                principal.company(job.company_id)
            for _, reference in references(job.payload_json):
                check_resource(session, principal, reference)
            if principal.role != "ADMIN":
                session.info.update(company_scope=list(principal.companies), user_scope=user.id)
            job_type, data, actor_id = job.job_type, job.payload_json, job.created_by
            session.rollback()  # End the authorization read before service-owned transactions.
            result = execute(session, settings, job_type, data, actor_id)
    except AppError as exc:
        error_code = exc.code
    except TimeoutError:
        error_code = "PROVIDER_TIMEOUT"
    except ConnectionError:
        error_code = "DEPENDENCY_UNAVAILABLE"
    except OperationalError as exc:
        sqlstate = getattr(exc.orig, "sqlstate", None)
        transient = {"40001", "40P01", "53300", "57P01", "57P02", "57P03"}
        error_code = (
            "DATABASE_TRANSIENT"
            if exc.connection_invalidated
            or sqlstate in transient
            or (isinstance(sqlstate, str) and sqlstate.startswith("08"))
            else "DATABASE_FAILURE"
        )
    except Exception:
        error_code = "JOB_EXECUTION_FAILED"
        logging.getLogger(__name__).exception("job_execution_failed")
    with Session(engine) as session, session.begin():
        finish(session, settings, job_id, lease_id, result=result, error_code=error_code)


if __name__ == "__main__":
    from app.core.logging import configure_logging

    configure_logging(get_settings().log_level)
    run(UUID(sys.argv[1]), UUID(sys.argv[2]))
