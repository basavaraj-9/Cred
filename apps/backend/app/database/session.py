from collections.abc import Generator
from functools import lru_cache

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker, with_loader_criteria

from app.core.config import get_settings
from app.database.base import Base


def create_database_engine(database_url: str | None) -> Engine:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL must use PostgreSQL")
    settings = get_settings()
    return create_engine(
        parsed,
        pool_pre_ping=True,
        hide_parameters=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        connect_args={"connect_timeout": 2},
    )


@lru_cache
def get_engine(database_url: str) -> Engine:
    return create_database_engine(database_url)


def get_db(request: Request) -> Generator[Session, None, None]:
    database_url = request.app.state.settings.database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    engine = get_engine(database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    principal = getattr(request.state, "principal", None)
    if principal is not None and principal.role != "ADMIN":
        session.info["company_scope"] = list(principal.companies)
        session.info["user_scope"] = principal.user_id
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@event.listens_for(Session, "do_orm_execute")
def restrict_company_collections(state: ORMExecuteState) -> None:
    if (
        not state.is_select
        or "company_scope" not in state.session.info
        or state.execution_options.get("runtime_identity_lookup")
    ):
        return
    scope = state.session.info["company_scope"]
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if hasattr(model, "company_id"):
            predicate = model.company_id.in_(scope)
            if model.__tablename__ == "background_jobs":
                predicate = predicate | (
                    model.company_id.is_(None)
                    & (model.created_by == state.session.info["user_scope"])
                )
            elif model.__tablename__.startswith("analyst_chat") and hasattr(model, "user_id"):
                predicate = predicate | (
                    model.company_id.is_(None) & (model.user_id == state.session.info["user_scope"])
                )
            state.statement = state.statement.options(
                with_loader_criteria(model, predicate, include_aliases=True)
            )
        elif model.__tablename__ == "companies":
            state.statement = state.statement.options(
                with_loader_criteria(model, model.id.in_(scope), include_aliases=True)
            )
        if model.__tablename__.startswith("analyst_chat") and hasattr(model, "user_id"):
            state.statement = state.statement.options(
                with_loader_criteria(
                    model, model.user_id == state.session.info["user_scope"], include_aliases=True
                )
            )
