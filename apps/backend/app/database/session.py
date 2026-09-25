from collections.abc import Generator
from functools import lru_cache

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str | None) -> Engine:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL must use PostgreSQL")
    return create_engine(parsed, pool_pre_ping=True, connect_args={"connect_timeout": 2})


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
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
