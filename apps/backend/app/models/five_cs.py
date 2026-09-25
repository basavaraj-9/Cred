from __future__ import annotations

# ruff: noqa: E501
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import FinancialScope


class FiveCsAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "five_cs_assessments"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "statement_scope",
            "input_hash",
            "policy_version",
            "engine_version",
            name="uq_five_cs_assessments_input",
        ),
        CheckConstraint(
            "overall_completeness >= 0 AND overall_completeness <= 1", name="completeness_range"
        ),
        CheckConstraint(
            "overall_confidence >= 0 AND overall_confidence <= 1", name="confidence_range"
        ),
        CheckConstraint(
            "status IN ('VERIFIED','NEEDS_REVIEW','PARTIAL','UNAVAILABLE','CONFLICTING')",
            name="status_valid",
        ),
        Index("ix_five_cs_assessments_document_scope", "document_id", "statement_scope"),
        Index("ix_five_cs_assessments_status", "status"),
    )

    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    company_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("company_profiles.id"), nullable=False
    )
    financial_analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_analysis_runs.id"), nullable=False
    )
    financial_trend_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_trend_runs.id"), nullable=False
    )
    credit_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_assessments.id"), nullable=False
    )
    domain_classification_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("domain_classifications.id")
    )
    statement_scope: Mapped[FinancialScope] = mapped_column(
        SAEnum(FinancialScope, native_enum=False, create_constraint=True), nullable=False
    )
    overall_completeness: Mapped[float] = mapped_column(Float, nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    summary_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class FiveCsSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "five_cs_sections"
    __table_args__ = (
        UniqueConstraint(
            "five_cs_assessment_id", "section", name="uq_five_cs_sections_assessment_section"
        ),
        CheckConstraint(
            "section IN ('CHARACTER','CAPACITY','CAPITAL','COLLATERAL','CONDITIONS')",
            name="section_valid",
        ),
        CheckConstraint(
            "status IN ('VERIFIED','NEEDS_REVIEW','PARTIAL','UNAVAILABLE','CONFLICTING')",
            name="status_valid",
        ),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        CheckConstraint(
            "completeness_score >= 0 AND completeness_score <= 1", name="completeness_range"
        ),
        CheckConstraint(
            "positive_count >= 0 AND negative_count >= 0 AND review_count >= 0",
            name="counts_nonnegative",
        ),
        Index("ix_five_cs_sections_assessment_id", "five_cs_assessment_id"),
    )

    five_cs_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("five_cs_assessments.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary_version: Mapped[str] = mapped_column(String(100), nullable=False)


class FiveCsEvidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "five_cs_evidence"
    __table_args__ = (
        UniqueConstraint(
            "five_cs_section_id",
            "observation_code",
            "source_reference_id",
            name="uq_five_cs_evidence_observation_source",
        ),
        CheckConstraint(
            "impact IN ('POSITIVE','NEGATIVE','NEUTRAL','REVIEW')", name="impact_valid"
        ),
        CheckConstraint(
            "status IN ('VERIFIED','NEEDS_REVIEW','PARTIAL','UNAVAILABLE','CONFLICTING')",
            name="status_valid",
        ),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        CheckConstraint(
            "source_type IS NULL OR source_type IN ('COMPANY_PROFILE','EXTRACTED_FIELD','FINANCIAL_VALUE','FINANCIAL_RATIO','FINANCIAL_TREND','FINANCIAL_ANOMALY','CREDIT_ASSESSMENT','CREDIT_SUBSCORE','DOMAIN_CLASSIFICATION','DOCUMENT_PAGE','RESEARCH_FINDING')",
            name="source_type_valid",
        ),
        CheckConstraint("page_number IS NULL OR page_number >= 1", name="page_number_positive"),
        Index("ix_five_cs_evidence_section_id", "five_cs_section_id"),
        Index("ix_five_cs_evidence_observation_code", "observation_code"),
    )

    five_cs_section_id: Mapped[UUID] = mapped_column(
        ForeignKey("five_cs_sections.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(60), nullable=False)
    observation_code: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(50))
    source_reference_id: Mapped[UUID | None] = mapped_column()
    document_page_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_pages.id"))
    page_number: Mapped[int | None] = mapped_column(Integer)
    raw_value: Mapped[str | None] = mapped_column(Text)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FiveCsReviewItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "five_cs_review_items"
    __table_args__ = (
        UniqueConstraint(
            "five_cs_assessment_id", "reason_code", name="uq_five_cs_review_items_reason"
        ),
        CheckConstraint(
            "section IN ('CHARACTER','CAPACITY','CAPITAL','COLLATERAL','CONDITIONS')",
            name="section_valid",
        ),
        CheckConstraint("status IN ('OPEN','RESOLVED','DISMISSED')", name="status_valid"),
        CheckConstraint("priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="priority_valid"),
        Index("ix_five_cs_review_items_assessment_id", "five_cs_assessment_id"),
    )

    five_cs_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("five_cs_assessments.id", ondelete="CASCADE"), nullable=False
    )
    five_cs_evidence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("five_cs_evidence.id", ondelete="SET NULL")
    )
    section: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
