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
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class StockIntelligenceRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('AVAILABLE','PARTIAL','INSUFFICIENT_DATA','NEEDS_REVIEW','UNAVAILABLE')",
            name="status_valid",
        ),
        CheckConstraint("score IS NULL OR (score BETWEEN 0 AND 100)", name="score_valid"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_valid"),
        CheckConstraint("coverage BETWEEN 0 AND 1", name="coverage_valid"),
        CheckConstraint("production_use_permitted = false", name="production_disabled"),
        UniqueConstraint("input_hash", name="uq_stock_intelligence_input_hash"),
        Index("ix_stock_intelligence_listing_date", "stock_listing_id", "as_of_date"),
        Index("ix_stock_intelligence_company_date", "listed_company_id", "as_of_date"),
        Index("ix_stock_intelligence_score_version", "score_version"),
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False
    )
    stock_listing_id: Mapped[UUID] = mapped_column(ForeignKey("stock_listings.id"), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    score_version: Mapped[str] = mapped_column(String(100), nullable=False)
    fusion_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    normalization_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    ranking_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    watchlist_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    confidence: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    coverage: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    available_weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    available_component_count: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_component_count: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[str | None] = mapped_column(String(60))
    agreement_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    top_positive_drivers: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    top_negative_drivers: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    contradictions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    missing_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    production_use_permitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockIntelligenceComponent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_components"
    __table_args__ = (
        CheckConstraint(
            "component_name IN ('ML_SIGNAL','VALUATION','FUNDAMENTAL_QUALITY','GROWTH',"
            "'PROFITABILITY','BALANCE_SHEET','MOMENTUM','RISK','PEER_RELATIVE',"
            "'SECTOR_RELATIVE','DATA_QUALITY')",
            name="component_name_valid",
        ),
        CheckConstraint(
            "status IN ('AVAILABLE','PARTIAL','INSUFFICIENT_DATA','NEEDS_REVIEW','UNAVAILABLE')",
            name="status_valid",
        ),
        CheckConstraint(
            "normalized_score IS NULL OR (normalized_score BETWEEN 0 AND 100)",
            name="normalized_score_valid",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_valid"),
        UniqueConstraint("run_id", "component_name", name="uq_stock_intelligence_component"),
        Index("ix_stock_intelligence_component_run", "run_id"),
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_runs.id", ondelete="CASCADE"), nullable=False
    )
    component_name: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_score: Mapped[Decimal | None] = mapped_column(Numeric(16, 8))
    normalized_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    configured_weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    effective_weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    contribution: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    confidence: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockIntelligenceComponentInput(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_intelligence_component_inputs"
    __table_args__ = (
        UniqueConstraint(
            "component_id",
            "source_type",
            "source_id",
            "feature_name",
            name="uq_stock_intelligence_component_input",
        ),
        Index("ix_stock_intelligence_input_component", "component_id"),
        Index("ix_stock_intelligence_input_source", "source_type", "source_id"),
    )
    component_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_components.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[UUID] = mapped_column(nullable=False)
    feature_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    source_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    source_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockRankingRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ranking_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('AVAILABLE','PARTIAL','INSUFFICIENT_DATA','NEEDS_REVIEW','UNAVAILABLE')",
            name="status_valid",
        ),
        UniqueConstraint("input_hash", name="uq_stock_ranking_input_hash"),
        Index("ix_stock_ranking_as_of", "as_of_date"),
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    ranking_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    watchlist_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    universe_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    eligible_company_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockRankingMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_ranking_members"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="score_valid"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_valid"),
        CheckConstraint("coverage BETWEEN 0 AND 1", name="coverage_valid"),
        CheckConstraint("percentile BETWEEN 0 AND 100", name="percentile_valid"),
        CheckConstraint("rank > 0", name="rank_positive"),
        CheckConstraint(
            "research_priority IN ('RESEARCH_PRIORITY_HIGH','RESEARCH_PRIORITY_MEDIUM',"
            "'RESEARCH_PRIORITY_LOW','INSUFFICIENT_DATA')",
            name="research_priority_valid",
        ),
        UniqueConstraint("ranking_run_id", "stock_listing_id", name="uq_stock_ranking_member"),
        Index("ix_stock_ranking_member_run", "ranking_run_id"),
    )
    ranking_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_ranking_runs.id", ondelete="CASCADE"), nullable=False
    )
    stock_intelligence_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_intelligence_runs.id"), nullable=False
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False
    )
    stock_listing_id: Mapped[UUID] = mapped_column(ForeignKey("stock_listings.id"), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    coverage: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    percentile: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    rank_status: Mapped[str] = mapped_column(String(30), nullable=False)
    research_priority: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
