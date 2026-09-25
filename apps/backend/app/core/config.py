from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Company Intelligence Platform"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    backend_host: str = "0.0.0.0"
    backend_port: int = Field(default=8000, ge=1, le=65535)
    frontend_url: str = "http://localhost:3000"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str | None = None
    test_database_url: str | None = None
    redis_url: str | None = None
    storage_provider: Literal["local"] = "local"
    local_storage_path: Path = Path("storage")
    max_upload_size_mb: int = Field(default=50, ge=1, le=1024)
    allowed_file_types: str = "pdf"
    ocr_enabled: bool = True
    ocr_provider: Literal["tesseract"] = "tesseract"
    ocr_language: str = "eng"
    ocr_dpi: int = Field(default=200, ge=72, le=400)
    ocr_timeout_seconds: int = Field(default=30, ge=1, le=300)
    text_quality_min_characters: int = Field(default=50, ge=1, le=1000)
    text_quality_min_alphanumeric_ratio: float = Field(default=0.30, ge=0, le=1)
    domain_verified_threshold: float = Field(default=0.85, ge=0, le=1)
    domain_review_threshold: float = Field(default=0.65, ge=0, le=1)
    accounting_reconciliation_tolerance_percent: float = Field(default=1.0, ge=0, le=20)
    debt_reconciliation_tolerance_percent: float = Field(default=1.0, ge=0, le=20)
    cash_reconciliation_tolerance_percent: float = Field(default=1.0, ge=0, le=20)

    @property
    def storage_root(self) -> Path:
        path = self.local_storage_path
        project_root = Path(__file__).resolve().parents[4]
        return (path if path.is_absolute() else project_root / path).resolve()

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @field_validator("allowed_file_types")
    @classmethod
    def validate_allowed_file_types(cls, value: str) -> str:
        if value.strip().lower() != "pdf":
            raise ValueError("Day 3 supports only PDF files")
        return "pdf"

    @field_validator("database_url", "test_database_url", mode="before")
    @classmethod
    def empty_database_url_is_unset(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        if not value.startswith("/") or value == "/" or value.endswith("/"):
            raise ValueError("API_V1_PREFIX must start with / and have no trailing /")
        return value

    @field_validator("frontend_url")
    @classmethod
    def validate_frontend_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("FRONTEND_URL must be an HTTP(S) origin")
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
