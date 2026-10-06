import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def legacy_auth_override(request, monkeypatch):
    """Legacy service tests bypass only the HTTP auth dependency, explicitly in tests.

    Day 29 security tests exercise the real boundary with the strict_auth marker.
    There is no application configuration switch for bypassing authentication.
    """
    if request.node.get_closest_marker("strict_auth"):
        return
    from uuid import UUID

    from fastapi import Request

    import app.main as main_module
    from app.runtime.security import Principal, authorize_request, install_security

    async def test_principal(http_request: Request) -> Principal:
        principal = Principal(UUID(int=1), "ADMIN", frozenset())
        http_request.state.principal = principal
        return principal

    def install_for_test(app):
        install_security(app)
        if app.state.settings.app_env == "test":
            app.dependency_overrides[authorize_request] = test_principal

    monkeypatch.setattr(main_module, "install_security", install_for_test)


@pytest.fixture
def client() -> TestClient:
    with TestClient(
        create_app(Settings(_env_file=None, app_env="test", ocr_enabled=False))
    ) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def test_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    parsed = make_url(url)
    assert parsed.get_backend_name() == "postgresql"
    assert "test" in (parsed.database or "").lower(), "Refusing to modify a non-test database"
    return url


@pytest.fixture(scope="module")
def database_engine(test_url: str) -> Iterator[Engine]:
    assert os.getenv("APP_ENV") == "test", "Database tests require APP_ENV=test"
    get_settings.cache_clear()
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
    engine = create_engine(test_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(database_engine: Engine) -> Iterator[Session]:
    with Session(database_engine) as session:
        yield session
        session.rollback()
