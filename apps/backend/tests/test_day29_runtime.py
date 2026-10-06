from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.main import create_app
from app.models.user import User
from app.runtime.observability import redact
from app.runtime.security import decode_token, issue_token
from app.runtime.storage import safe_path

pytestmark = pytest.mark.strict_auth


def settings(**overrides):
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=None,
        auth_signing_key=SecretStr("test-key-" * 8),
        **overrides,
    )


def test_live_is_public_but_api_requires_authentication():
    with TestClient(create_app(settings())) as client:
        response = client.get("/health/live", headers={"X-Request-ID": "test-correlation"})
        assert response.json() == {"status": "LIVE"}
        assert response.headers["x-request-id"] == "test-correlation"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        response = client.get("/api/v1/status")
        assert response.status_code == 401
        assert response.json()["error_code"] == "AUTHENTICATION_REQUIRED"
        assert client.get("/health/dependencies").status_code == 401


def test_readiness_does_not_expose_dependency_configuration(tmp_path):
    with TestClient(create_app(settings(local_storage_path=tmp_path))) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "NOT_READY"}
        assert str(tmp_path) not in response.text


def test_request_body_and_content_type_limits():
    with TestClient(create_app(settings(max_json_bytes=1024))) as client:
        assert (
            client.post(
                "/api/v1/auth/token", content="x", headers={"Content-Type": "text/plain"}
            ).status_code
            == 415
        )
        assert (
            client.post(
                "/api/v1/auth/token", content="{", headers={"Content-Type": "application/json"}
            ).status_code
            == 422
        )
        assert client.post("/api/v1/auth/token", json={"value": "x" * 1024}).status_code == 413
        assert client.request("GET", "/health/live", json={"value": "x" * 1024}).status_code == 413


def test_token_claims_signature_audience_and_expiry():
    config = settings()
    user = User(id=uuid4(), email="test@example.test", reviewer_role="VIEWER", token_version=4)
    token = issue_token(user, config)
    claims = decode_token(token, config)
    assert claims["sub"] == str(user.id)
    assert claims["ver"] == 4
    for changes in (
        {"aud": "another-service"},
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"iss": "another-issuer"},
    ):
        forged = jwt.encode(
            {**claims, **changes}, config.auth_signing_key.get_secret_value(), algorithm="HS256"
        )
        with pytest.raises(AppError):
            decode_token(forged, config)
    with pytest.raises(AppError):
        decode_token(token + "tampered", config)


def test_controlled_environment_rejects_insecure_configuration():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", database_url=None)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="unknown")


def test_secret_redaction_and_artifact_containment(tmp_path):
    rendered = str(redact({"password": "private", "message": "Bearer token-value"}))
    assert "private" not in rendered and "token-value" not in rendered
    for reference in ("../outside.pdf", "C:\\outside.pdf", "/outside.pdf"):
        with pytest.raises(AppError):
            safe_path(tmp_path, reference)
    assert safe_path(tmp_path, "reports/report.pdf") == tmp_path / "reports/report.pdf"


def test_production_provider_guard_has_no_fixture_fallback():
    from app.core.config import Environment
    from app.runtime.provider_safety import runtime_settings
    from app.services.external_research.providers.fixture import FixtureResearchProvider
    from app.services.stock.service import FixtureListedUniverseProvider

    controlled = settings().model_copy(update={"app_env": Environment.PRODUCTION})
    token = runtime_settings.set(controlled)
    try:
        with pytest.raises(AppError) as caught:
            FixtureListedUniverseProvider()._all()
        assert caught.value.code == "DEVELOPMENT_PROVIDER_FORBIDDEN"
        with pytest.raises(AppError):
            FixtureResearchProvider().search(None, "Company")
    finally:
        runtime_settings.reset(token)


def test_reference_extraction_preserves_typed_ids():
    from app.runtime.security import references

    identifier = uuid4()
    assert references({"company_id": identifier}) == [("company_id", identifier)]


def test_memory_rate_limit_and_dependency_failure():
    from app.runtime.rate_limit import MemoryRateLimitStore, check_rate

    store = MemoryRateLimitStore()
    config = settings(rate_limit_per_minute=1)
    check_rate(config, store, "user", "normal")
    with pytest.raises(AppError) as caught:
        check_rate(config, store, "user", "normal")
    assert caught.value.status_code == 429

    class FailedStore:
        def increment(self, key, window):
            raise ConnectionError("private connection details")

    with pytest.raises(AppError) as caught:
        check_rate(config, FailedStore(), "user", "normal")
    assert caught.value.status_code == 503
    assert "private" not in caught.value.message


def test_temporary_cleanup_preserves_artifacts(tmp_path):
    import os

    from app.runtime.storage import cleanup_temporary

    temporary = tmp_path / ".runtime-temporary"
    temporary.mkdir()
    old = temporary / "old.temporary"
    old.write_text("temporary")
    artifact = tmp_path / "report.pdf"
    artifact.write_text("immutable")
    os.utime(old, (0, 0))
    assert cleanup_temporary(tmp_path, 1) == 1
    assert artifact.read_text() == "immutable"


def test_openapi_includes_authentication_and_jobs():
    schema = create_app(settings()).openapi()
    assert "HTTPBearer" in schema["components"]["securitySchemes"]
    assert "/api/v1/jobs" in schema["paths"]
    assert schema["paths"]["/api/v1/status"]["get"]["security"]


def test_giant_json_response_is_bounded():
    app = create_app(settings(max_json_response_bytes=1024))

    @app.get("/large-response")
    def large():
        return {"data": "x" * 2048}

    with TestClient(app) as client:
        response = client.get("/large-response")
        assert response.status_code == 413
        assert response.json()["error_code"] == "RESPONSE_TOO_LARGE"
        assert response.headers["x-request-id"]


@pytest.mark.parametrize(
    "changes",
    [
        {"debug": True},
        {"https_deployment": False},
        {"allowed_origins": "*"},
        {"trusted_hosts": "*"},
        {"auth_signing_key": "short"},
        {"local_storage_path": "relative"},
        {"queue_backend": "database"},
        {"rate_limit_backend": "memory"},
        {"redis_url": ""},
    ],
)
def test_production_configuration_rejects_each_unsafe_override(tmp_path, changes):
    values = dict(
        app_env="production",
        database_url="postgresql://test",
        auth_signing_key="test-signing-key-" * 4,
        https_deployment=True,
        allowed_origins="https://app.example.test",
        trusted_hosts="api.example.test",
        local_storage_path=tmp_path,
        queue_backend="redis_rq",
        rate_limit_backend="redis",
        redis_url="redis://test",
    )
    assert Settings(_env_file=None, **values).controlled_environment
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**values, **changes})
