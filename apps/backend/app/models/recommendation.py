from __future__ import annotations

# ruff: noqa: E501
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FiveCsRefreshRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "five_cs_refresh_runs"
    __table_args__ = (
        CheckConstraint("status IN ('COMPLETED','NEEDS_REVIEW','FAILED')", name="status_valid"),
        UniqueConstraint(
            "base_five_cs_assessment_id",
            "research_run_id",
            "input_hash",
            name="uq_five_cs_refresh_input",
        ),
        Index("ix_five_cs_refresh_base", "base_five_cs_assessment_id"),
        Index("ix_five_cs_refresh_refreshed", "refreshed_five_cs_assessment_id"),
    )

    base_five_cs_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("five_cs_assessments.id"), nullable=False
    )
    refreshed_five_cs_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("five_cs_assessments.id"), nullable=False
    )
    research_run_id: Mapped[UUID] = mapped_column(ForeignKey("research_runs.id"), nullable=False)
    refresh_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    refresh_engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    updated_sections: Mapped[str] = mapped_column(String(255), nullable=False)
    new_review_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved_review_item_count: Mapped[int] = mapped_column(Integer, nullable=False)


class FiveCsResearchEvidenceLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "five_cs_research_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "impact IN ('POSITIVE','NEGATIVE','NEUTRAL','MIXED','REVIEW')", name="impact_valid"
        ),
        CheckConstraint(
            "status IN ('VERIFIED','NEEDS_REVIEW','CONFLICTING','STALE')", name="status_valid"
        ),
        UniqueConstraint(
            "five_cs_assessment_id",
            "research_finding_id",
            "mapping_code",
            name="uq_five_cs_research_mapping",
        ),
        Index("ix_five_cs_research_links_assessment", "five_cs_assessment_id"),
        Index("ix_five_cs_research_links_finding", "research_finding_id"),
    )

    five_cs_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("five_cs_assessments.id", ondelete="CASCADE"), nullable=False
    )
    five_cs_section_id: Mapped[UUID] = mapped_column(
        ForeignKey("five_cs_sections.id", ondelete="CASCADE"), nullable=False
    )
    five_cs_evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey("five_cs_evidence.id", ondelete="CASCADE"), nullable=False
    )
    research_finding_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_findings.id"), nullable=False
    )
    research_evidence_id: Mapped[UUID | None] = mapped_column(ForeignKey("research_evidence.id"))
    mapping_code: Mapped[str] = mapped_column(String(120), nullable=False)
    impact: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class CreditRecommendationPreparation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_recommendation_preparations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('READY_FOR_DECISION_REVIEW','CONDITIONAL_REVIEW_REQUIRED','INSUFFICIENT_EVIDENCE','CRITICAL_RISK_REVIEW','DATA_CONFLICT_REVIEW','NOT_READY')",
            name="status_valid",
        ),
        CheckConstraint(
            "overall_confidence >= 0 AND overall_confidence <= 1", name="confidence_range"
        ),
        CheckConstraint(
            "overall_completeness >= 0 AND overall_completeness <= 1", name="completeness_range"
        ),
        CheckConstraint(
            "critical_risk_count >= 0 AND risk_count >= 0 AND strength_count >= 0 AND review_item_count >= 0 AND missing_evidence_count >= 0",
            name="counts_nonnegative",
        ),
        UniqueConstraint(
            "document_id",
            "input_hash",
            "policy_version",
            "engine_version",
            name="uq_credit_recommendation_input",
        ),
        Index("ix_credit_recommendations_document", "document_id", "created_at"),
        Index("ix_credit_recommendations_status", "status"),
    )

    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    credit_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_assessments.id"), nullable=False
    )
    five_cs_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("five_cs_assessments.id"), nullable=False
    )
    research_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("research_runs.id"))
    fusion_experiment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_fusion_experiments.id")
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    overall_completeness: Mapped[float] = mapped_column(Float, nullable=False)
    critical_risk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_count: Mapped[int] = mapped_column(Integer, nullable=False)
    review_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary_version: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class CreditRecommendationFactor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_recommendation_factors"
    __table_args__ = (
        CheckConstraint(
            "category IN ('STRENGTH','RISK','CRITICAL_RISK','MISSING_EVIDENCE','REVIEW_REQUIRED','EXPERIMENTAL_CONTEXT')",
            name="category_valid",
        ),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        CheckConstraint(
            "severity IS NULL OR severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')",
            name="severity_valid",
        ),
        UniqueConstraint(
            "recommendation_preparation_id",
            "factor_code",
            "source_type",
            "source_reference_id",
            name="uq_credit_recommendation_factor",
        ),
        Index("ix_credit_recommendation_factors_preparation", "recommendation_preparation_id"),
        Index("ix_credit_recommendation_factors_category", "category"),
    )

    recommendation_preparation_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_recommendation_preparations.id", ondelete="CASCADE"), nullable=False
    )
    factor_code: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20))


class CreditRecommendationReviewItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_recommendation_review_items"
    __table_args__ = (
        CheckConstraint(
            "category IN ('DATA','FINANCIAL','CHARACTER','CAPACITY','CAPITAL','COLLATERAL','CONDITIONS','RESEARCH','EXPERIMENTAL')",
            name="category_valid",
        ),
        UniqueConstraint(
            "recommendation_preparation_id", "review_code", name="uq_credit_recommendation_review"
        ),
        Index("ix_credit_recommendation_reviews_preparation", "recommendation_preparation_id"),
    )

    recommendation_preparation_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_recommendation_preparations.id", ondelete="CASCADE"), nullable=False
    )
    review_code: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_type: Mapped[str | None] = mapped_column(String(50))
    source_reference_id: Mapped[UUID | None] = mapped_column()
