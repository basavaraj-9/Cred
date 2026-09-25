from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import FinancialScope, FinancialStatementType, FinancialStatus


class FinancialExtractionRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_extraction_runs"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "extractor_version",
            "taxonomy_version",
            "input_hash",
            name="uq_financial_runs_input",
        ),
        CheckConstraint("statement_count >= 0 AND line_item_count >= 0", name="counts_nonnegative"),
        Index("ix_financial_runs_document_id", "document_id"),
    )

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[FinancialStatus] = mapped_column(
        SAEnum(FinancialStatus, native_enum=False, create_constraint=True), nullable=False
    )
    statement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FinancialStatement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_statements"
    __table_args__ = (
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        CheckConstraint(
            "start_page_number >= 1 AND end_page_number >= start_page_number", name="page_range"
        ),
        CheckConstraint("unit_multiplier > 0", name="multiplier_positive"),
        Index("ix_financial_statements_document_id", "document_id"),
        Index("ix_financial_statements_run_id", "run_id"),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("financial_extraction_runs.id"), nullable=False)
    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    statement_type: Mapped[FinancialStatementType] = mapped_column(
        SAEnum(FinancialStatementType, native_enum=False, create_constraint=True), nullable=False
    )
    statement_scope: Mapped[FinancialScope] = mapped_column(
        SAEnum(FinancialScope, native_enum=False, create_constraint=True), nullable=False
    )
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    fiscal_year: Mapped[str | None] = mapped_column(String(20))
    period_label: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str | None] = mapped_column(String(3))
    raw_unit: Mapped[str | None] = mapped_column(String(50))
    normalized_unit: Mapped[str | None] = mapped_column(String(20))
    unit_multiplier: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False, default=1)
    start_page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[FinancialStatus] = mapped_column(
        SAEnum(FinancialStatus, native_enum=False, create_constraint=True), nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)


class FinancialLineItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_line_items"
    __table_args__ = (
        CheckConstraint(
            "numeric_value IS NOT NULL OR status IN ('UNAVAILABLE', 'UNMAPPED')",
            name="null_numeric_status",
        ),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
        CheckConstraint("page_number >= 1", name="page_positive"),
        CheckConstraint("unit_multiplier > 0", name="multiplier_positive"),
        Index("ix_financial_line_items_statement_id", "financial_statement_id"),
        Index("ix_financial_line_items_document_page_id", "document_page_id"),
    )

    financial_statement_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_statements.id"), nullable=False
    )
    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    document_page_id: Mapped[UUID] = mapped_column(ForeignKey("document_pages.id"), nullable=False)
    canonical_name: Mapped[str | None] = mapped_column(String(100))
    raw_label: Mapped[str] = mapped_column(String(500), nullable=False)
    measurement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    raw_value: Mapped[str] = mapped_column(String(100), nullable=False)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 6))
    raw_column_header: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str | None] = mapped_column(String(3))
    raw_unit: Mapped[str | None] = mapped_column(String(50))
    normalized_unit: Mapped[str | None] = mapped_column(String(20))
    unit_multiplier: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False, default=1)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    fiscal_year: Mapped[str | None] = mapped_column(String(20))
    period_label: Mapped[str | None] = mapped_column(String(100))
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[FinancialStatus] = mapped_column(
        SAEnum(FinancialStatus, native_enum=False, create_constraint=True), nullable=False
    )
    source_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
