import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.runtime.admin_api import router as admin_router
from app.runtime.auth import router as auth_router
from app.runtime.health import router as runtime_router
from app.runtime.job_api import router as job_router
from app.runtime.middleware import RuntimeMiddleware
from app.runtime.observability import register_secrets
from app.runtime.rate_limit import build_store
from app.runtime.security import install_security
from app.runtime.startup import validate_startup

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    register_secrets(
        [
            settings.database_url or "",
            settings.redis_url or "",
            settings.auth_signing_key.get_secret_value() if settings.auth_signing_key else "",
        ]
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        validate_startup(settings)
        logger.info("Application starting")
        yield
        logger.info("Application stopping")

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Foundation API for company intelligence, credit decisions, "
            "and Indian stock intelligence."
        ),
        version=settings.app_version,
        debug=settings.debug,
        docs_url=None if settings.controlled_environment else "/docs",
        redoc_url=None if settings.controlled_environment else "/redoc",
        openapi_url=None if settings.controlled_environment else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.rate_limits = build_store(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[host.strip() for host in settings.trusted_hosts.split(",")],
    )
    app.add_middleware(RuntimeMiddleware, settings=settings)
    register_exception_handlers(app)
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(runtime_router)
    app.include_router(job_router, prefix=settings.api_v1_prefix)
    app.include_router(admin_router, prefix=settings.api_v1_prefix)
    install_security(app)
    return app


app = create_app()
