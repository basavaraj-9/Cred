from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.company_profile import CompanyProfile
from app.models.domain_classification import DomainClassification
from app.models.extracted_field import ExtractedField
from app.models.stock import (
    ListedCompany,
    MarketDataError,
    MarketDataRun,
    PeerGroup,
    PeerGroupMember,
    StockListing,
    StockPrice,
)
from app.services.rag.service import CreditRagIndexService

UNIVERSE_VERSION = "indian_listed_universe_v1"
RESOLVER_VERSION = "listed_company_entity_resolver_v1"
PEER_ENGINE_VERSION = "peer_discovery_engine_v1"


def now() -> datetime:
    return datetime.now(UTC)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def norm(value: str | None) -> str:
    return re.sub(r"\b(limited|ltd|private|pvt)\b|[^a-z0-9]", "", (value or "").lower())


def tokens(value: str | None) -> set[str]:
    return {
        x
        for x in re.findall(r"[a-z0-9]+", (value or "").lower())
        if x not in {"and", "the", "of", "limited", "company", "systems", "services", "products"}
    }


@dataclass(frozen=True)
class UniverseRecord:
    company_name: str
    legal_name: str
    exchange: str
    symbol: str
    isin: str | None
    sector: str
    industry: str
    domain: str
    sub_domain: str
    description: str
    products: tuple[str, ...]
    website: str | None = None
    listing_status: str = "ACTIVE"
    security_type: str = "EQUITY"
    exchange_security_id: str | None = None


class ListedUniverseProvider(Protocol):
    provider_name: str
    provider_version: str

    def fetch_nse_universe(self) -> list[UniverseRecord]: ...
    def fetch_bse_universe(self) -> list[UniverseRecord]: ...
    def normalize_company(self, row: UniverseRecord) -> UniverseRecord: ...
    def normalize_listing(self, row: UniverseRecord) -> UniverseRecord: ...


class FixtureListedUniverseProvider:
    provider_name = "development_fixture_provider"
    provider_version = UNIVERSE_VERSION

    def _all(self) -> list[UniverseRecord]:
        e = (
            "Industrials",
            "Electrical Equipment",
            "Power Distribution Equipment",
            "Transformers & Switchgear",
        )
        return [
            UniverseRecord(
                "Example Transformer Ltd",
                "Example Transformer Limited",
                "NSE",
                "EXTRANS",
                "INE000A01001",
                *e,
                "Power transformers and switchgear for electricity grids",
                ("transformers", "switchgear"),
                "https://extrans.example",
            ),
            UniverseRecord(
                "Example Transformer Ltd",
                "Example Transformer Limited",
                "BSE",
                "500000",
                "INE000A01001",
                *e,
                "Power transformers and switchgear for electricity grids",
                ("transformers", "switchgear"),
                "https://extrans.example",
                exchange_security_id="500000",
            ),
            UniverseRecord(
                "Example Power Systems Ltd",
                "Example Power Systems Limited",
                "NSE",
                "EXPOWER",
                "INE000B01001",
                *e,
                "Distribution transformers and grid power equipment",
                ("transformers", "power equipment"),
            ),
            UniverseRecord(
                "Grid Switchgear India Ltd",
                "Grid Switchgear India Limited",
                "BSE",
                "500101",
                "INE000C01001",
                *e,
                "Industrial switchgear and power distribution equipment",
                ("switchgear", "control panels"),
            ),
            UniverseRecord(
                "Example Consumer Appliances Ltd",
                "Example Consumer Appliances Limited",
                "NSE",
                "EXHOME",
                "INE000D01001",
                "Consumer Discretionary",
                "Consumer Durables",
                "Home Appliances",
                "Kitchen Appliances",
                "Consumer fans and kitchen appliances",
                ("fans", "mixers"),
            ),
            UniverseRecord(
                "Infoserve India Ltd",
                "Infoserve India Limited",
                "NSE",
                "INFOSERVE",
                "INE000E01001",
                "Information Technology",
                "IT Services",
                "Software Services",
                "IT Consulting",
                "Technology consulting and application services",
                ("software", "consulting"),
            ),
            UniverseRecord(
                "National Bank Example Ltd",
                "National Bank Example Limited",
                "NSE",
                "NBANK",
                "INE000F01001",
                "Financials",
                "Banks",
                "Banking",
                "Private Sector Bank",
                "Retail and corporate banking",
                ("loans", "deposits"),
            ),
            UniverseRecord(
                "Example Pharma Ltd",
                "Example Pharma Limited",
                "BSE",
                "500202",
                "INE000G01001",
                "Healthcare",
                "Pharmaceuticals",
                "Pharmaceutical Manufacturing",
                "Generic Medicines",
                "Generic medicines and formulations",
                ("tablets", "formulations"),
            ),
            UniverseRecord(
                "Example Oil Foods Ltd",
                "Example Oil Foods Limited",
                "NSE",
                "OILFOOD",
                "INE000H01001",
                "Consumer Staples",
                "Food Products",
                "Edible Oils",
                "Packaged Oils",
                "Edible cooking oils",
                ("edible oil",),
            ),
            UniverseRecord(
                "Example Refining Ltd",
                "Example Refining Limited",
                "NSE",
                "REFINE",
                "INE000I01001",
                "Energy",
                "Oil & Gas",
                "Oil Refining",
                "Refineries",
                "Petroleum refining",
                ("fuel", "petroleum"),
            ),
            UniverseRecord(
                "Example Metals Ltd",
                "Example Metals Limited",
                "BSE",
                "500303",
                "INE000J01001",
                "Materials",
                "Metals",
                "Steel Manufacturing",
                "Flat Steel",
                "Steel products",
                ("steel",),
            ),
            UniverseRecord(
                "Example Power Industries Ltd",
                "Example Power Industries Limited",
                "NSE",
                "EXPOWIND",
                None,
                *e,
                "Electrical equipment holding company",
                ("equipment",),
                listing_status="SUSPENDED",
            ),
        ]

    def fetch_nse_universe(self) -> list[UniverseRecord]:
        return [x for x in self._all() if x.exchange == "NSE"]

    def fetch_bse_universe(self) -> list[UniverseRecord]:
        return [x for x in self._all() if x.exchange == "BSE"]

    def normalize_company(self, row: UniverseRecord) -> UniverseRecord:
        return row

    def normalize_listing(self, row: UniverseRecord) -> UniverseRecord:
        return UniverseRecord(
            **{**asdict(row), "symbol": re.sub(r"\.(NS|BO)$", "", row.symbol.strip().upper())}
        )


class StockUniverseService:
    def __init__(self, session: Session, provider: ListedUniverseProvider | None = None):
        self.session = session
        self.provider = provider or FixtureListedUniverseProvider()

    def sync(self, actor_id: UUID, exchange: str | None = None) -> dict[str, object]:
        actor = CreditRagIndexService(self.session)._user(actor_id)
        rows = []
        if exchange in {None, "NSE"}:
            rows += self.provider.fetch_nse_universe()
        if exchange in {None, "BSE"}:
            rows += self.provider.fetch_bse_universe()
        if exchange not in {None, "NSE", "BSE"}:
            raise AppError("EXCHANGE_INVALID", "Exchange must be NSE or BSE", 422)
        rows = [self.provider.normalize_listing(self.provider.normalize_company(x)) for x in rows]
        snapshot = digest([asdict(x) for x in rows])
        marker = UUID(snapshot[:32])
        write_audit_log(
            self.session,
            entity_type="stock_universe",
            entity_id=marker,
            action="STOCK_UNIVERSE_SYNC_STARTED",
            event_type="STOCK_UNIVERSE_SYNC_STARTED",
            user_id=actor.id,
        )
        companies: dict[str, ListedCompany] = {}
        for item in rows:
            key = item.isin or f"{norm(item.legal_name)}:{(item.website or '').lower()}"
            company = companies.get(key)
            if company is None:
                company = (
                    self.session.scalar(
                        select(ListedCompany).where(ListedCompany.isin == item.isin)
                    )
                    if item.isin
                    else None
                )
            if company is None and item.isin is None:
                matches = list(
                    self.session.scalars(
                        select(ListedCompany).where(ListedCompany.legal_name == item.legal_name)
                    )
                )
                company = (
                    matches[0]
                    if len(matches) == 1
                    and (
                        (item.website and matches[0].website == item.website)
                        or matches[0].domain == item.domain
                    )
                    else None
                )
            if company is None:
                company = ListedCompany(
                    canonical_name=item.company_name,
                    legal_name=item.legal_name,
                    website=item.website,
                    isin=item.isin,
                    sector=item.sector,
                    industry=item.industry,
                    domain=item.domain,
                    sub_domain=item.sub_domain,
                    business_description=item.description,
                    products_json=list(item.products),
                    taxonomy_version="domain_taxonomy_v1",
                    classification_status="VERIFIED",
                    entity_match_status="VERIFIED" if item.isin else "NEEDS_REVIEW",
                    source_provider=self.provider.provider_name,
                    source_version=self.provider.provider_version,
                    universe_snapshot_hash=snapshot,
                )
                self.session.add(company)
                self.session.flush()
            companies[key] = company
            listing = self.session.scalar(
                select(StockListing).where(
                    StockListing.exchange == item.exchange, StockListing.symbol == item.symbol
                )
            )
            if listing is None:
                listing = StockListing(
                    listed_company_id=company.id,
                    exchange=item.exchange,
                    symbol=item.symbol,
                    exchange_security_id=item.exchange_security_id,
                    listing_status=item.listing_status,
                    security_type=item.security_type,
                    currency="INR",
                    source_provider=self.provider.provider_name,
                    source_version=self.provider.provider_version,
                    retrieved_at=now(),
                    is_primary=False,
                    price_data_status="MISSING",
                )
                self.session.add(listing)
            else:
                listing.listed_company_id = company.id
                listing.listing_status = item.listing_status
                listing.source_version = self.provider.provider_version
                listing.retrieved_at = now()
        self.session.flush()
        for company in set(companies.values()):
            listings = list(
                self.session.scalars(
                    select(StockListing).where(StockListing.listed_company_id == company.id)
                )
            )
            eligible = [
                x for x in listings if x.listing_status == "ACTIVE" and x.security_type == "EQUITY"
            ]
            preferred = next(
                (x for x in eligible if x.exchange == "NSE"), eligible[0] if eligible else None
            )
            for listing in listings:
                listing.is_primary = listing is preferred
        write_audit_log(
            self.session,
            entity_type="stock_universe",
            entity_id=marker,
            action="STOCK_UNIVERSE_SYNC_COMPLETED",
            event_type="STOCK_UNIVERSE_SYNC_COMPLETED",
            user_id=actor.id,
            metadata_json={
                "snapshot_hash": snapshot,
                "listing_count": len(rows),
                "company_count": len(companies),
            },
        )
        return {
            "provider": self.provider.provider_name,
            "version": self.provider.provider_version,
            "snapshot_hash": snapshot,
            "listing_count": len(rows),
            "company_count": len(companies),
        }


class PeerDiscoveryService:
    def __init__(self, session: Session):
        self.session = session
        self.policy = json.loads(
            Path(__file__).with_name("peer_discovery_policy_v1.json").read_text()
        )

    def discover(
        self, document_id: UUID, actor_id: UUID, max_peers: int | None = None
    ) -> PeerGroup:
        actor = CreditRagIndexService(self.session)._user(actor_id)
        profile = self.session.scalar(
            select(CompanyProfile)
            .where(CompanyProfile.document_id == document_id)
            .order_by(desc(CompanyProfile.created_at))
            .limit(1)
        )
        classification = self.session.scalar(
            select(DomainClassification)
            .where(DomainClassification.document_id == document_id)
            .order_by(desc(DomainClassification.created_at))
            .limit(1)
        )
        if profile is None:
            raise AppError("COMPANY_PROFILE_NOT_FOUND", "Company profile not found", 404)
        listings = list(
            self.session.scalars(
                select(StockListing).where(
                    StockListing.listing_status == "ACTIVE", StockListing.security_type == "EQUITY"
                )
            )
        )
        if not listings:
            raise AppError("STOCK_UNIVERSE_EMPTY", "Sync the stock universe first", 409)
        companies = {
            x.id: x
            for x in self.session.scalars(
                select(ListedCompany).where(
                    ListedCompany.id.in_({x.listed_company_id for x in listings})
                )
            )
        }
        snapshot = digest(sorted({x.universe_snapshot_hash for x in companies.values()}))
        status_value = (
            getattr(classification.status, "value", classification.status)
            if classification
            else "UNAVAILABLE"
        )
        input_hash = digest(
            {
                "document": str(document_id),
                "classification": str(classification.id) if classification else None,
                "classification_hash": classification.input_text_hash if classification else None,
                "universe": snapshot,
                "policy": self.policy["version"],
            }
        )
        existing = self.session.scalar(
            select(PeerGroup).where(
                PeerGroup.document_id == document_id, PeerGroup.input_hash == input_hash
            )
        )
        if existing:
            return existing
        group = PeerGroup(
            source_company_id=profile.company_id,
            document_id=document_id,
            company_profile_id=profile.id,
            domain_classification_id=classification.id if classification else None,
            taxonomy_version=classification.taxonomy_version if classification else None,
            policy_version=self.policy["version"],
            engine_version=PEER_ENGINE_VERSION,
            universe_provider="development_fixture_provider",
            universe_version=UNIVERSE_VERSION,
            universe_snapshot_hash=snapshot,
            input_hash=input_hash,
            status="INSUFFICIENT_CLASSIFICATION",
            created_at=now(),
        )
        self.session.add(group)
        self.session.flush()
        write_audit_log(
            self.session,
            entity_type="peer_group",
            entity_id=group.id,
            action="PEER_DISCOVERY_STARTED",
            event_type="PEER_DISCOVERY_STARTED",
            company_id=profile.company_id,
            user_id=actor.id,
        )
        if (
            classification is None
            or status_value not in self.policy["eligible_classification_statuses"]
        ):
            return group
        fields = list(
            self.session.scalars(
                select(ExtractedField).where(
                    ExtractedField.company_profile_id == profile.id,
                    ExtractedField.field_name.in_(["product", "service", "operating_segment"]),
                )
            )
        )
        source_products = (
            set().union(*(tokens(x.normalized_value) for x in fields)) if fields else set()
        )
        source_text = tokens(profile.business_description)
        weights = self.policy["weights"]
        scored = []
        primary = {x.listed_company_id: x for x in listings if x.is_primary}
        for company in companies.values():
            s = float(company.sector == classification.sector)
            i = float(company.industry == classification.industry)
            d = float(company.domain == classification.domain)
            sd = float(company.sub_domain == classification.sub_domain)
            ct = tokens(company.business_description)
            b = len(source_text & ct) / math.sqrt(max(1, len(source_text)) * max(1, len(ct)))
            cp = set().union(*(tokens(x) for x in company.products_json or []))
            p = (
                len(source_products & cp) / len(source_products | cp)
                if source_products | cp
                else 0.0
            )
            score = sum(
                weights[k] * v
                for k, v in {
                    "sector": s,
                    "industry": i,
                    "domain": d,
                    "sub_domain": sd,
                    "business_similarity": b,
                    "product_overlap": p,
                }.items()
            )
            if score < self.policy["minimum_similarity"] or company.id not in primary:
                continue
            rationale = []
            if s:
                rationale.append(f"Same sector: {classification.sector}")
            if i:
                rationale.append(f"Same industry: {classification.industry}")
            if d:
                rationale.append(f"Same domain: {classification.domain}")
            if sd:
                rationale.append(f"Same sub-domain: {classification.sub_domain}")
            if p:
                rationale.append(
                    "Product/service overlap: " + ", ".join(sorted(source_products & cp))
                )
            scored.append((score, company, primary[company.id], s, i, d, sd, b, p, rationale))
        scored.sort(key=lambda x: (-x[0], x[1].canonical_name))
        limit = min(max_peers or self.policy["maximum_peers"], self.policy["maximum_peers"])
        low_conf = (
            status_value != "VERIFIED"
            or classification.overall_confidence < self.policy["review_threshold"]
        )
        for rank, item in enumerate(scored[:limit], 1):
            score, company, listing, s, i, d, sd, b, p, rationale = item
            member_status = (
                "NEEDS_REVIEW"
                if low_conf or score < self.policy["review_threshold"]
                else (
                    "HIGH_CONFIDENCE"
                    if score >= self.policy["high_threshold"]
                    else "MEDIUM_CONFIDENCE"
                )
            )
            self.session.add(
                PeerGroupMember(
                    peer_group_id=group.id,
                    listed_company_id=company.id,
                    stock_listing_id=listing.id,
                    rank=rank,
                    similarity_score=score,
                    sector_score=s,
                    industry_score=i,
                    domain_score=d,
                    sub_domain_score=sd,
                    business_similarity_score=b,
                    product_overlap_score=p,
                    status=member_status,
                    review_required=member_status == "NEEDS_REVIEW",
                    rationale_json=rationale,
                    created_at=now(),
                )
            )
        group.status = "NEEDS_REVIEW" if low_conf else ("READY" if scored else "NO_PEERS_FOUND")
        event = (
            "PEER_DISCOVERY_REVIEW_REQUIRED"
            if group.status == "NEEDS_REVIEW"
            else "PEER_DISCOVERY_COMPLETED"
        )
        write_audit_log(
            self.session,
            entity_type="peer_group",
            entity_id=group.id,
            action=event,
            event_type=event,
            company_id=profile.company_id,
            user_id=actor.id,
            metadata_json={"peer_count": min(len(scored), limit)},
        )
        return group


@dataclass(frozen=True)
class DailyBar:
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int
    currency: str = "INR"
    is_adjusted: bool = False


class MarketDataProvider(Protocol):
    provider_name: str
    provider_version: str

    def get_daily_bars(
        self, exchange: str, symbol: str, start_date: date, end_date: date
    ) -> list[DailyBar]: ...
    def get_symbol_metadata(self, exchange: str, symbol: str) -> dict[str, object]: ...
    def health_check(self) -> bool: ...


class FixtureMarketDataProvider:
    provider_name = "development_fixture_provider"
    provider_version = "fixture_market_data_v1"

    def get_daily_bars(
        self, exchange: str, symbol: str, start_date: date, end_date: date
    ) -> list[DailyBar]:
        if symbol == "FAIL":
            raise RuntimeError("fixture symbol failure")
        result = []
        cursor = start_date
        base = Decimal(
            100 + int(hashlib.sha256(f"{exchange}:{symbol}".encode()).hexdigest()[:2], 16)
        )
        while cursor <= end_date:
            if cursor.weekday() < 5:
                delta = Decimal((cursor - start_date).days) / Decimal("10")
                close = base + delta
                result.append(
                    DailyBar(
                        cursor,
                        close - 1,
                        close + 2,
                        close - 2,
                        close,
                        close,
                        100000 + (cursor - start_date).days,
                        is_adjusted=True,
                    )
                )
            cursor += timedelta(days=1)
        return result

    def get_symbol_metadata(self, exchange: str, symbol: str) -> dict[str, object]:
        return {"exchange": exchange, "symbol": symbol, "currency": "INR"}

    def health_check(self) -> bool:
        return True


class MarketDataService:
    def __init__(self, session: Session, provider: MarketDataProvider | None = None):
        self.session = session
        self.provider = provider or FixtureMarketDataProvider()
        self.freshness = json.loads(
            Path(__file__).with_name("market_data_freshness_policy_v1.json").read_text()
        )

    def sync(
        self,
        actor_id: UUID,
        start_date: date,
        end_date: date,
        exchange: str | None = None,
        symbols: list[str] | None = None,
    ) -> MarketDataRun:
        actor = CreditRagIndexService(self.session)._user(actor_id)
        query = select(StockListing).where(
            StockListing.listing_status == "ACTIVE", StockListing.security_type == "EQUITY"
        )
        if exchange:
            query = query.where(StockListing.exchange == exchange)
        if symbols:
            query = query.where(StockListing.symbol.in_([x.upper() for x in symbols]))
        listings = list(self.session.scalars(query))
        input_hash = digest(
            {
                "provider": self.provider.provider_version,
                "ids": [str(x.id) for x in listings],
                "start": start_date,
                "end": end_date,
            }
        )
        existing = self.session.scalar(
            select(MarketDataRun).where(MarketDataRun.input_hash == input_hash)
        )
        if existing:
            return existing
        run = MarketDataRun(
            provider=self.provider.provider_name,
            provider_version=self.provider.provider_version,
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
            symbol_count=len(listings),
            success_count=0,
            failure_count=0,
            status="RUNNING",
            input_hash=input_hash,
            started_at=now(),
        )
        self.session.add(run)
        self.session.flush()
        write_audit_log(
            self.session,
            entity_type="market_data_run",
            entity_id=run.id,
            action="MARKET_DATA_SYNC_STARTED",
            event_type="MARKET_DATA_SYNC_STARTED",
            user_id=actor.id,
        )
        for listing in listings:
            try:
                bars = self.provider.get_daily_bars(
                    listing.exchange, listing.symbol, start_date, end_date
                )
                for bar in bars:
                    if (
                        min(bar.open, bar.high, bar.low, bar.close) <= 0
                        or not (
                            bar.low <= bar.open <= bar.high and bar.low <= bar.close <= bar.high
                        )
                        or bar.volume < 0
                    ):
                        raise ValueError("invalid OHLCV")
                    if (
                        self.session.scalar(
                            select(StockPrice).where(
                                StockPrice.stock_listing_id == listing.id,
                                StockPrice.trade_date == bar.trade_date,
                                StockPrice.provider == self.provider.provider_name,
                                StockPrice.provider_version == self.provider.provider_version,
                            )
                        )
                        is None
                    ):
                        self.session.add(
                            StockPrice(
                                stock_listing_id=listing.id,
                                market_data_run_id=run.id,
                                trade_date=bar.trade_date,
                                open=bar.open,
                                high=bar.high,
                                low=bar.low,
                                close=bar.close,
                                adjusted_close=bar.adjusted_close,
                                volume=bar.volume,
                                currency=bar.currency,
                                provider=self.provider.provider_name,
                                provider_version=self.provider.provider_version,
                                retrieved_at=now(),
                                is_adjusted=bar.is_adjusted,
                                created_at=now(),
                            )
                        )
                listing.last_price_date = max((x.trade_date for x in bars), default=None)
                listing.price_data_status = self.status(listing.last_price_date, end_date)
                run.success_count += 1
            except Exception as error:
                run.failure_count += 1
                listing.price_data_status = "PARTIAL"
                self.session.add(
                    MarketDataError(
                        market_data_run_id=run.id,
                        stock_listing_id=listing.id,
                        symbol=listing.symbol,
                        error_code="PROVIDER_SYMBOL_FAILED",
                        message=str(error)[:500],
                        created_at=now(),
                    )
                )
                write_audit_log(
                    self.session,
                    entity_type="market_data_run",
                    entity_id=run.id,
                    action="MARKET_DATA_SYMBOL_FAILED",
                    event_type="MARKET_DATA_SYMBOL_FAILED",
                    user_id=actor.id,
                    metadata_json={"symbol": listing.symbol},
                )
        run.status = (
            "PARTIAL"
            if run.failure_count and run.success_count
            else ("FAILED" if run.failure_count else "COMPLETED")
        )
        run.completed_at = now()
        write_audit_log(
            self.session,
            entity_type="market_data_run",
            entity_id=run.id,
            action="MARKET_DATA_SYNC_COMPLETED",
            event_type="MARKET_DATA_SYNC_COMPLETED",
            user_id=actor.id,
            metadata_json={"success": run.success_count, "failed": run.failure_count},
        )
        return run

    def status(self, last: date | None, as_of: date | None = None) -> str:
        if last is None:
            return "MISSING"
        age = ((as_of or date.today()) - last).days
        return (
            "CURRENT"
            if age <= self.freshness["current_calendar_days"]
            else ("STALE" if age <= self.freshness["stale_calendar_days"] else "MISSING")
        )
