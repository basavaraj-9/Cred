from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis_job import AnalysisJob
    from app.models.company import Company
    from app.models.user import User


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_analysis_job_id", "analysis_job_id"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    analysis_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("analysis_jobs.id"))
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id"))
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str | None] = mapped_column(String(2000))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User | None] = relationship(back_populates="audit_logs")
    analysis_job: Mapped[AnalysisJob | None] = relationship(back_populates="audit_logs")
    company: Mapped[Company | None] = relationship(back_populates="audit_logs")
