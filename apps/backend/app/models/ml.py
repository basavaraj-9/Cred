from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MLRunStatus


class MLDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ml_datasets"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_ml_datasets_name_version"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_name: Mapped[str | None] = mapped_column(String(100))
    prediction_horizon_days: Mapped[int | None] = mapped_column(Integer)
    label_policy_version: Mapped[str | None] = mapped_column(String(100))
    feature_builder_version: Mapped[str | None] = mapped_column(String(100))
    feature_schema_version: Mapped[str | None] = mapped_column(String(100))
    split_policy_version: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)


class MLRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ml_runs"
    __table_args__ = (
        Index("ix_ml_runs_task_type", "task_type"),
        Index("ix_ml_runs_status", "status"),
    )

    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("ml_datasets.id"), nullable=False)
    status: Mapped[MLRunStatus] = mapped_column(
        SAEnum(MLRunStatus, native_enum=False, create_constraint=True), nullable=False
    )
    parameters_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_uri: Mapped[str | None] = mapped_column(String(2048))
    error_code: Mapped[str | None] = mapped_column(String(100))
    training_mode: Mapped[str | None] = mapped_column(String(50))
    feature_group: Mapped[str | None] = mapped_column(String(100))
    training_config_version: Mapped[str | None] = mapped_column(String(100))


class MLMetric(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ml_metrics"
    __table_args__ = (
        Index("ix_ml_metrics_run_id", "run_id"),
        CheckConstraint("metric_value >= 0", name="value_nonnegative"),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("ml_runs.id"), nullable=False)
    split: Mapped[str] = mapped_column(String(30), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class MLModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ml_models"
    __table_args__ = (
        UniqueConstraint("task_type", "model_version", name="uq_ml_models_task_version"),
        Index(
            "uq_ml_models_active_task", "task_type", unique=True, postgresql_where=text("is_active")
        ),
    )

    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("ml_runs.id"), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("ml_datasets.id"), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_builder_version: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    training_mode: Mapped[str | None] = mapped_column(String(50))
    model_readiness_status: Mapped[str | None] = mapped_column(String(50))
    lifecycle_status: Mapped[str | None] = mapped_column(String(50))
    calibration_method: Mapped[str | None] = mapped_column(String(50))
    selected_threshold: Mapped[float | None] = mapped_column(Float)
    feature_group: Mapped[str | None] = mapped_column(String(100))
    selection_policy_version: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
