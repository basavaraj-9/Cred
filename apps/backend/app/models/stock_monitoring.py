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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class StockMonitoringRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_monitoring_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','PARTIAL','INSUFFICIENT_DATA','FAILED')",
            name="status_valid",
        ),
        CheckConstraint(
            "overall_health_status IN ('HEALTHY','WATCH','REVIEW_REQUIRED','INSUFFICIENT_DATA')",
            name="health_valid",
        ),
        CheckConstraint(
            "recalibration_readiness_status IN "
            "('NOT_INDICATED','MONITOR','RESEARCH_REVIEW_RECOMMENDED',"
            "'INSUFFICIENT_DATA')",
            name="readiness_valid",
        ),
        CheckConstraint(
            "comparability_status IN ('COMPARABLE','PARTIALLY_COMPARABLE','INCOMPARABLE')",
            name="comparability_valid",
        ),
        UniqueConstraint("input_hash", name="uq_stock_monitoring_input_hash"),
        Index(
            "ix_stock_monitoring_windows",
            "reference_start_date",
            "reference_end_date",
            "current_start_date",
            "current_end_date",
        ),
        Index(
            "ix_stock_monitoring_status",
            "status",
            "overall_health_status",
            "recalibration_readiness_status",
        ),
    )
    monitoring_version: Mapped[str] = mapped_column(String(100), nullable=False)
    drift_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    governance_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    window_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    recalibration_readiness_version: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_universe_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_universe_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_member_count: Mapped[int] = mapped_column(Integer, nullable=False)
    comparability_status: Mapped[str] = mapped_column(String(30), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    overall_health_status: Mapped[str] = mapped_column(String(30), nullable=False)
    recalibration_readiness_status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StockMonitoringFinding(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_monitoring_findings"
    __table_args__ = (
        Index("ix_stock_monitoring_finding_category", "monitoring_run_id", "category", "severity"),
        CheckConstraint("severity IN ('INFO','LOW','MODERATE','HIGH')", name="severity_valid"),
        CheckConstraint(
            "status IN ('OBSERVED','WATCH','REVIEW_REQUIRED','INSUFFICIENT_DATA')",
            name="status_valid",
        ),
    )
    monitoring_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_monitoring_runs.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_name: Mapped[str | None] = mapped_column(String(120))
    reference_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    delta: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    drift_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockFeatureDrift(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_feature_drift"
    __table_args__ = (
        UniqueConstraint("monitoring_run_id", "feature_name", name="uq_stock_feature_drift"),
        Index("ix_stock_feature_drift_feature", "feature_name"),
        CheckConstraint("psi IS NULL OR psi >= 0", name="psi_nonnegative"),
        CheckConstraint("severity IN ('INFO','LOW','MODERATE','HIGH')", name="severity_valid"),
    )
    monitoring_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_monitoring_runs.id", ondelete="CASCADE"), nullable=False
    )
    feature_name: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_mean: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    current_mean: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    reference_std: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    current_std: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    psi: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    psi_bin_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ks_statistic: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    ks_pvalue: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    reference_missing_rate: Mapped[Decimal] = mapped_column(Numeric(16, 10), nullable=False)
    current_missing_rate: Mapped[Decimal] = mapped_column(Numeric(16, 10), nullable=False)
    missing_rate_delta: Mapped[Decimal] = mapped_column(Numeric(16, 10), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockModelMonitoring(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_model_monitoring"
    __table_args__ = (Index("ix_stock_model_monitoring_model", "model_name", "model_version"),)
    monitoring_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_monitoring_runs.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_prediction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_prediction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_probability_mean: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_probability_mean: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    reference_probability_median: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_probability_median: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    reference_probability_std: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_probability_std: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    reference_probability_min: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_probability_min: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    reference_probability_max: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_probability_max: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    probability_psi: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    reference_positive_rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_positive_rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    diagnostic_metric_name: Mapped[str | None] = mapped_column(String(80))
    reference_metric: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    current_metric: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    metric_delta: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    maturity_status: Mapped[str] = mapped_column(String(30), nullable=False)
    comparability_status: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockScoreMonitoring(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_score_monitoring"
    __table_args__ = (
        CheckConstraint("score_psi IS NULL OR score_psi >= 0", name="psi_nonnegative"),
    )
    monitoring_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_monitoring_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score_version: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_mean: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_mean: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    reference_median: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_median: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    reference_std: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_std: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    reference_min: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_min: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    reference_max: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_max: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    score_psi: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    confidence_reference_mean: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    confidence_current_mean: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    confidence_reference_median: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    confidence_current_median: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    confidence_reference_below_rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    confidence_current_below_rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    coverage_reference_mean: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    coverage_current_mean: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    coverage_reference_median: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    coverage_current_median: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    coverage_reference_below_rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    coverage_current_below_rate: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    band_distribution_reference: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    band_distribution_current: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockComponentMonitoring(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_component_monitoring"
    __table_args__ = (
        UniqueConstraint(
            "monitoring_run_id", "component_name", name="uq_stock_component_monitoring"
        ),
        Index("ix_stock_component_monitoring_component", "component_name"),
    )
    monitoring_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_monitoring_runs.id", ondelete="CASCADE"), nullable=False
    )
    component_name: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_mean: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    current_mean: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    psi: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    availability_reference: Mapped[Decimal] = mapped_column(Numeric(16, 10), nullable=False)
    availability_current: Mapped[Decimal] = mapped_column(Numeric(16, 10), nullable=False)
    availability_delta: Mapped[Decimal] = mapped_column(Numeric(16, 10), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockRankingMonitoring(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ranking_monitoring"
    __table_args__ = (
        CheckConstraint(
            "rank_spearman IS NULL OR rank_spearman BETWEEN -1 AND 1",
            name="rank_spearman_range",
        ),
        CheckConstraint(
            "top_k_overlap IS NULL OR top_k_overlap BETWEEN 0 AND 1",
            name="top_k_overlap_range",
        ),
        CheckConstraint(
            "turnover IS NULL OR turnover BETWEEN 0 AND 1",
            name="turnover_range",
        ),
    )
    monitoring_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_monitoring_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reference_ranking_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ranking_runs.id"), nullable=False
    )
    current_ranking_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ranking_runs.id"), nullable=False
    )
    common_company_count: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    rank_spearman: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    top_k_overlap: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    mean_absolute_rank_change: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    turnover: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockProviderMonitoring(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_provider_monitoring"
    __table_args__ = (
        Index("ix_stock_provider_monitoring_type", "provider_type"),
        CheckConstraint(
            "freshness_status IN ('CURRENT','AGING','STALE','MISSING')",
            name="freshness_status_valid",
        ),
        CheckConstraint(
            "provider_classification IN ('DEVELOPMENT','LIVE')",
            name="provider_classification_valid",
        ),
    )
    monitoring_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_monitoring_runs.id", ondelete="CASCADE"), nullable=False
    )
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_classification: Mapped[str] = mapped_column(String(20), nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    freshness_age_days: Mapped[int | None] = mapped_column(Integer)
    freshness_status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockGovernanceAssessment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_governance_assessments"
    __table_args__ = (UniqueConstraint("monitoring_run_id", name="uq_stock_governance_run"),)
    monitoring_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_monitoring_runs.id", ondelete="CASCADE"), nullable=False
    )
    health_status: Mapped[str] = mapped_column(String(30), nullable=False)
    recalibration_readiness_status: Mapped[str] = mapped_column(String(50), nullable=False)
    high_severity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    moderate_severity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    stale_provider_count: Mapped[int] = mapped_column(Integer, nullable=False)
    high_drift_feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_drift_count: Mapped[int] = mapped_column(Integer, nullable=False)
    score_drift_status: Mapped[str] = mapped_column(String(40), nullable=False)
    ranking_stability_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reasons_for_review: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reasons_against_review: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    insufficient_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
