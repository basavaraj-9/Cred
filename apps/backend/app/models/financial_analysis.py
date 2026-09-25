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
    FinancialScope,
    NormalizationStatus,
    RatioStatus,
    ValidationSeverity,
    ValidationStatus,
    ValueOrigin,
)


class FinancialAnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_analysis_runs"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "input_hash",
            "validator_version",
            "calculator_version",
            "ratio_taxonomy_version",
            name="uq_financial_analysis_runs_input",
        ),
        CheckConstraint(
            "completeness_score >= 0 AND completeness_score <= 1", name="completeness_range"
        ),
        Index("ix_financial_analysis_runs_document_id", "document_id"),
    )

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    normalized_value_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    derived_value_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ratio_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validator_version: Mapped[str] = mapped_column(String(100), nullable=False)
    calculator_version: Mapped[str] = mapped_column(String(100), nullable=False)
    ratio_taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NormalizedFinancialValue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "normalized_financial_values"
    __table_args__ = (
        CheckConstraint(
            "normalization_confidence >= 0 AND normalization_confidence <= 1",
            name="confidence_range",
        ),
        Index("ix_normalized_financial_values_run_id", "run_id"),
        Index(
            "ix_normalized_financial_values_lookup",
            "document_id",
            "statement_scope",
            "fiscal_year",
            "canonical_name",
        ),
        UniqueConstraint(
            "run_id",
            "statement_scope",
            "fiscal_year",
            "canonical_name",
            name="uq_normalized_financial_values_run_scope_year_name",
        ),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("financial_analysis_runs.id"), nullable=False)
    financial_line_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("financial_line_items.id")
    )
    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(100), nullable=False)
    statement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    statement_scope: Mapped[FinancialScope] = mapped_column(
        SAEnum(FinancialScope, native_enum=False, create_constraint=True), nullable=False
    )
    fiscal_year: Mapped[str] = mapped_column(String(20), nullable=False)
    measurement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    raw_numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    normalized_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    currency: Mapped[str | None] = mapped_column(String(3))
    normalized_currency: Mapped[str | None] = mapped_column(String(3))
    raw_unit: Mapped[str | None] = mapped_column(String(50))
    canonical_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    unit_multiplier: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    normalization_status: Mapped[NormalizationStatus] = mapped_column(
        SAEnum(NormalizationStatus, native_enum=False, create_constraint=True), nullable=False
    )
    normalization_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    value_origin: Mapped[ValueOrigin] = mapped_column(
        SAEnum(ValueOrigin, native_enum=False, create_constraint=True), nullable=False
    )
    formula: Mapped[str | None] = mapped_column(String(500))
    input_value_ids: Mapped[list[str] | None] = mapped_column(JSONB)


class FinancialValidationIssue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_validation_issues"
    __table_args__ = (
        Index("ix_financial_validation_issues_run_id", "run_id"),
        Index("ix_financial_validation_issues_document_id", "document_id"),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("financial_analysis_runs.id"), nullable=False)
    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    statement_scope: Mapped[FinancialScope] = mapped_column(
        SAEnum(FinancialScope, native_enum=False, create_constraint=True), nullable=False
    )
    fiscal_year: Mapped[str] = mapped_column(String(20), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[ValidationSeverity] = mapped_column(
        SAEnum(ValidationSeverity, native_enum=False, create_constraint=True), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_line_item_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    related_value_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    expected_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    tolerance: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    status: Mapped[ValidationStatus] = mapped_column(
        SAEnum(ValidationStatus, native_enum=False, create_constraint=True), nullable=False
    )
    validator_version: Mapped[str] = mapped_column(String(100), nullable=False)


class FinancialRatio(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_ratios"
    __table_args__ = (
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        UniqueConstraint(
            "run_id",
            "statement_scope",
            "fiscal_year",
            "ratio_name",
            name="uq_financial_ratios_run_scope_year_name",
        ),
        Index(
            "ix_financial_ratios_document_scope_year",
            "document_id",
            "statement_scope",
            "fiscal_year",
        ),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("financial_analysis_runs.id"), nullable=False)
    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    statement_scope: Mapped[FinancialScope] = mapped_column(
        SAEnum(FinancialScope, native_enum=False, create_constraint=True), nullable=False
    )
    fiscal_year: Mapped[str] = mapped_column(String(20), nullable=False)
    ratio_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ratio_category: Mapped[str] = mapped_column(String(50), nullable=False)
    ratio_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    ratio_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[RatioStatus] = mapped_column(
        SAEnum(RatioStatus, native_enum=False, create_constraint=True), nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    calculation_basis: Mapped[str] = mapped_column(String(30), nullable=False)
    formula: Mapped[str] = mapped_column(String(500), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(100), nullable=False)
    ratio_taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    calculator_version: Mapped[str] = mapped_column(String(100), nullable=False)


class FinancialRatioInput(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_ratio_inputs"
    __table_args__ = (
        UniqueConstraint(
            "financial_ratio_id",
            "normalized_financial_value_id",
            "input_role",
            name="uq_financial_ratio_inputs_role",
        ),
        Index("ix_financial_ratio_inputs_ratio_id", "financial_ratio_id"),
    )

    financial_ratio_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_ratios.id"), nullable=False
    )
    normalized_financial_value_id: Mapped[UUID] = mapped_column(
        ForeignKey("normalized_financial_values.id"), nullable=False
    )
    input_role: Mapped[str] = mapped_column(String(100), nullable=False)
