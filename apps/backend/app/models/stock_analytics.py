from __future__ import annotations

# ruff: noqa: E501
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

RUN_STATUS = "status IN ('PENDING','PROCESSING','COMPLETED','PARTIAL','FAILED','NEEDS_REVIEW')"
VALUE_STATUS = "status IN ('AVAILABLE','UNAVAILABLE','INSUFFICIENT_INPUTS','INVALID_DENOMINATOR','NOT_MEANINGFUL','NEEDS_REVIEW','INSUFFICIENT_HISTORY','INSUFFICIENT_GROUP_SIZE','INVALID_INPUT')"


class StockFundamentalRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stock_fundamental_runs"
    __table_args__ = (
        CheckConstraint(RUN_STATUS, name="status_valid"),
        UniqueConstraint(
            "listed_company_id",
            "provider",
            "provider_version",
            "statement_scope",
            "period_end",
            "input_hash",
            name="uq_stock_fundamental_run_input",
        ),
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(100), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    statement_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    reporting_period: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    availability_date: Mapped[date | None] = mapped_column(Date)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StockFundamental(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_fundamentals"
    __table_args__ = (
        UniqueConstraint("fundamental_run_id", "metric_code", name="uq_stock_fundamental_metric"),
    )
    fundamental_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_fundamental_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False
    )
    metric_code: Mapped[str] = mapped_column(String(60), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    raw_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    raw_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10))
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    availability_date: Mapped[date | None] = mapped_column(Date)
    statement_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    provenance_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    normalization_version: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockValuationRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_valuation_runs"
    __table_args__ = (
        UniqueConstraint(
            "stock_listing_id",
            "valuation_date",
            "policy_version",
            "input_hash",
            name="uq_stock_valuation_input",
        ),
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False
    )
    stock_listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_listings.id"), nullable=False, index=True
    )
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    fundamental_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_fundamental_runs.id"))
    price_record_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_prices.id"))
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockValuation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_valuations"
    __table_args__ = (
        CheckConstraint(VALUE_STATUS, name="status_valid"),
        UniqueConstraint("valuation_run_id", "metric_code", name="uq_stock_valuation_metric"),
    )
    valuation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_valuation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_code: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockValuationInput(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_valuation_inputs"
    stock_valuation_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_valuations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(nullable=False)
    input_name: Mapped[str] = mapped_column(String(80), nullable=False)
    input_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SectorMetricRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sector_metric_runs"
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    group_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(100))
    domain: Mapped[str | None] = mapped_column(String(100))
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    universe_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SectorMetric(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sector_metrics"
    __table_args__ = (
        UniqueConstraint(
            "sector_metric_run_id",
            "listed_company_id",
            "metric_code",
            name="uq_sector_metric_member",
        ),
    )
    sector_metric_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("sector_metric_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False
    )
    metric_code: Mapped[str] = mapped_column(String(60), nullable=False)
    raw_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    percentile: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    z_score: Mapped[Decimal | None] = mapped_column(Numeric(16, 8))
    rank: Mapped[int | None] = mapped_column(Integer)
    eligible_company_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockFeatureRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_feature_runs"
    __table_args__ = (
        UniqueConstraint(
            "stock_listing_id",
            "as_of_date",
            "feature_set_version",
            "input_hash",
            name="uq_stock_feature_input",
        ),
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False
    )
    stock_listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_listings.id"), nullable=False, index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    feature_set_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockFeature(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_features"
    __table_args__ = (
        CheckConstraint(VALUE_STATUS, name="status_valid"),
        UniqueConstraint("feature_run_id", "feature_name", name="uq_stock_feature_name"),
    )
    feature_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_feature_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_name: Mapped[str] = mapped_column(String(80), nullable=False)
    feature_group: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockFeatureInput(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_feature_inputs"
    stock_feature_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_features.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(nullable=False)
    input_name: Mapped[str] = mapped_column(String(80), nullable=False)
    input_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
