from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis_job import AnalysisJob
    from app.models.audit_log import AuditLog
    from app.models.document import Document


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    legal_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    registration_number: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="India")
    website: Mapped[str | None] = mapped_column(String(2048))

    analysis_jobs: Mapped[list[AnalysisJob]] = relationship(back_populates="company")
    documents: Mapped[list[Document]] = relationship(back_populates="company")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="company")
