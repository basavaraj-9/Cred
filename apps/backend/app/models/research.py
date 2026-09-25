from __future__ import annotations

# ruff: noqa: E501
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ResearchRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','SEARCHING','FETCHING','EXTRACTING','COMPLETED','PARTIAL','NEEDS_REVIEW','FAILED')",
            name="status_valid",
        ),
        CheckConstraint("refresh_number >= 0", name="refresh_nonnegative"),
        UniqueConstraint(
            "company_id", "input_hash", "refresh_number", name="uq_research_runs_input_refresh"
        ),
        Index("ix_research_runs_company_created", "company_id", "created_at"),
        Index("ix_research_runs_status", "status"),
    )

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    company_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("company_profiles.id"), nullable=False
    )
    domain_classification_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("domain_classifications.id")
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    query_builder_version: Mapped[str] = mapped_column(String(100), nullable=False)
    source_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    freshness_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)
    finding_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    refresh_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class ResearchQuery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_queries"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('COMPANY','PROMOTER','LEGAL','RATINGS','INDUSTRY','SECTOR')",
            name="scope_valid",
        ),
        CheckConstraint(
            "status IN ('PENDING','COMPLETED','PARTIAL','FAILED','NO_VERIFIED_FINDINGS')",
            name="status_valid",
        ),
        UniqueConstraint("research_run_id", "query_hash", name="uq_research_queries_run_hash"),
        Index("ix_research_queries_run", "research_run_id"),
    )

    research_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(30), nullable=False)
    query_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))


class ResearchSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_sources"
    __table_args__ = (
        CheckConstraint("length(trim(canonical_url)) > 0", name="canonical_url_nonempty"),
        CheckConstraint("quality_score >= 0 AND quality_score <= 1", name="quality_range"),
        CheckConstraint(
            "entity_match_score >= 0 AND entity_match_score <= 1", name="entity_match_range"
        ),
        CheckConstraint(
            "source_type IN ('OFFICIAL','RATING_AGENCY','REGULATOR','GOVERNMENT','INDUSTRY_BODY','REPUTABLE_NEWS','OTHER')",
            name="source_type_valid",
        ),
        CheckConstraint(
            "status IN ('RETRIEVED','REJECTED','DUPLICATE','FAILED','NEEDS_REVIEW')",
            name="status_valid",
        ),
        CheckConstraint(
            "freshness_status IN ('CURRENT','STALE','HISTORICAL','UNKNOWN')", name="freshness_valid"
        ),
        UniqueConstraint("research_run_id", "canonical_url", name="uq_research_sources_run_url"),
        Index("ix_research_sources_run", "research_run_id"),
        Index("ix_research_sources_status", "status"),
        Index("ix_research_sources_publisher", "publisher"),
    )

    research_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    research_query_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_queries.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    publisher: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    normalized_text: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    publication_date: Mapped[date | None] = mapped_column(Date)
    event_date: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_match_status: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_match_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    duplicate_of_source_id: Mapped[UUID | None] = mapped_column(ForeignKey("research_sources.id"))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))


class ResearchEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_evidence"
    __table_args__ = (
        CheckConstraint(
            "category IN ('COMPANY','PROMOTER','LEGAL','RATINGS','INDUSTRY','SECTOR')",
            name="category_valid",
        ),
        CheckConstraint(
            "impact IN ('POSITIVE','NEGATIVE','NEUTRAL','MIXED','REVIEW')", name="impact_valid"
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint("length(trim(evidence_text)) > 0", name="evidence_nonempty"),
        CheckConstraint("length(evidence_text) <= 2000", name="evidence_length"),
        CheckConstraint(
            "status IN ('VERIFIED','NEEDS_REVIEW','CONFLICTING','STALE')", name="status_valid"
        ),
        UniqueConstraint(
            "research_source_id", "evidence_hash", name="uq_research_evidence_source_hash"
        ),
        Index("ix_research_evidence_run", "research_run_id"),
        Index("ix_research_evidence_category", "category"),
    )

    research_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    research_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    event_code: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    impact: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    candidate_section: Mapped[str | None] = mapped_column(String(30))
    event_date: Mapped[date | None] = mapped_column(Date)
    attributes_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class ResearchFinding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_findings"
    __table_args__ = (
        CheckConstraint(
            "category IN ('COMPANY','PROMOTER','LEGAL','RATINGS','INDUSTRY','SECTOR')",
            name="category_valid",
        ),
        CheckConstraint(
            "impact IN ('POSITIVE','NEGATIVE','NEUTRAL','MIXED','REVIEW')", name="impact_valid"
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "status IN ('VERIFIED','CORROBORATED','SINGLE_SOURCE','NEEDS_REVIEW','CONFLICTING','STALE')",
            name="status_valid",
        ),
        UniqueConstraint(
            "research_run_id",
            "finding_code",
            "entity_name",
            "event_date",
            name="uq_research_findings_event",
        ),
        Index("ix_research_findings_run", "research_run_id"),
        Index("ix_research_findings_category", "category"),
    )

    research_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    finding_code: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    impact: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    candidate_section: Mapped[str | None] = mapped_column(String(30))
    event_date: Mapped[date | None] = mapped_column(Date)
    first_published_at: Mapped[date | None] = mapped_column(Date)
    latest_published_at: Mapped[date | None] = mapped_column(Date)
    contradiction_code: Mapped[str | None] = mapped_column(String(100))
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)


class ResearchFindingSource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "research_finding_sources"
    __table_args__ = (
        UniqueConstraint(
            "research_finding_id", "research_source_id", name="uq_research_finding_sources_link"
        ),
        Index("ix_research_finding_sources_finding", "research_finding_id"),
    )

    research_finding_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_findings.id", ondelete="CASCADE"), nullable=False
    )
    research_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False
    )
    research_evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_evidence.id", ondelete="CASCADE"), nullable=False
    )
    is_independent: Mapped[bool] = mapped_column(nullable=False, default=True)
