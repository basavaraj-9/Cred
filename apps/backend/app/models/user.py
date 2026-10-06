from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis_job import AnalysisJob
    from app.models.audit_log import AuditLog


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "reviewer_role IN ('CREDIT_ANALYST','SENIOR_CREDIT_REVIEWER','CREDIT_MANAGER',"
            "'CREDIT_COMMITTEE_MEMBER','ADMIN','VIEWER','RESEARCH_ANALYST')",
            name="reviewer_role_valid",
        ),
        CheckConstraint(
            "account_status IN ('ACTIVE','DISABLED','LOCKED','PENDING')",
            name="account_status_valid",
        ),
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    account_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    reviewer_role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="CREDIT_ANALYST", server_default="CREDIT_ANALYST"
    )

    analysis_jobs: Mapped[list[AnalysisJob]] = relationship(back_populates="created_by_user")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")
