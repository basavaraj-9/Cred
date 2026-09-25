from __future__ import annotations

# ruff: noqa: E501
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    AnomalySeverity,
    AnomalyStatus,
    ChangeType,
    FinancialScope,
    TrendDirection,
    TrendMetricSourceType,
    TrendStatus,
    TrendStrength,
)


class FinancialTrendRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_trend_runs"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "input_hash",
            "trend_calculator_version",
            "anomaly_rule_version",
            name="uq_financial_trend_runs_input",
        ),
        Index("ix_financial_trend_runs_document_id", "document_id"),
    )

    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    financial_analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_analysis_runs.id"), nullable=False
    )
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    trend_calculator_version: Mapped[str] = mapped_column(String(100), nullable=False)
    anomaly_rule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    trend_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FinancialTrend(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_trends"
    __table_args__ = (
        CheckConstraint("period_count >= 1", name="period_count_positive"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        UniqueConstraint(
            "run_id",
            "statement_scope",
            "metric_source_type",
            "metric_name",
            "currency",
            name="uq_financial_trends_run_scope_source_metric_currency",
        ),
        Index(
            "ix_financial_trends_document_scope_metric",
            "document_id",
            "statement_scope",
            "metric_name",
        ),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("financial_trend_runs.id"), nullable=False)
    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    statement_scope: Mapped[FinancialScope] = mapped_column(
        SAEnum(FinancialScope, native_enum=False, create_constraint=True), nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_source_type: Mapped[TrendMetricSourceType] = mapped_column(
        SAEnum(TrendMetricSourceType, native_enum=False, create_constraint=True), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="N/A")
    start_fiscal_year: Mapped[str] = mapped_column(String(20), nullable=False)
    end_fiscal_year: Mapped[str] = mapped_column(String(20), nullable=False)
    period_count: Mapped[int] = mapped_column(Integer, nullable=False)
    start_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    end_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    absolute_change: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    percentage_change: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    cagr: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    percentage_point_change: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    change_type: Mapped[ChangeType] = mapped_column(
        SAEnum(ChangeType, native_enum=False, create_constraint=True), nullable=False
    )
    state_transition: Mapped[str | None] = mapped_column(String(30))
    trend_direction: Mapped[TrendDirection] = mapped_column(
        SAEnum(TrendDirection, native_enum=False, create_constraint=True), nullable=False
    )
    trend_strength: Mapped[TrendStrength | None] = mapped_column(
        SAEnum(TrendStrength, native_enum=False, create_constraint=True)
    )
    status: Mapped[TrendStatus] = mapped_column(
        SAEnum(TrendStatus, native_enum=False, create_constraint=True), nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    series: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    missing_periods: Mapped[list[str] | None] = mapped_column(JSONB)
    calculator_version: Mapped[str] = mapped_column(String(100), nullable=False)


class FinancialTrendInput(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_trend_inputs"
    __table_args__ = (
        CheckConstraint(
            "(normalized_financial_value_id IS NOT NULL) <> (financial_ratio_id IS NOT NULL)",
            name="exactly_one_source",
        ),
        UniqueConstraint(
            "financial_trend_id",
            "normalized_financial_value_id",
            "financial_ratio_id",
            "input_role",
            name="uq_financial_trend_inputs_source_role",
        ),
        Index("ix_financial_trend_inputs_trend_id", "financial_trend_id"),
    )

    financial_trend_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_trends.id"), nullable=False
    )
    normalized_financial_value_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("normalized_financial_values.id")
    )
    financial_ratio_id: Mapped[UUID | None] = mapped_column(ForeignKey("financial_ratios.id"))
    input_role: Mapped[str] = mapped_column(String(100), nullable=False)
    fiscal_year: Mapped[str] = mapped_column(String(20), nullable=False)


class FinancialAnomaly(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_anomalies"
    __table_args__ = (
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        UniqueConstraint(
            "run_id",
            "statement_scope",
            "anomaly_type",
            "start_fiscal_year",
            "end_fiscal_year",
            name="uq_financial_anomalies_run_scope_type_period",
        ),
        Index(
            "ix_financial_anomalies_document_scope_severity",
            "document_id",
            "statement_scope",
            "severity",
        ),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("financial_trend_runs.id"), nullable=False)
    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    statement_scope: Mapped[FinancialScope] = mapped_column(
        SAEnum(FinancialScope, native_enum=False, create_constraint=True), nullable=False
    )
    anomaly_type: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[AnomalySeverity] = mapped_column(
        SAEnum(AnomalySeverity, native_enum=False, create_constraint=True), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    start_fiscal_year: Mapped[str] = mapped_column(String(20), nullable=False)
    end_fiscal_year: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[AnomalyStatus] = mapped_column(
        SAEnum(AnomalyStatus, native_enum=False, create_constraint=True), nullable=False
    )
    persistence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rule_version: Mapped[str] = mapped_column(String(100), nullable=False)


class FinancialAnomalyInput(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_anomaly_inputs"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(financial_trend_id, normalized_financial_value_id, financial_ratio_id) = 1",
            name="exactly_one_source",
        ),
        UniqueConstraint(
            "financial_anomaly_id",
            "financial_trend_id",
            "normalized_financial_value_id",
            "financial_ratio_id",
            "input_role",
            name="uq_financial_anomaly_inputs_source_role",
        ),
        Index("ix_financial_anomaly_inputs_anomaly_id", "financial_anomaly_id"),
    )

    financial_anomaly_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_anomalies.id"), nullable=False
    )
    financial_trend_id: Mapped[UUID | None] = mapped_column(ForeignKey("financial_trends.id"))
    normalized_financial_value_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("normalized_financial_values.id")
    )
    financial_ratio_id: Mapped[UUID | None] = mapped_column(ForeignKey("financial_ratios.id"))
    input_role: Mapped[str] = mapped_column(String(100), nullable=False)
