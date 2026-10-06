"""Bounded dependency probes; public readiness never exposes connection details."""

import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, Request
from redis import Redis
from sqlalchemy import text
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.database.session import get_engine
from app.runtime.observability import metrics
from app.runtime.security import Principal, authorize_request, require_permission

router = APIRouter(tags=["Runtime"])


def dependency_status(settings: Settings) -> dict[str, str]:
    result = {"database": "NOT_READY", "migration": "NOT_READY", "storage": "NOT_READY"}
    result["authentication"] = "READY" if settings.auth_signing_key else "NOT_READY"
    if settings.database_url:
        try:
            with get_engine(settings.database_url).connect() as connection:
                connection.execute(text("SELECT 1"))
                result["database"] = "READY"
                actual = set(connection.scalars(text("SELECT version_num FROM alembic_version")))
            backend = Path(__file__).resolve().parents[2]
            config = Config(str(backend / "alembic.ini"))
            config.set_main_option("script_location", str(backend / "alembic"))
            expected = set(ScriptDirectory.from_config(config).get_heads())
            result["migration"] = "READY" if actual == expected else "NOT_READY"
        except Exception:
            # Health responses contain bounded states, never dependency exceptions.
            pass
    try:
        root = settings.storage_root
        root.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=root, prefix=".readiness-", suffix=".temporary") as probe:
            probe.write(b"ready")
            probe.flush()
        result["storage"] = "READY"
    except OSError:
        pass
    result["queue"] = "READY" if settings.queue_backend == "database" else "NOT_READY"
    result["rate_limit"] = "READY" if settings.rate_limit_backend == "memory" else "NOT_READY"
    if settings.redis_url and (
        settings.queue_backend == "redis_rq" or settings.rate_limit_backend == "redis"
    ):
        try:
            with Redis.from_url(
                settings.redis_url, socket_connect_timeout=2, socket_timeout=2
            ) as redis:
                redis.ping()
            result["queue"] = "READY"
            result["rate_limit"] = "READY"
        except Exception:
            pass
    result["ocr"] = "READY" if settings.ocr_enabled and shutil.which("tesseract") else "WARN"
    result["analytics"] = "NON_PRODUCTION_ANALYTICS"
    return result


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "LIVE"}


@router.get("/health/ready")
def ready(request: Request) -> JSONResponse:
    states = dependency_status(request.app.state.settings)
    available = all(
        states[key] == "READY"
        for key in ("database", "migration", "storage", "queue", "rate_limit", "authentication")
    )
    return JSONResponse(
        {"status": "READY" if available else "NOT_READY"},
        status_code=200 if available else 503,
    )


@router.get("/health/dependencies")
def dependencies(
    request: Request, principal: Principal = Depends(authorize_request)
) -> dict[str, str]:
    require_permission(principal, "ADMIN_RUNTIME")
    return dependency_status(request.app.state.settings)


@router.get("/metrics")
def runtime_metrics(
    request: Request, principal: Principal = Depends(authorize_request)
) -> Response:
    require_permission(principal, "ADMIN_RUNTIME")
    if not request.app.state.settings.metrics_enabled:
        return Response(status_code=404)
    return Response(metrics.render(), media_type="text/plain; version=0.0.4")
