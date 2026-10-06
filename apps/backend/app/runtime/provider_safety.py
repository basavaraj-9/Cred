from contextvars import ContextVar

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError

runtime_settings: ContextVar[Settings | None] = ContextVar("runtime_settings", default=None)


def reject_development_provider() -> None:
    settings = runtime_settings.get() or get_settings()
    if settings.controlled_environment:
        raise AppError(
            "DEVELOPMENT_PROVIDER_FORBIDDEN",
            "Development data providers are unavailable in controlled environments",
            503,
        )
