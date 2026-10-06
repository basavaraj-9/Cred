from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    app_name: str = "Company Intelligence Platform"
    app_version: str = "0.1.0"
    app_env: Environment = Environment.DEVELOPMENT
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    backend_host: str = "0.0.0.0"
    backend_port: int = Field(default=8000, ge=1, le=65535)
    frontend_url: str = "http://localhost:3000"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str | None = Field(default=None, repr=False, exclude=True)
    test_database_url: str | None = Field(default=None, repr=False, exclude=True)
    redis_url: str | None = Field(default=None, repr=False, exclude=True)
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

    auth_signing_key: SecretStr | None = Field(default=None, exclude=True)
    auth_issuer: str = "company-intelligence"
    auth_audience: str = "company-intelligence-api"
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    allowed_origins: str = ""
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    https_deployment: bool = False
    request_timeout_seconds: int = Field(default=30, ge=1, le=120)
    max_request_bytes: int = Field(default=55 * 1024 * 1024, ge=1024, le=1100 * 1024 * 1024)
    max_json_bytes: int = Field(default=1024 * 1024, ge=1024, le=4 * 1024 * 1024)
    max_json_response_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    db_pool_timeout: int = Field(default=30, ge=1, le=120)
    db_pool_recycle: int = Field(default=1800, ge=60)
    queue_backend: Literal["database", "redis_rq"] = "database"
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    rate_limit_per_minute: int = Field(default=120, ge=1, le=10000)
    expensive_rate_limit_per_minute: int = Field(default=10, ge=1, le=1000)
    login_rate_limit_per_minute: int = Field(default=5, ge=1, le=100)
    worker_concurrency: int = Field(default=1, ge=1, le=16)
    job_max_attempts: int = Field(default=3, ge=1, le=5)
    job_timeout_seconds: int = Field(default=900, ge=1, le=7200)
    job_recovery_grace_seconds: int = Field(default=30, ge=1, le=300)
    retry_base_seconds: int = Field(default=5, ge=1, le=60)
    temporary_retention_hours: int = Field(default=24, ge=1, le=720)
    metrics_enabled: bool = True
    external_research_enabled: bool = True
    stock_ml_research_enabled: bool = True

    @property
    def controlled_environment(self) -> bool:
        return self.app_env in {Environment.STAGING, Environment.PRODUCTION}

    @property
    def cors_origins(self) -> list[str]:
        return [value.strip() for value in (self.allowed_origins or self.frontend_url).split(",")]

    @model_validator(mode="after")
    def runtime_validation(self) -> "Settings":
        for origin in self.cors_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or parsed.username
            ):
                raise ValueError("CORS requires explicit HTTP(S) origins")
        if self.controlled_environment:
            if (
                not self.database_url
                or not self.auth_signing_key
                or len(self.auth_signing_key.get_secret_value()) < 32
            ):
                raise ValueError("Database and signing key (minimum 32 characters) required")
            if (
                self.debug
                or not self.https_deployment
                or not self.allowed_origins
                or any(not item.startswith("https://") for item in self.cors_origins)
            ):
                raise ValueError(
                    "Controlled runtime requires HTTPS, explicit HTTPS origins and debug disabled"
                )
            if "*" in self.trusted_hosts or self.trusted_hosts == "localhost,127.0.0.1,testserver":
                raise ValueError("Controlled runtime requires explicit trusted hosts")
            if (
                not self.local_storage_path.is_absolute()
                or self.rate_limit_backend != "redis"
                or self.queue_backend != "redis_rq"
                or not self.redis_url
            ):
                raise ValueError(
                    "Absolute storage root and shared Redis queue/rate limits required"
                )
        if (
            self.queue_backend == "redis_rq" or self.rate_limit_backend == "redis"
        ) and not self.redis_url:
            raise ValueError("Redis configuration is required for selected runtime adapters")
        return self

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
