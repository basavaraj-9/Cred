from __future__ import annotations

# ruff: noqa: E501
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CreditFusionExperiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_fusion_experiments"
    __table_args__ = (
        UniqueConstraint(
            "credit_assessment_id",
            "ml_model_id",
            "input_hash",
            "policy_version",
            "strategy",
            name="uq_credit_fusion_experiment_input",
        ),
        Index("ix_credit_fusion_experiments_document_id", "document_id"),
        Index("ix_credit_fusion_experiments_status", "status"),
        CheckConstraint(
            "rule_score IS NULL OR (rule_score >= 0 AND rule_score <= 100)", name="rule_score_range"
        ),
        CheckConstraint(
            "rule_risk_index IS NULL OR (rule_risk_index >= 0 AND rule_risk_index <= 1)",
            name="rule_risk_index_range",
        ),
        CheckConstraint(
            "ml_probability IS NULL OR (ml_probability >= 0 AND ml_probability <= 1)",
            name="ml_probability_range",
        ),
        CheckConstraint(
            "rule_weight >= 0 AND rule_weight <= 1 AND ml_weight >= 0 AND ml_weight <= 1",
            name="weights_range",
        ),
        CheckConstraint("rule_weight + ml_weight = 1", name="weights_sum_to_one"),
        CheckConstraint("strategy IN ('WEIGHTED_BLEND', 'CONSENSUS_GATED')", name="strategy_valid"),
        CheckConstraint(
            "mode IN ('DISABLED', 'EXPERIMENTAL', 'FUTURE_PRODUCTION')", name="mode_valid"
        ),
        CheckConstraint(
            "status IN ('EXPERIMENTAL_RESULT', 'RULE_ONLY_FALLBACK', 'REVIEW_REQUIRED', "
            "'INSUFFICIENT_DATA', 'BLOCKED_BY_READINESS', 'BLOCKED_BY_DRIFT', "
            "'BLOCKED_BY_DISAGREEMENT', 'BLOCKED_BY_ARTIFACT_INTEGRITY', "
            "'NO_RELIABLE_OUTPUT')",
            name="status_valid",
        ),
        CheckConstraint(
            "experimental_hybrid_risk_index IS NULL OR (experimental_hybrid_risk_index >= 0 AND experimental_hybrid_risk_index <= 1)",
            name="hybrid_risk_range",
        ),
        CheckConstraint(
            "fusion_confidence >= 0 AND fusion_confidence <= 1", name="fusion_confidence_range"
        ),
    )

    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    credit_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_assessments.id"), nullable=False
    )
    ml_model_id: Mapped[UUID | None] = mapped_column(ForeignKey("ml_models.id"))
    feature_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_ml_feature_snapshots.id")
    )
    evaluation_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_ml_evaluation_runs.id")
    )
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rule_risk_index: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    ml_probability: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    rule_weight: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    ml_weight: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    experimental_hybrid_risk_index: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    experimental_strength_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    experimental_band: Mapped[str | None] = mapped_column(String(60))
    rule_ml_gap: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    fusion_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    production_use_permitted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    fusion_not_executed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    fallback_source: Mapped[str | None] = mapped_column(String(60))
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_band_version: Mapped[str] = mapped_column(String(100), nullable=False)
    fusion_engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    readiness_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class CreditFusionContribution(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_fusion_contributions"
    __table_args__ = (
        UniqueConstraint(
            "fusion_experiment_id", "contribution_type", name="uq_credit_fusion_contribution_type"
        ),
        Index("ix_credit_fusion_contributions_experiment_id", "fusion_experiment_id"),
        CheckConstraint("weight >= 0 AND weight <= 1", name="weight_range"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence_range"
        ),
    )

    fusion_experiment_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_fusion_experiments.id", ondelete="CASCADE"), nullable=False
    )
    contribution_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    raw_value: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    normalized_value: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    weighted_contribution: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditFusionReason(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_fusion_reasons"
    __table_args__ = (Index("ix_credit_fusion_reasons_experiment_id", "fusion_experiment_id"),)

    fusion_experiment_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_fusion_experiments.id", ondelete="CASCADE"), nullable=False
    )
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    impact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(30))
    source_reference_type: Mapped[str | None] = mapped_column(String(60))
    source_reference_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditFusionInput(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_fusion_inputs"
    __table_args__ = (
        UniqueConstraint("fusion_experiment_id", "input_role", name="uq_credit_fusion_input_role"),
        Index("ix_credit_fusion_inputs_experiment_id", "fusion_experiment_id"),
    )

    fusion_experiment_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_fusion_experiments.id", ondelete="CASCADE"), nullable=False
    )
    credit_assessment_id: Mapped[UUID | None] = mapped_column(ForeignKey("credit_assessments.id"))
    ml_model_id: Mapped[UUID | None] = mapped_column(ForeignKey("ml_models.id"))
    feature_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_ml_feature_snapshots.id")
    )
    evaluation_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_ml_evaluation_runs.id")
    )
    ml_prediction_reference: Mapped[str | None] = mapped_column(String(200))
    input_role: Mapped[str] = mapped_column(String(60), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
