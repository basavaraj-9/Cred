"""Creates a fresh disposable test database and verifies migrations and a real worker.

Requires TEST_DATABASE_URL for a PostgreSQL role allowed to create a test database.
Never resets or drops the supplied database. No credentials are written to output.
"""

import json
import os
import secrets
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings, get_settings
from app.models.company import Company
from app.models.user import User
from app.runtime.security import PASSWORDS


def main() -> None:
    supplied = make_url(os.environ["TEST_DATABASE_URL"])
    if supplied.get_backend_name() != "postgresql" or "test" not in (supplied.database or ""):
        raise SystemExit("A PostgreSQL TEST_DATABASE_URL is required")
    database = f"company_intelligence_day29_{uuid4().hex[:8]}_test"
    server = create_engine(
        supplied.set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    with server.connect() as connection:
        # Identifier is entirely generated above; no caller-provided SQL is interpolated.
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    server.dispose()
    url = supplied.set(database=database).render_as_string(hide_password=False)
    root = Path(__file__).resolve().parents[3] / "output" / "day29-smoke"
    root.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        APP_ENV="test",
        DATABASE_URL=url,
        TEST_DATABASE_URL=url,
        AUTH_SIGNING_KEY=secrets.token_urlsafe(48),
        LOCAL_STORAGE_PATH=str(root / "storage"),
        OCR_ENABLED="false",
    )
    get_settings.cache_clear()
    assert get_settings().database_url == get_settings().test_database_url == url
    config = Config("alembic.ini")
    checks: dict[str, object] = {"database": database, "checks": {}}
    results = checks["checks"]
    assert isinstance(results, dict)
    command.upgrade(config, "head")
    results["clean_database_to_head"] = True
    command.downgrade(config, "0027_company_intelligence_360_report")
    command.upgrade(config, "head")
    results["day29_downgrade_reapply"] = True
    command.check(config)
    results["schema_drift"] = "none"
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
    results["base_to_head_roundtrip"] = True

    from app.main import create_app
    from app.runtime.worker import run_one

    engine = create_engine(url, hide_parameters=True)
    password = secrets.token_urlsafe(24)
    with Session(engine) as session, session.begin():
        admin = User(
            email="day29-runtime@example.test",
            reviewer_role="ADMIN",
            password_hash=PASSWORDS.hash(password),
        )
        company = Company(legal_name="Day 29 Runtime Smoke Company")
        session.add_all([admin, company])
        session.flush()
        company_id = str(company.id)
    with TestClient(create_app(get_settings())) as client:
        began = time.perf_counter()
        assert client.get("/health/live").status_code == 200
        results["live_latency_ms"] = round((time.perf_counter() - began) * 1000, 2)
        assert client.get("/api/v1/jobs").status_code == 401
        login = client.post(
            "/api/v1/auth/token", json={"email": "day29-runtime@example.test", "password": password}
        )
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        body = {
            "job_type": "REPORT_360",
            "company_id": company_id,
            "idempotency_key": "day29-worker-smoke",
            "include_stock": False,
        }
        began = time.perf_counter()
        queued = client.post("/api/v1/jobs", json=body, headers=headers)
        assert queued.status_code == 202, queued.text
        results["enqueue_latency_ms"] = round((time.perf_counter() - began) * 1000, 2)
        identifier = queued.json()["id"]
        assert client.post("/api/v1/jobs", json=body, headers=headers).json()["id"] == identifier
        assert run_one(identifier)
        finished = client.get(f"/api/v1/jobs/{identifier}", headers=headers).json()
        assert finished["status"] == "COMPLETED", finished
        assert len(finished["attempts"]) == 1
        results["authenticated_queue_and_real_worker"] = True
        report_id = finished["result_json"]["report_id"]
        me = client.get("/api/v1/auth/me", headers=headers).json()
        report = client.get(
            f"/api/v1/company-intelligence-reports/{report_id}/artifacts/pdf",
            params={"actor_user_id": me["user_id"]},
            headers=headers,
        )
        assert report.status_code == 200 and report.content.startswith(b"%PDF-")
        (root / "runtime-smoke-report.pdf").write_bytes(report.content)
        results["authenticated_pdf_download"] = True
        assert client.get("/health/ready").status_code == 200
        results["readiness"] = True
    # Exercise real controlled settings with an intentionally unavailable Redis endpoint.
    # This is a failure/degradation smoke, not a claim that Redis has been deployed.
    production = Settings(
        _env_file=None,
        app_env="production",
        database_url=url,
        auth_signing_key=os.environ["AUTH_SIGNING_KEY"],
        https_deployment=True,
        allowed_origins="https://app.example.test",
        trusted_hosts="api.example.test",
        local_storage_path=root / "storage",
        queue_backend="redis_rq",
        rate_limit_backend="redis",
        redis_url="redis://127.0.0.1:6399",
        ocr_enabled=False,
        external_research_enabled=False,
        stock_ml_research_enabled=False,
    )
    with TestClient(create_app(production), base_url="https://api.example.test") as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert "strict-transport-security" in live.headers
        ready = client.get("/health/ready")
        assert ready.status_code == 503 and ready.json() == {"status": "NOT_READY"}
        assert client.get("/api/v1/jobs").status_code == 503
        results["production_missing_redis_fails_closed"] = True
    engine.dispose()
    (root / "verification.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
