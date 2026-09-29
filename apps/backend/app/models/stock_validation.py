from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin

VALIDATION_STATUSES = "'PENDING','RUNNING','COMPLETED','PARTIAL','INSUFFICIENT_DATA','FAILED'"


class StockIntelligenceValidationRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_validation_runs"
    __table_args__ = (
        CheckConstraint(f"status IN ({VALIDATION_STATUSES})", name="status_valid"),
        CheckConstraint(
            "result_status IN ('INSUFFICIENT_DATA','PIPELINE_VALIDATED',"
            "'RESEARCH_DIAGNOSTICS_AVAILABLE')",
            name="result_status_valid",
        ),
        UniqueConstraint("input_hash", name="uq_stock_validation_input_hash"),
        Index("ix_stock_validation_dates", "start_date", "end_date"),
        Index("ix_stock_validation_version", "validation_version"),
    )
    validation_version: Mapped[str] = mapped_column(String(100), nullable=False)
    validation_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    ablation_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    robustness_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    score_version: Mapped[str] = mapped_column(String(100), nullable=False)
    label_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    result_status: Mapped[str] = mapped_column(String(50), nullable=False)
    historical_date_count: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    censored_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mean_spearman: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    median_spearman: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    mean_top_bottom_spread: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StockIntelligenceValidationPeriod(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_validation_periods"
    __table_args__ = (
        UniqueConstraint("validation_run_id", "as_of_date", name="uq_stock_validation_period"),
        Index("ix_stock_validation_period_run", "validation_run_id"),
    )
    validation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_validation_runs.id", ondelete="CASCADE"), nullable=False
    )
    ranking_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ranking_runs.id"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    eligible_company_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bucket_method: Mapped[str] = mapped_column(String(20), nullable=False)
    spearman: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    kendall: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    top_bottom_spread: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    top_bucket_hit_rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    monotonicity_score: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    monotonicity_status: Mapped[str] = mapped_column(String(30), nullable=False)
    mean_score: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    median_score: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    score_std: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    mean_confidence: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    mean_coverage: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockIntelligenceValidationMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_validation_members"
    __table_args__ = (
        UniqueConstraint(
            "validation_run_id",
            "dataset_row_id",
            name="uq_stock_validation_member",
        ),
        Index("ix_stock_validation_member_period", "validation_period_id"),
    )
    validation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_validation_runs.id", ondelete="CASCADE"), nullable=False
    )
    validation_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_validation_periods.id", ondelete="CASCADE"), nullable=False
    )
    dataset_row_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_dataset_rows.id"), nullable=False
    )
    score_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_runs.id"), nullable=False
    )
    ranking_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ranking_runs.id"), nullable=False
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False
    )
    stock_listing_id: Mapped[UUID] = mapped_column(ForeignKey("stock_listings.id"), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    coverage: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    percentile: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    future_relative_return: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    future_rank_target: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    label_class: Mapped[str] = mapped_column(String(20), nullable=False)
    label_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockIntelligenceValidationBucket(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_validation_buckets"
    __table_args__ = (
        UniqueConstraint("validation_period_id", "bucket_name", name="uq_stock_validation_bucket"),
    )
    validation_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_validation_periods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bucket_name: Mapped[str] = mapped_column(String(20), nullable=False)
    bucket_order: Mapped[int] = mapped_column(Integer, nullable=False)
    company_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mean_relative_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    median_relative_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    positive_rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    std_relative_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    minimum_relative_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    maximum_relative_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockIntelligenceComponentValidation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_component_validation"
    __table_args__ = (
        UniqueConstraint(
            "validation_run_id", "component_name", name="uq_stock_component_validation"
        ),
    )
    validation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_validation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_name: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_period_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mean_spearman: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    median_spearman: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    std_spearman: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    minimum_spearman: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    maximum_spearman: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockIntelligenceComponentCorrelation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_component_correlations"
    __table_args__ = (
        UniqueConstraint(
            "validation_run_id", "component_a", "component_b", name="uq_stock_component_correlation"
        ),
    )
    validation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_validation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_a: Mapped[str] = mapped_column(String(40), nullable=False)
    component_b: Mapped[str] = mapped_column(String(40), nullable=False)
    correlation: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    redundancy_status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockIntelligenceAblationRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_ablation_runs"
    __table_args__ = (
        CheckConstraint(f"status IN ({VALIDATION_STATUSES})", name="status_valid"),
        UniqueConstraint("input_hash", name="uq_stock_ablation_input_hash"),
    )
    validation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_validation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    experiment_name: Mapped[str] = mapped_column(String(80), nullable=False)
    ablation_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    removed_components_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    weights_json: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockIntelligenceAblationMetric(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_ablation_metrics"
    __table_args__ = (
        UniqueConstraint("ablation_run_id", "metric_name", name="uq_stock_ablation_metric"),
    )
    ablation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_ablation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(String(80), nullable=False)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    valid_period_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockIntelligenceSensitivityRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_sensitivity_runs"
    __table_args__ = (
        UniqueConstraint("validation_run_id", "experiment_name", name="uq_stock_sensitivity_run"),
    )
    validation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_validation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    experiment_name: Mapped[str] = mapped_column(String(80), nullable=False)
    robustness_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    weights_json: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    baseline_rank_correlation: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    top_k_overlap: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    mean_absolute_rank_change: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    spearman_delta: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    spread_delta: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockIntelligenceSegmentValidation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_segment_validation"
    __table_args__ = (
        UniqueConstraint(
            "validation_run_id", "segment_type", "segment_value", name="uq_stock_segment_validation"
        ),
    )
    validation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_validation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    segment_value: Mapped[str] = mapped_column(String(120), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    period_count: Mapped[int] = mapped_column(Integer, nullable=False)
    spearman: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    top_bottom_spread: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    top_bucket_hit_rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    mean_relative_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    median_relative_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    std_relative_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    positive_rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
