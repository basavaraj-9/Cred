from __future__ import annotations

# ruff: noqa: E501
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CreditMLEvaluationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_ml_evaluation_runs"
    __table_args__ = (
        UniqueConstraint("input_hash", name="uq_credit_ml_evaluation_runs_input_hash"),
        Index("ix_credit_ml_evaluation_runs_dataset_id", "dataset_id"),
        Index("ix_credit_ml_evaluation_runs_status", "status"),
        CheckConstraint("valid_window_count >= 0", name="valid_window_count_nonnegative"),
        CheckConstraint("skipped_window_count >= 0", name="skipped_window_count_nonnegative"),
    )

    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("ml_datasets.id"), nullable=False)
    evaluation_version: Mapped[str] = mapped_column(String(100), nullable=False)
    walk_forward_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_selection_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    fusion_readiness_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    drift_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    diagnostic_band_version: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    window_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_window_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_window_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    fusion_readiness: Mapped[str] = mapped_column(String(50), nullable=False)
    fusion_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreditMLEvaluationWindow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_ml_evaluation_windows"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", "window_number", name="uq_credit_ml_window_number"),
        Index("ix_credit_ml_windows_run_id", "evaluation_run_id"),
        CheckConstraint(
            "train_count >= 0 AND evaluation_count >= 0", name="window_counts_nonnegative"
        ),
    )

    evaluation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_ml_evaluation_runs.id", ondelete="CASCADE"), nullable=False
    )
    window_number: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    train_start: Mapped[date | None] = mapped_column(Date)
    train_end: Mapped[date | None] = mapped_column(Date)
    evaluation_start: Mapped[date | None] = mapped_column(Date)
    evaluation_end: Mapped[date | None] = mapped_column(Date)
    train_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    train_positive: Mapped[int] = mapped_column(Integer, nullable=False)
    train_negative: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluation_positive: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluation_negative: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditMLWindowModelResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_ml_window_model_results"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_window_id", "model_family", name="uq_credit_ml_window_model_family"
        ),
        Index("ix_credit_ml_window_results_window_id", "evaluation_window_id"),
    )

    evaluation_window_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_ml_evaluation_windows.id", ondelete="CASCADE"), nullable=False
    )
    model_family: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    calibration_method: Mapped[str] = mapped_column(String(50), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    metric_summary_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    artifact_uri: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditMLDriftResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_ml_drift_results"
    __table_args__ = (Index("ix_credit_ml_drift_window_id", "evaluation_window_id"),)

    evaluation_window_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_ml_evaluation_windows.id", ondelete="CASCADE"), nullable=False
    )
    feature_name: Mapped[str | None] = mapped_column(String(120))
    drift_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    threshold_version: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditRuleMLComparison(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_rule_ml_comparisons"
    __table_args__ = (
        Index("ix_credit_rule_ml_comparisons_run_id", "evaluation_run_id"),
        CheckConstraint("ml_probability >= 0 AND ml_probability <= 1", name="ml_probability_range"),
        CheckConstraint(
            "rule_risk_index IS NULL OR (rule_risk_index >= 0 AND rule_risk_index <= 1)",
            name="rule_risk_index_range",
        ),
    )

    evaluation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_ml_evaluation_runs.id", ondelete="CASCADE"), nullable=False
    )
    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_ml_observations.id"), nullable=False
    )
    credit_assessment_id: Mapped[UUID | None] = mapped_column(ForeignKey("credit_assessments.id"))
    ml_model_family: Mapped[str] = mapped_column(String(100), nullable=False)
    ml_probability: Mapped[float] = mapped_column(Float, nullable=False)
    ml_predicted_class: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_score: Mapped[float | None] = mapped_column(Float)
    rule_risk_index: Mapped[float | None] = mapped_column(Float)
    rule_risk_band: Mapped[str | None] = mapped_column(String(50))
    ml_diagnostic_band: Mapped[str] = mapped_column(String(50), nullable=False)
    agreement_status: Mapped[str] = mapped_column(String(50), nullable=False)
    probability_gap: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
