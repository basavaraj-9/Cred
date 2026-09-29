from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
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

from app.database.base import Base, UUIDPrimaryKeyMixin


class StockMLDataset(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ml_datasets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','BUILDING','READY','PARTIAL','FAILED',"
            "'NEEDS_REVIEW','PIPELINE_VALIDATED')",
            name="status_valid",
        ),
        UniqueConstraint("input_hash", name="uq_stock_ml_dataset_input_hash"),
    )
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
    feature_set_version: Mapped[str] = mapped_column(String(100), nullable=False)
    label_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    benchmark_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    split_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    universe_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_catalog_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    dataset_readiness: Mapped[str] = mapped_column(String(40), nullable=False)
    label_horizon: Mapped[str] = mapped_column(String(20), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    company_count: Mapped[int] = mapped_column(Integer, nullable=False)
    listing_count: Mapped[int] = mapped_column(Integer, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, nullable=False)
    neutral_count: Mapped[int] = mapped_column(Integer, nullable=False)
    censored_count: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockMLDatasetRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ml_dataset_rows"
    __table_args__ = (
        CheckConstraint(
            "eligibility_status IN ('LABELED','CENSORED','INSUFFICIENT_BENCHMARK',"
            "'INSUFFICIENT_PRICE_HISTORY','INVALID_SOURCE','NEEDS_REVIEW')",
            name="eligibility_status_valid",
        ),
        UniqueConstraint(
            "dataset_id", "stock_listing_id", "as_of_date", name="uq_stock_ml_dataset_row"
        ),
    )
    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False
    )
    stock_listing_id: Mapped[UUID] = mapped_column(ForeignKey("stock_listings.id"), nullable=False)
    feature_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_feature_runs.id"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    label_reference_date: Mapped[date | None] = mapped_column(Date)
    start_price_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_prices.id"))
    end_price_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_prices.id"))
    forward_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    benchmark_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    relative_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    label_class: Mapped[str | None] = mapped_column(String(20))
    rank_target: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    benchmark_type: Mapped[str | None] = mapped_column(String(40))
    benchmark_reference: Mapped[str | None] = mapped_column(String(255))
    eligibility_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockMLDatasetFeature(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ml_dataset_features"
    __table_args__ = (
        UniqueConstraint("dataset_row_id", "feature_name", name="uq_stock_ml_dataset_feature"),
    )
    dataset_row_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_dataset_rows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_name: Mapped[str] = mapped_column(String(100), nullable=False)
    feature_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    feature_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockMLSplit(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ml_splits"
    __table_args__ = (
        CheckConstraint("split_index > 0", name="split_index_positive"),
        UniqueConstraint("dataset_id", "split_index", name="uq_stock_ml_split_index"),
    )
    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    split_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    split_index: Mapped[int] = mapped_column(Integer, nullable=False)
    train_start: Mapped[date] = mapped_column(Date, nullable=False)
    train_end: Mapped[date] = mapped_column(Date, nullable=False)
    validation_start: Mapped[date] = mapped_column(Date, nullable=False)
    validation_end: Mapped[date] = mapped_column(Date, nullable=False)
    test_start: Mapped[date] = mapped_column(Date, nullable=False)
    test_end: Mapped[date] = mapped_column(Date, nullable=False)
    embargo_days: Mapped[int] = mapped_column(Integer, nullable=False)
    purged_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockMLSplitRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ml_split_rows"
    __table_args__ = (
        CheckConstraint(
            "partition IN ('TRAIN','VALIDATION','TEST','PURGED','CENSORED')",
            name="partition_valid",
        ),
        UniqueConstraint("split_id", "dataset_row_id", name="uq_stock_ml_split_row"),
    )
    split_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_splits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_row_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_dataset_rows.id", ondelete="CASCADE"), nullable=False
    )
    partition: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockMLRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ml_runs"
    __table_args__ = (
        UniqueConstraint("split_id", "model_name", "model_version", name="uq_stock_ml_run"),
    )
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("stock_ml_datasets.id"), nullable=False)
    split_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_splits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    hyperparameters_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    preprocessing_version: Mapped[str] = mapped_column(String(100), nullable=False)
    random_state: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockMLMetric(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ml_metrics"
    __table_args__ = (
        UniqueConstraint("ml_run_id", "partition", "metric_name", name="uq_stock_ml_metric"),
    )
    ml_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    partition: Mapped[str] = mapped_column(String(20), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(80), nullable=False)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    metric_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockMLModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ml_models"
    __table_args__ = (UniqueConstraint("ml_run_id", name="uq_stock_ml_model_run"),)
    ml_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    feature_schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(40), nullable=False)
    selected_for_research: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    production_use_permitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockMLPrediction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ml_predictions"
    __table_args__ = (
        CheckConstraint(
            "prediction_probability IS NULL OR (prediction_probability BETWEEN 0 AND 1)",
            name="probability_valid",
        ),
        UniqueConstraint("ml_run_id", "dataset_row_id", name="uq_stock_ml_prediction"),
    )
    ml_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_row_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ml_dataset_rows.id", ondelete="CASCADE"), nullable=False
    )
    partition: Mapped[str] = mapped_column(String(20), nullable=False)
    prediction_score: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    prediction_probability: Mapped[Decimal | None] = mapped_column(Numeric(12, 10))
    predicted_class: Mapped[str | None] = mapped_column(String(20))
    rank_score: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
