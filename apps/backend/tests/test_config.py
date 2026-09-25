import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url is None
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"


def test_invalid_api_prefix() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, api_v1_prefix="api/v1")
