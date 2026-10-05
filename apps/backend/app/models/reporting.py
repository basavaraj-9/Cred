from __future__ import annotations

# ruff: noqa: E501
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
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GeneratedReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generated_reports"
    __table_args__ = (
        CheckConstraint(
            "report_type IN ('CAM','CREDIT_COMMITTEE_MEMO','DECISION_EVIDENCE_PACK',"
            "'STRUCTURED_JSON_EXPORT','COMPANY_INTELLIGENCE_360')",
            name="report_type_valid",
        ),
        CheckConstraint(
            "status IN ('DRAFT','GENERATED','READY','NEEDS_REVIEW','FINALIZED',"
            "'SUPERSEDED','FAILED')",
            name="status_valid",
        ),
        CheckConstraint(
            "readiness_status IS NULL OR readiness_status IN "
            "('COMPLETE','PARTIAL','INSUFFICIENT_DATA','NEEDS_REVIEW')",
            name="readiness_valid",
        ),
        CheckConstraint(
            "completeness_ratio IS NULL OR completeness_ratio BETWEEN 0 AND 1",
            name="completeness_range",
        ),
        CheckConstraint(
            "evidence_coverage IS NULL OR evidence_coverage BETWEEN 0 AND 1",
            name="evidence_coverage_range",
        ),
        CheckConstraint("report_version > 0", name="version_positive"),
        CheckConstraint(
            "(status IN ('FINALIZED','SUPERSEDED') AND finalized_at IS NOT NULL AND finalized_by_user_id IS NOT NULL) OR (status NOT IN ('FINALIZED','SUPERSEDED') AND finalized_at IS NULL AND finalized_by_user_id IS NULL)",
            name="finalization_consistent",
        ),
        UniqueConstraint(
            "review_case_id", "report_type", "report_version", name="uq_generated_report_version"
        ),
        UniqueConstraint(
            "review_case_id",
            "report_type",
            "input_hash",
            "template_version",
            "renderer_version",
            name="uq_generated_report_input",
        ),
        Index("ix_generated_reports_case_type", "review_case_id", "report_type", "created_at"),
        Index("ix_generated_reports_company_type", "company_id", "report_type", "generated_at"),
        Index("ix_generated_reports_as_of", "analytical_as_of_date", "report_type"),
    )
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))
    analysis_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("analysis_jobs.id"))
    review_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("credit_review_cases.id"))
    decision_support_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_decision_support.id")
    )
    human_decision_id: Mapped[UUID | None] = mapped_column(ForeignKey("credit_human_decisions.id"))
    committee_package_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_committee_packages.id")
    )
    report_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False)
    template_version: Mapped[str] = mapped_column(String(100), nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(100))
    schema_version: Mapped[str | None] = mapped_column(String(100))
    readiness_status: Mapped[str | None] = mapped_column(String(30))
    analytical_as_of_date: Mapped[date | None] = mapped_column(Date)
    include_credit: Mapped[bool | None] = mapped_column(Boolean)
    include_stock: Mapped[bool | None] = mapped_column(Boolean)
    completeness_ratio: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    evidence_coverage: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    confidentiality_label: Mapped[str] = mapped_column(String(40), nullable=False)
    generated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    finalized_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_report_id: Mapped[UUID | None] = mapped_column(ForeignKey("generated_reports.id"))
    superseded_by_report_id: Mapped[UUID | None] = mapped_column(ForeignKey("generated_reports.id"))


class ReportSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "report_snapshots"
    __table_args__ = (
        UniqueConstraint("generated_report_id", name="uq_report_snapshot_report"),
        CheckConstraint("snapshot_version > 0", name="version_positive"),
    )
    generated_report_id: Mapped[UUID] = mapped_column(
        ForeignKey("generated_reports.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReportArtifact(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "report_artifacts"
    __table_args__ = (
        CheckConstraint("artifact_type IN ('REPORT','SNAPSHOT')", name="artifact_type_valid"),
        CheckConstraint("format IN ('PDF','JSON')", name="format_valid"),
        CheckConstraint("file_size_bytes > 0", name="size_positive"),
        CheckConstraint("char_length(sha256) = 64", name="sha256_valid"),
        UniqueConstraint("generated_report_id", "format", name="uq_report_artifact_format"),
    )
    generated_report_id: Mapped[UUID] = mapped_column(
        ForeignKey("generated_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(20), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReportSourceLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "report_source_links"
    __table_args__ = (
        UniqueConstraint(
            "generated_report_id",
            "source_type",
            "source_reference_id",
            name="uq_report_source_link",
        ),
    )
    generated_report_id: Mapped[UUID] = mapped_column(
        ForeignKey("generated_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(nullable=False)
    lineage_role: Mapped[str] = mapped_column(String(100), nullable=False)
    source_metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReportFinalizationAction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "report_finalization_actions"
    __table_args__ = (CheckConstraint("action IN ('FINALIZED','SUPERSEDED')", name="action_valid"),)
    generated_report_id: Mapped[UUID] = mapped_column(
        ForeignKey("generated_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
