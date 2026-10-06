from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CompanyAccess(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_company_access"
    __table_args__ = (UniqueConstraint("user_id", "company_id", name="uq_user_company_access"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)


class BackgroundJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("job_type", "input_hash", name="uq_background_jobs_input"),
        CheckConstraint(
            "status IN ('PENDING','QUEUED','RUNNING','RETRYING','COMPLETED',"
            "'FAILED','CANCELLED','TIMED_OUT')",
            name="status_valid",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 5 AND timeout_seconds > 0",
            name="limits_valid",
        ),
        Index("ix_background_jobs_claim", "status", "scheduled_at", "priority"),
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id"), index=True)
    analysis_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("analysis_jobs.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    queue_name: Mapped[str] = mapped_column(String(50), nullable=False, default="analytics")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    lease_id: Mapped[UUID | None] = mapped_column()
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)


class JobAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_attempts"
    __table_args__ = (UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("background_jobs.id"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    retryable: Mapped[bool] = mapped_column(default=False, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    worker_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
