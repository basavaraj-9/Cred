from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AnalysisJobStatus, AnalysisStage

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.company import Company
    from app.models.document import Document
    from app.models.user import User


class AnalysisJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="progress_range"),
        Index("ix_analysis_jobs_company_id", "company_id"),
        Index("ix_analysis_jobs_status", "status"),
    )

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[AnalysisJobStatus] = mapped_column(
        SAEnum(AnalysisJobStatus, native_enum=False, create_constraint=True),
        nullable=False,
        default=AnalysisJobStatus.PENDING,
    )
    current_stage: Mapped[AnalysisStage] = mapped_column(
        SAEnum(AnalysisStage, native_enum=False, create_constraint=True),
        nullable=False,
        default=AnalysisStage.CREATED,
    )
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(2000))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship(back_populates="analysis_jobs")
    created_by_user: Mapped[User | None] = relationship(back_populates="analysis_jobs")
    documents: Mapped[list[Document]] = relationship(back_populates="analysis_job")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="analysis_job")
