from __future__ import annotations

# ruff: noqa: E501
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    CreditAssessmentStatus,
    CreditComponent,
    CreditReasonType,
    CreditRiskBand,
    FinancialScope,
)


class CreditAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_assessments"
    __table_args__ = (
        CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)",
            name="overall_score_range",
        ),
        CheckConstraint(
            "component_coverage >= 0 AND component_coverage <= 1", name="component_coverage_range"
        ),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        CheckConstraint(
            "(overall_score IS NULL AND risk_band IS NULL) OR (overall_score IS NOT NULL AND risk_band IS NOT NULL)",
            name="score_band_consistency",
        ),
        UniqueConstraint(
            "document_id",
            "statement_scope",
            "input_hash",
            "policy_version",
            "feature_builder_version",
            "score_engine_version",
            name="uq_credit_assessments_input",
        ),
        Index("ix_credit_assessments_document_scope", "document_id", "statement_scope"),
    )

    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    financial_analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_analysis_runs.id"), nullable=False
    )
    financial_trend_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_trend_runs.id"), nullable=False
    )
    statement_scope: Mapped[FinancialScope] = mapped_column(
        SAEnum(FinancialScope, native_enum=False, create_constraint=True), nullable=False
    )
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    risk_band: Mapped[CreditRiskBand | None] = mapped_column(
        SAEnum(CreditRiskBand, native_enum=False, create_constraint=True)
    )
    component_coverage: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    status: Mapped[CreditAssessmentStatus] = mapped_column(
        SAEnum(CreditAssessmentStatus, native_enum=False, create_constraint=True), nullable=False
    )
    feature_builder_version: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    score_engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class CreditAssessmentInput(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_assessment_inputs"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(normalized_financial_value_id, financial_ratio_id, financial_trend_id, financial_anomaly_id, company_profile_id, domain_classification_id) = 1",
            name="exactly_one_source",
        ),
        UniqueConstraint(
            "credit_assessment_id", "input_role", name="uq_credit_assessment_inputs_role"
        ),
        Index("ix_credit_assessment_inputs_assessment_id", "credit_assessment_id"),
    )

    credit_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_assessments.id"), nullable=False
    )
    normalized_financial_value_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("normalized_financial_values.id")
    )
    financial_ratio_id: Mapped[UUID | None] = mapped_column(ForeignKey("financial_ratios.id"))
    financial_trend_id: Mapped[UUID | None] = mapped_column(ForeignKey("financial_trends.id"))
    financial_anomaly_id: Mapped[UUID | None] = mapped_column(ForeignKey("financial_anomalies.id"))
    company_profile_id: Mapped[UUID | None] = mapped_column(ForeignKey("company_profiles.id"))
    domain_classification_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("domain_classifications.id")
    )
    input_role: Mapped[str] = mapped_column(String(120), nullable=False)


class CreditSubscore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_subscores"
    __table_args__ = (
        CheckConstraint("raw_score >= 0 AND raw_score <= 100", name="raw_score_range"),
        CheckConstraint("max_score = 100", name="max_score_expected"),
        CheckConstraint(
            "normalized_score >= 0 AND normalized_score <= 100", name="normalized_score_range"
        ),
        CheckConstraint("weight >= 0 AND weight <= 1", name="weight_range"),
        CheckConstraint(
            "weighted_score IS NULL OR (weighted_score >= 0 AND weighted_score <= 100)",
            name="weighted_score_range",
        ),
        CheckConstraint("coverage_ratio >= 0 AND coverage_ratio <= 1", name="coverage_range"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        UniqueConstraint(
            "credit_assessment_id",
            "component_name",
            name="uq_credit_subscores_assessment_component",
        ),
        Index("ix_credit_subscores_assessment_id", "credit_assessment_id"),
    )

    credit_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_assessments.id"), nullable=False
    )
    component_name: Mapped[CreditComponent] = mapped_column(
        SAEnum(CreditComponent, native_enum=False, create_constraint=True), nullable=False
    )
    raw_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    max_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=100)
    normalized_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    weighted_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    status: Mapped[CreditAssessmentStatus] = mapped_column(
        SAEnum(CreditAssessmentStatus, native_enum=False, create_constraint=True), nullable=False
    )


class CreditRuleResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_rule_results"
    __table_args__ = (
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        UniqueConstraint(
            "credit_assessment_id", "rule_code", name="uq_credit_rule_results_assessment_code"
        ),
        Index("ix_credit_rule_results_assessment_type", "credit_assessment_id", "reason_type"),
    )

    credit_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_assessments.id"), nullable=False
    )
    credit_assessment_input_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_assessment_inputs.id")
    )
    component: Mapped[CreditComponent] = mapped_column(
        SAEnum(CreditComponent, native_enum=False, create_constraint=True), nullable=False
    )
    rule_code: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_metric: Mapped[str] = mapped_column(String(120), nullable=False)
    input_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    input_status: Mapped[str] = mapped_column(String(30), nullable=False)
    score_impact: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    max_score_impact: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    reason_type: Mapped[CreditReasonType] = mapped_column(
        SAEnum(CreditReasonType, native_enum=False, create_constraint=True), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[CreditAssessmentStatus] = mapped_column(
        SAEnum(CreditAssessmentStatus, native_enum=False, create_constraint=True), nullable=False
    )
