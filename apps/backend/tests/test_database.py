from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool
from starlette.requests import Request

from alembic import command
from app.core.config import Settings, get_settings
from app.database.health import check_database
from app.database.repositories.analysis_job import create_analysis_job, get_analysis_job
from app.database.repositories.audit_log import write_audit_log
from app.database.repositories.company import create_company, get_company
from app.database.repositories.document import register_document_metadata
from app.database.session import get_db, get_engine
from app.main import create_app
from app.models import AnalysisJob, Company, User
from app.models.enums import AnalysisJobStatus, DocumentStatus


def test_database_migrations_apply_cleanly_and_downgrade(
    test_url: str, database_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TEST_DATABASE_URL", test_url)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    assert {
        "users",
        "companies",
        "analysis_jobs",
        "documents",
        "audit_logs",
        "financial_extraction_runs",
        "financial_statements",
        "financial_line_items",
        "financial_analysis_runs",
        "normalized_financial_values",
        "financial_validation_issues",
        "financial_ratios",
        "financial_ratio_inputs",
        "financial_trend_runs",
        "financial_trends",
        "financial_trend_inputs",
        "financial_anomalies",
        "financial_anomaly_inputs",
    }.issubset(inspect(database_engine).get_table_names())
    command.downgrade(config, "base")
    assert "companies" not in inspect(database_engine).get_table_names()
    command.upgrade(config, "head")
    assert "audit_logs" in inspect(database_engine).get_table_names()
    get_settings.cache_clear()


def test_database_connection(database_engine: Engine, test_url: str) -> None:
    assert check_database(test_url, database_engine) == "connected"
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1


def test_create_user(db_session: Session) -> None:
    user = User(email=f"person-{uuid4()}@example.test")
    db_session.add(user)
    db_session.flush()
    assert user.id is not None
    assert user.is_active is True
    assert user.created_at.tzinfo is not None
    assert user.updated_at.tzinfo is not None


def test_duplicate_email_rejected(db_session: Session) -> None:
    email = f"duplicate-{uuid4()}@example.test"
    db_session.add_all([User(email=email), User(email=email)])
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_create_company(db_session: Session) -> None:
    company = create_company(db_session, "Example Holdings")
    assert get_company(db_session, company.id) is company
    assert company.country == "India"


def test_company_requires_legal_name(db_session: Session) -> None:
    db_session.add(Company())
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_create_analysis_job_and_relationship(db_session: Session) -> None:
    company = create_company(db_session, "Analysis Co")
    job = create_analysis_job(db_session, company.id)
    assert get_analysis_job(db_session, job.id) is job
    assert job.company is company
    assert job.status == AnalysisJobStatus.PENDING
    assert job.progress_percent == 0
    assert job in company.analysis_jobs


@pytest.mark.parametrize("progress", [-1, 101])
def test_progress_percent_constraints(db_session: Session, progress: int) -> None:
    company = create_company(db_session, "Progress Co")
    db_session.add(AnalysisJob(company_id=company.id, progress_percent=progress))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_create_document_metadata_and_relationship(db_session: Session) -> None:
    company = create_company(db_session, "Document Co")
    job = create_analysis_job(db_session, company.id)
    document = register_document_metadata(db_session, job.id, company.id, "annual.pdf")
    assert document.analysis_job is job
    assert document.company is company
    assert document.status == DocumentStatus.REGISTERED
    assert document.storage_uri is None
    assert document.sha256_hash is None
    assert document in job.documents


def test_create_audit_log(db_session: Session) -> None:
    company = create_company(db_session, "Audit Co")
    job = create_analysis_job(db_session, company.id)
    log = write_audit_log(
        db_session,
        entity_type="analysis_job",
        entity_id=job.id,
        action="ANALYSIS_CREATED",
        event_type="creation",
        company_id=company.id,
        analysis_job_id=job.id,
        metadata_json={"source": "test"},
    )
    assert log.analysis_job is job
    assert log.company is company
    assert log.metadata_json == {"source": "test"}
    assert log.created_at.tzinfo is not None


def test_foreign_key_integrity(db_session: Session) -> None:
    db_session.add(AnalysisJob(company_id=uuid4()))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_transaction_rollback(database_engine: Engine) -> None:
    legal_name = f"Rollback {uuid4()}"
    with pytest.raises(RuntimeError), Session(database_engine) as session, session.begin():
        company = create_company(session, legal_name)
        job = create_analysis_job(session, company.id)
        write_audit_log(
            session,
            entity_type="analysis_job",
            entity_id=job.id,
            action="ANALYSIS_CREATED",
            event_type="creation",
            company_id=company.id,
            analysis_job_id=job.id,
        )
        raise RuntimeError("Simulated required step failure")
    with Session(database_engine) as session:
        assert session.scalar(select(Company).where(Company.legal_name == legal_name)) is None


def test_session_dependency_rolls_back_and_returns_connection(test_url: str) -> None:
    legal_name = f"Dependency rollback {uuid4()}"
    app = create_app(Settings(_env_file=None, app_env="test", database_url=test_url))
    request = Request({"type": "http", "app": app})
    engine = get_engine(test_url)
    assert isinstance(engine.pool, QueuePool)
    checked_out_before = engine.pool.checkedout()
    dependency = get_db(request)
    session = next(dependency)
    create_company(session, legal_name)
    with pytest.raises(RuntimeError):
        dependency.throw(RuntimeError("abort"))
    assert engine.pool.checkedout() == checked_out_before
    with Session(engine) as verifying_session:
        assert (
            verifying_session.scalar(select(Company).where(Company.legal_name == legal_name))
            is None
        )


def test_database_constraints_present(database_engine: Engine) -> None:
    inspector = inspect(database_engine)
    job_constraints = {item["name"] for item in inspector.get_check_constraints("analysis_jobs")}
    assert "ck_analysis_jobs_progress_range" in job_constraints
    user_indexes = {item["name"] for item in inspector.get_indexes("users")}
    assert "ix_users_email" in user_indexes
    assert any(
        column["name"] == "metadata_json" and column["type"].__class__.__name__ == "JSONB"
        for column in inspector.get_columns("audit_logs")
    )


def test_health_database_connected(test_url: str) -> None:
    settings = Settings(_env_file=None, app_env="test", database_url=test_url)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["dependencies"]["database"] == "connected"
    assert response.json()["status"] == "healthy"


def test_health_database_unavailable_behavior() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://invalid@127.0.0.1:1/unavailable_test",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["dependencies"]["database"] == "unavailable"
    assert response.json()["status"] == "degraded"
    assert "invalid@" not in response.text


def test_status_preserves_database_and_model_reporting(test_url: str) -> None:
    settings = Settings(_env_file=None, app_env="test", database_url=test_url)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["components"]["database"] == "connected"
    assert payload["components"]["document_intelligence"] == "foundation_ready"
    assert payload["development_stage"]["day"] == 26
