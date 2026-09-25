from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import IdentityMatchStatus, ProfileStatus

if TYPE_CHECKING:
    from app.models.extracted_field import ExtractedField


class CompanyProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "company_profiles"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "extractor_version", name="uq_company_profiles_document_version"
        ),
        CheckConstraint(
            "overall_confidence >= 0 AND overall_confidence <= 1", name="confidence_range"
        ),
        Index("ix_company_profiles_analysis_job_id", "analysis_job_id"),
        Index("ix_company_profiles_company_id", "company_id"),
        Index("ix_company_profiles_document_id", "document_id"),
    )

    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    reporting_period: Mapped[str | None] = mapped_column(String(100))
    business_description: Mapped[str | None] = mapped_column(String(1000))
    headquarters: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(2048))
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[ProfileStatus] = mapped_column(
        SAEnum(ProfileStatus, native_enum=False, create_constraint=True), nullable=False
    )
    identity_match_status: Mapped[IdentityMatchStatus] = mapped_column(
        SAEnum(IdentityMatchStatus, native_enum=False, create_constraint=True), nullable=False
    )
    extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)

    fields: Mapped[list[ExtractedField]] = relationship(back_populates="profile")
