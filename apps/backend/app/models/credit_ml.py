from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    CreditDatasetQuality,
    CreditDatasetSplit,
    CreditLabelQuality,
    CreditLabelStatus,
    CreditOutcomeType,
    DatasetEligibilityStatus,
    VerificationStatus,
)


class CreditMLObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_ml_observations"
    __table_args__ = (
        CheckConstraint("prediction_horizon_days > 0", name="prediction_horizon_positive"),
        CheckConstraint("outcome_window_end >= outcome_window_start", name="outcome_window_valid"),
        UniqueConstraint(
            "company_id",
            "observation_date",
            "prediction_horizon_days",
            "feature_cutoff_timestamp",
            name="uq_credit_ml_observation_identity",
        ),
        Index("ix_credit_ml_observations_company_id", "company_id"),
        Index("ix_credit_ml_observations_observation_date", "observation_date"),
    )

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    analysis_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("analysis_jobs.id"))
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    as_of_fiscal_year: Mapped[str] = mapped_column(String(20), nullable=False)
    prediction_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome_window_start: Mapped[date] = mapped_column(Date, nullable=False)
    outcome_window_end: Mapped[date] = mapped_column(Date, nullable=False)
    feature_cutoff_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    label_status: Mapped[CreditLabelStatus] = mapped_column(
        SAEnum(CreditLabelStatus, native_enum=False, create_constraint=True), nullable=False
    )
    dataset_eligibility_status: Mapped[DatasetEligibilityStatus] = mapped_column(
        SAEnum(DatasetEligibilityStatus, native_enum=False, create_constraint=True), nullable=False
    )


class CreditOutcome(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_outcomes"
    __table_args__ = (
        CheckConstraint(
            "binary_default_label IS NULL OR binary_default_label IN (0, 1)",
            name="binary_label_valid",
        ),
        CheckConstraint(
            "days_past_due IS NULL OR days_past_due >= 0", name="days_past_due_nonnegative"
        ),
        UniqueConstraint(
            "company_id",
            "observation_date",
            "outcome_type",
            "outcome_date",
            "source_type",
            "source_reference",
            name="uq_credit_outcome_source",
        ),
        Index("ix_credit_outcomes_company_id", "company_id"),
        Index("ix_credit_outcomes_outcome_date", "outcome_date"),
    )

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    outcome_date: Mapped[date | None] = mapped_column(Date)
    outcome_type: Mapped[CreditOutcomeType] = mapped_column(
        SAEnum(CreditOutcomeType, native_enum=False, create_constraint=True), nullable=False
    )
    outcome_value: Mapped[str | None] = mapped_column(String(200))
    binary_default_label: Mapped[int | None] = mapped_column(Integer)
    days_past_due: Mapped[int | None] = mapped_column(Integer)
    credit_event_severity: Mapped[str | None] = mapped_column(String(30))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    label_quality: Mapped[CreditLabelQuality] = mapped_column(
        SAEnum(CreditLabelQuality, native_enum=False, create_constraint=True), nullable=False
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False, create_constraint=True), nullable=False
    )


class CreditMLFeatureSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_ml_feature_snapshots"
    __table_args__ = (
        CheckConstraint(
            "feature_count >= 0 AND missing_feature_count >= 0", name="feature_counts_nonnegative"
        ),
        UniqueConstraint(
            "observation_id",
            "feature_builder_version",
            "feature_schema_version",
            "feature_group",
            "input_hash",
            name="uq_credit_ml_snapshot_input",
        ),
        Index("ix_credit_ml_feature_snapshots_input_hash", "input_hash"),
    )

    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_ml_observations.id"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    feature_cutoff_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    feature_builder_version: Mapped[str] = mapped_column(String(100), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    feature_group: Mapped[str] = mapped_column(String(100), nullable=False)
    features_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    availability_complete: Mapped[bool] = mapped_column(nullable=False, default=False)


class CreditMLFeatureSource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_ml_feature_sources"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(normalized_financial_value_id, financial_ratio_id, "
            "financial_trend_id, financial_anomaly_id, credit_assessment_id, "
            "company_profile_id, domain_classification_id) = 1",
            name="exactly_one_source",
        ),
        UniqueConstraint(
            "feature_snapshot_id", "feature_name", name="uq_credit_ml_feature_source_name"
        ),
    )

    feature_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_ml_feature_snapshots.id"), nullable=False
    )
    feature_name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_financial_value_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("normalized_financial_values.id")
    )
    financial_ratio_id: Mapped[UUID | None] = mapped_column(ForeignKey("financial_ratios.id"))
    financial_trend_id: Mapped[UUID | None] = mapped_column(ForeignKey("financial_trends.id"))
    financial_anomaly_id: Mapped[UUID | None] = mapped_column(ForeignKey("financial_anomalies.id"))
    credit_assessment_id: Mapped[UUID | None] = mapped_column(ForeignKey("credit_assessments.id"))
    company_profile_id: Mapped[UUID | None] = mapped_column(ForeignKey("company_profiles.id"))
    domain_classification_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("domain_classifications.id")
    )
    source_available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreditMLExample(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_ml_examples"
    __table_args__ = (
        CheckConstraint(
            "target_value IS NULL OR target_value IN (0, 1)", name="target_value_valid"
        ),
        UniqueConstraint("dataset_id", "observation_id", name="uq_credit_ml_example_observation"),
        Index("ix_credit_ml_examples_dataset_id", "dataset_id"),
        Index("ix_credit_ml_examples_split", "split"),
        Index("ix_credit_ml_examples_company_id", "company_id"),
    )

    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("ml_datasets.id"), nullable=False)
    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_ml_observations.id"), nullable=False
    )
    feature_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_ml_feature_snapshots.id"), nullable=False
    )
    outcome_id: Mapped[UUID | None] = mapped_column(ForeignKey("credit_outcomes.id"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_value: Mapped[int | None] = mapped_column(Integer)
    label_status: Mapped[CreditLabelStatus] = mapped_column(
        SAEnum(CreditLabelStatus, native_enum=False, create_constraint=True), nullable=False
    )
    label_quality: Mapped[CreditLabelQuality] = mapped_column(
        SAEnum(CreditLabelQuality, native_enum=False, create_constraint=True), nullable=False
    )
    split: Mapped[CreditDatasetSplit] = mapped_column(
        SAEnum(CreditDatasetSplit, native_enum=False, create_constraint=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditMLDatasetReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_ml_dataset_reports"
    __table_args__ = (UniqueConstraint("dataset_id", name="uq_credit_ml_dataset_report"),)

    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("ml_datasets.id"), nullable=False)
    quality_status: Mapped[CreditDatasetQuality] = mapped_column(
        SAEnum(CreditDatasetQuality, native_enum=False, create_constraint=True), nullable=False
    )
    training_readiness: Mapped[str] = mapped_column(String(50), nullable=False)
    report_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
