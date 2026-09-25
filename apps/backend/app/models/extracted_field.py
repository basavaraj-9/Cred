from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import FieldStatus

if TYPE_CHECKING:
    from app.models.company_profile import CompanyProfile


class ExtractedField(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        CheckConstraint("page_number >= 1", name="page_number_positive"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        CheckConstraint("length(trim(evidence_text)) > 0", name="evidence_nonempty"),
        Index("ix_extracted_fields_document_id", "document_id"),
        Index("ix_extracted_fields_document_page_id", "document_page_id"),
        Index("ix_extracted_fields_field_name", "field_name"),
        Index("ix_extracted_fields_status", "status"),
    )

    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    document_page_id: Mapped[UUID] = mapped_column(ForeignKey("document_pages.id"), nullable=False)
    company_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("company_profiles.id"), nullable=False
    )
    field_group: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[str] = mapped_column(String(30), nullable=False, default="string")
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[FieldStatus] = mapped_column(
        SAEnum(FieldStatus, native_enum=False, create_constraint=True), nullable=False
    )
    extraction_method: Mapped[str] = mapped_column(String(30), nullable=False, default="RULE")
    extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)

    profile: Mapped[CompanyProfile] = relationship(back_populates="fields")
