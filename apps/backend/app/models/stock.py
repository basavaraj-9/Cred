from __future__ import annotations

# ruff: noqa: E501
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
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


class ListedCompany(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "listed_companies"
    __table_args__ = (
        Index("ix_listed_companies_taxonomy", "sector", "industry", "domain", "sub_domain"),
    )
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(500))
    isin: Mapped[str | None] = mapped_column(String(20), unique=True)
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    domain: Mapped[str | None] = mapped_column(String(100))
    sub_domain: Mapped[str | None] = mapped_column(String(100))
    business_description: Mapped[str | None] = mapped_column(Text)
    products_json: Mapped[list[str] | None] = mapped_column(JSON)
    taxonomy_version: Mapped[str | None] = mapped_column(String(100))
    classification_status: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_match_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    source_version: Mapped[str] = mapped_column(String(100), nullable=False)
    universe_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class StockListing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stock_listings"
    __table_args__ = (
        CheckConstraint("exchange IN ('NSE','BSE')", name="exchange_valid"),
        CheckConstraint(
            "listing_status IN ('ACTIVE','SUSPENDED','DELISTED','UNKNOWN')",
            name="listing_status_valid",
        ),
        CheckConstraint(
            "security_type IN ('EQUITY','SME_EQUITY','OTHER')", name="security_type_valid"
        ),
        CheckConstraint(
            "price_data_status IN ('CURRENT','STALE','MISSING','PARTIAL')",
            name="price_data_status_valid",
        ),
        UniqueConstraint("exchange", "symbol", name="uq_stock_listing_exchange_symbol"),
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False, index=True
    )
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange_security_id: Mapped[str | None] = mapped_column(String(50))
    listing_status: Mapped[str] = mapped_column(String(20), nullable=False)
    security_type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    source_version: Mapped[str] = mapped_column(String(100), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False)
    last_price_date: Mapped[date | None] = mapped_column(Date)
    price_data_status: Mapped[str] = mapped_column(String(20), nullable=False, default="MISSING")


class PeerGroup(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "peer_groups"
    __table_args__ = (
        CheckConstraint(
            "status IN ('READY','PARTIAL','NEEDS_REVIEW','INSUFFICIENT_CLASSIFICATION','NO_PEERS_FOUND','SEGMENT_REVIEW_REQUIRED')",
            name="status_valid",
        ),
        UniqueConstraint(
            "document_id",
            "domain_classification_id",
            "policy_version",
            "universe_snapshot_hash",
            "input_hash",
            name="uq_peer_group_input",
        ),
    )
    source_company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    company_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("company_profiles.id"), nullable=False
    )
    domain_classification_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("domain_classifications.id")
    )
    taxonomy_version: Mapped[str | None] = mapped_column(String(100))
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    universe_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    universe_version: Mapped[str] = mapped_column(String(100), nullable=False)
    universe_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PeerGroupMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "peer_group_members"
    __table_args__ = (
        CheckConstraint("rank > 0", name="rank_positive"),
        CheckConstraint("similarity_score BETWEEN 0 AND 1", name="similarity_range"),
        UniqueConstraint("peer_group_id", "listed_company_id", name="uq_peer_group_company"),
        UniqueConstraint("peer_group_id", "rank", name="uq_peer_group_rank"),
    )
    peer_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("peer_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    listed_company_id: Mapped[UUID] = mapped_column(
        ForeignKey("listed_companies.id"), nullable=False
    )
    stock_listing_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_listings.id"))
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity_score: Mapped[float] = mapped_column(Numeric(7, 6), nullable=False)
    sector_score: Mapped[float] = mapped_column(Numeric(7, 6), nullable=False)
    industry_score: Mapped[float] = mapped_column(Numeric(7, 6), nullable=False)
    domain_score: Mapped[float] = mapped_column(Numeric(7, 6), nullable=False)
    sub_domain_score: Mapped[float] = mapped_column(Numeric(7, 6), nullable=False)
    business_similarity_score: Mapped[float] = mapped_column(Numeric(7, 6), nullable=False)
    product_overlap_score: Mapped[float] = mapped_column(Numeric(7, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rationale_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketDataRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "market_data_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','PARTIAL','FAILED')", name="status_valid"
        ),
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(10))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StockPrice(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_prices"
    __table_args__ = (
        CheckConstraint("open > 0 AND high > 0 AND low > 0 AND close > 0", name="prices_positive"),
        CheckConstraint(
            "low <= open AND open <= high AND low <= close AND close <= high", name="ohlc_valid"
        ),
        CheckConstraint("volume >= 0", name="volume_nonnegative"),
        UniqueConstraint(
            "stock_listing_id",
            "trade_date",
            "provider",
            "provider_version",
            name="uq_stock_price_provider_day",
        ),
        Index("ix_stock_prices_listing_date", "stock_listing_id", "trade_date"),
    )
    stock_listing_id: Mapped[UUID] = mapped_column(ForeignKey("stock_listings.id"), nullable=False)
    market_data_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_data_runs.id"), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(100), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_adjusted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketDataError(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "market_data_errors"
    market_data_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_data_runs.id", ondelete="CASCADE"), nullable=False
    )
    stock_listing_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_listings.id"))
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    error_code: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
