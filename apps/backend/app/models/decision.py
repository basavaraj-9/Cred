from __future__ import annotations

# ruff: noqa: E501
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import FinancialScope


class CreditDecisionSupport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_decision_support"
    __table_args__ = (
        CheckConstraint(
            "system_recommendation IN ('FAVORABLE_REVIEW','CONDITIONAL_REVIEW','MANUAL_REVIEW_REQUIRED','ADVERSE_REVIEW','INSUFFICIENT_EVIDENCE','POLICY_EXCEPTION_REVIEW')",
            name="recommendation_valid",
        ),
        CheckConstraint(
            "human_decision IS NULL OR human_decision IN ('APPROVED','DECLINED','RETURNED_FOR_INFORMATION')",
            name="human_decision_valid",
        ),
        CheckConstraint(
            "confidence_score BETWEEN 0 AND 1 AND completeness_score BETWEEN 0 AND 1",
            name="scores_range",
        ),
        CheckConstraint(
            "blocking_gate_count >= 0 AND review_gate_count >= 0 AND exception_count >= 0",
            name="counts_nonnegative",
        ),
        UniqueConstraint(
            "document_id",
            "statement_scope",
            "recommendation_preparation_id",
            "input_hash",
            "policy_version",
            "engine_version",
            name="uq_credit_decision_input",
        ),
        Index("ix_credit_decision_document_scope", "document_id", "statement_scope", "created_at"),
        Index("ix_credit_decision_recommendation", "system_recommendation"),
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
    recommendation_preparation_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_recommendation_preparations.id"), nullable=False
    )
    research_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("research_runs.id"))
    fusion_experiment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_fusion_experiments.id")
    )
    statement_scope: Mapped[FinancialScope] = mapped_column(
        SAEnum(FinancialScope, native_enum=False, create_constraint=True), nullable=False
    )
    system_recommendation: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False)
    blocking_gate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    review_gate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    exception_count: Mapped[int] = mapped_column(Integer, nullable=False)
    production_ml_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    summary_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    human_decision: Mapped[str | None] = mapped_column(String(40))


class CreditDecisionGate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_decision_gates"
    __table_args__ = (
        CheckConstraint(
            "category IN ('FINANCIAL','REPAYMENT_CAPACITY','CAPITAL','COLLATERAL','CHARACTER_RESEARCH','CONDITIONS','LEGAL_REGULATORY','DATA_QUALITY','RESEARCH_COVERAGE','POLICY_EXCEPTION')",
            name="category_valid",
        ),
        CheckConstraint(
            "status IN ('PASS','PASS_WITH_REVIEW','FAIL_REVIEW','INSUFFICIENT_DATA','CONFLICTING')",
            name="status_valid",
        ),
        CheckConstraint(
            "severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')", name="severity_valid"
        ),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="confidence_range"),
        UniqueConstraint("credit_decision_support_id", "gate_code", name="uq_credit_decision_gate"),
        Index("ix_credit_decision_gates_support", "credit_decision_support_id"),
    )
    credit_decision_support_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_decision_support.id", ondelete="CASCADE"), nullable=False
    )
    gate_code: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exception_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(60))
    source_reference_id: Mapped[UUID | None] = mapped_column()


class CreditPolicyException(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_policy_exceptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN','WAIVED','APPROVED_BY_HUMAN','REJECTED_BY_HUMAN','MORE_INFORMATION_REQUIRED','REFERRED_TO_HIGHER_AUTHORITY')",
            name="status_valid",
        ),
        UniqueConstraint(
            "credit_decision_support_id", "exception_code", name="uq_credit_policy_exception"
        ),
        Index("ix_credit_policy_exceptions_support", "credit_decision_support_id"),
    )
    credit_decision_support_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_decision_support.id", ondelete="CASCADE"), nullable=False
    )
    exception_code: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    required_authority: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN")
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_type: Mapped[str | None] = mapped_column(String(60))
    source_reference_id: Mapped[UUID | None] = mapped_column()


class CreditDecisionReviewItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_decision_review_items"
    __table_args__ = (
        CheckConstraint("priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="priority_valid"),
        UniqueConstraint(
            "credit_decision_support_id", "review_code", name="uq_credit_decision_review"
        ),
        Index("ix_credit_decision_reviews_support", "credit_decision_support_id"),
    )
    credit_decision_support_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_decision_support.id", ondelete="CASCADE"), nullable=False
    )
    review_code: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_type: Mapped[str | None] = mapped_column(String(60))
    source_reference_id: Mapped[UUID | None] = mapped_column()


class CreditLimitPreparation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_limit_preparations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('AVAILABLE','PARTIAL','UNAVAILABLE','NEEDS_REVIEW')", name="status_valid"
        ),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="confidence_range"),
        CheckConstraint("lower_bound IS NULL OR lower_bound >= 0", name="lower_nonnegative"),
        CheckConstraint("upper_bound IS NULL OR upper_bound >= 0", name="upper_nonnegative"),
        CheckConstraint(
            "analytical_ceiling IS NULL OR analytical_ceiling >= 0", name="ceiling_nonnegative"
        ),
        UniqueConstraint("credit_decision_support_id", name="uq_credit_limit_support"),
    )
    credit_decision_support_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_decision_support.id", ondelete="CASCADE"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    lower_bound: Mapped[Decimal | None] = mapped_column(Numeric(38, 2))
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(38, 2))
    analytical_ceiling: Mapped[Decimal | None] = mapped_column(Numeric(38, 2))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    method_count: Mapped[int] = mapped_column(Integer, nullable=False)
    existing_exposure_status: Mapped[str] = mapped_column(String(50), nullable=False)
    projected_ratios_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )


class CreditLimitMethod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_limit_methods"
    __table_args__ = (
        CheckConstraint(
            "status IN ('AVAILABLE','UNAVAILABLE','BLOCKED','NEEDS_REVIEW')", name="status_valid"
        ),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="confidence_range"),
        CheckConstraint(
            "calculated_limit IS NULL OR calculated_limit >= 0", name="limit_nonnegative"
        ),
        UniqueConstraint(
            "credit_decision_support_id", "method_code", name="uq_credit_limit_method"
        ),
        Index("ix_credit_limit_methods_support", "credit_decision_support_id"),
    )
    credit_decision_support_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_decision_support.id", ondelete="CASCADE"), nullable=False
    )
    method_code: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    calculated_limit: Mapped[Decimal | None] = mapped_column(Numeric(38, 2))
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    formula_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_summary_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
