from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ClassificationStatus


class DomainClassification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "domain_classifications"
    __table_args__ = (
        UniqueConstraint(
            "company_profile_id",
            "model_id",
            "input_text_hash",
            "input_builder_version",
            name="uq_domain_classifications_input_model",
        ),
        Index("ix_domain_classifications_company_profile_id", "company_profile_id"),
        Index("ix_domain_classifications_document_id", "document_id"),
        CheckConstraint(
            "sector_confidence >= 0 AND sector_confidence <= 1", name="sector_confidence_range"
        ),
        CheckConstraint(
            "industry_confidence >= 0 AND industry_confidence <= 1",
            name="industry_confidence_range",
        ),
        CheckConstraint(
            "domain_confidence >= 0 AND domain_confidence <= 1", name="domain_confidence_range"
        ),
        CheckConstraint(
            "sub_domain_confidence >= 0 AND sub_domain_confidence <= 1",
            name="sub_domain_confidence_range",
        ),
        CheckConstraint(
            "overall_confidence >= 0 AND overall_confidence <= 1", name="overall_confidence_range"
        ),
    )

    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    company_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("company_profiles.id"), nullable=False
    )
    model_id: Mapped[UUID] = mapped_column(ForeignKey("ml_models.id"), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    sub_domain: Mapped[str] = mapped_column(String(100), nullable=False)
    sector_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    industry_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    domain_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    sub_domain_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[ClassificationStatus] = mapped_column(
        SAEnum(ClassificationStatus, native_enum=False, create_constraint=True), nullable=False
    )
    alternative_sub_domain: Mapped[str | None] = mapped_column(String(100))
    alternative_confidence: Mapped[float | None] = mapped_column(Float)
    taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_builder_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class DomainClassificationEvidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "domain_classification_evidence"
    __table_args__ = (
        UniqueConstraint(
            "domain_classification_id",
            "extracted_field_id",
            name="uq_domain_classification_evidence_field",
        ),
        Index("ix_domain_classification_evidence_classification_id", "domain_classification_id"),
    )

    domain_classification_id: Mapped[UUID] = mapped_column(
        ForeignKey("domain_classifications.id"), nullable=False
    )
    extracted_field_id: Mapped[UUID] = mapped_column(
        ForeignKey("extracted_fields.id"), nullable=False
    )
    document_page_id: Mapped[UUID] = mapped_column(ForeignKey("document_pages.id"), nullable=False)
    evidence_role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
