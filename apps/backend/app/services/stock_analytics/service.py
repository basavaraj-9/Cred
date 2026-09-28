from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
import math
import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.stock import (
    ListedCompany,
    PeerGroup,
    PeerGroupMember,
    StockListing,
    StockPrice,
)
from app.models.stock_analytics import (
    SectorMetric,
    SectorMetricRun,
    StockFeature,
    StockFeatureInput,
    StockFeatureRun,
    StockFundamental,
    StockFundamentalRun,
    StockValuation,
    StockValuationInput,
    StockValuationRun,
)
from app.services.rag.service import CreditRagIndexService

NORMALIZER = "stock_fundamental_normalizer_v1"
VAL_ENGINE = "stock_valuation_engine_v1"
FEATURE_SET = "stock_features_v1"
PROVIDER_VERSION = "fixture_fundamentals_v1"


def now():
    return datetime.now(UTC)


def digest(v):
    return hashlib.sha256(
        json.dumps(v, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class FundamentalPeriod:
    period_start: date
    period_end: date
    availability_date: date | None
    period_type: str
    scope: str
    currency: str
    metrics: dict[str, Decimal]


class StockFundamentalsProvider(Protocol):
    provider_name: str
    provider_version: str

    def get_company_fundamentals(self, company: ListedCompany) -> list[FundamentalPeriod]: ...
    def get_statement_periods(self, company: ListedCompany) -> list[date]: ...
    def health_check(self) -> bool: ...


class FixtureFundamentalsProvider:
    provider_name = "development_fixture_fundamentals_provider"
    provider_version = PROVIDER_VERSION

    def get_company_fundamentals(self, company):
        seed = int(hashlib.sha256(company.canonical_name.encode()).hexdigest()[:4], 16)
        base = Decimal(3000 + seed % 1500)
        shares = Decimal(10 + seed % 10)
        out = []
        for year, factor in [(2025, Decimal("0.9")), (2026, Decimal("1"))]:
            revenue = base * factor
            pat = revenue * Decimal("0.08")
            ebitda = revenue * Decimal("0.15")
            equity = revenue * Decimal("0.4")
            if "Oil Foods" in company.canonical_name:
                pat = -abs(pat)
            if "Metals" in company.canonical_name:
                equity = -abs(equity)
            if "Pharma" in company.canonical_name:
                ebitda = Decimal(0)
            m = {
                "REVENUE": revenue,
                "EBITDA": ebitda,
                "EBIT": ebitda * Decimal("0.8"),
                "PAT": pat,
                "EPS": pat / shares,
                "TOTAL_ASSETS": revenue,
                "TOTAL_LIABILITIES": revenue - equity,
                "TOTAL_EQUITY": equity,
                "TOTAL_DEBT": revenue * Decimal("0.18"),
                "CASH_AND_EQUIVALENTS": revenue * Decimal("0.05"),
                "OPERATING_CASH_FLOW": revenue * Decimal("0.10"),
                "CAPEX": revenue * Decimal("0.03"),
                "FREE_CASH_FLOW": revenue * Decimal("0.07"),
                "SHARES_OUTSTANDING": shares,
                "BOOK_VALUE": equity,
                "BOOK_VALUE_PER_SHARE": equity / shares,
                "DIVIDEND_PER_SHARE": Decimal("2"),
                "ROE": pat / equity if equity else Decimal(0),
                "ROA": pat / revenue,
                "EBITDA_MARGIN": ebitda / revenue,
                "NET_MARGIN": pat / revenue,
                "DEBT_TO_EQUITY": revenue * Decimal("0.18") / equity if equity else Decimal(0),
            }
            end = date(year, 3, 31)
            out.append(
                FundamentalPeriod(
                    date(year - 1, 4, 1), end, date(year, 5, 15), "ANNUAL", "CONSOLIDATED", "INR", m
                )
            )
        return out

    def get_statement_periods(self, company):
        return [x.period_end for x in self.get_company_fundamentals(company)]

    def health_check(self):
        return True


class FundamentalService:
    def __init__(self, s: Session, p: StockFundamentalsProvider | None = None):
        self.s = s
        self.p = p or FixtureFundamentalsProvider()

    def sync(self, actor: UUID, ids: list[UUID] | None = None):
        user = CreditRagIndexService(self.s)._user(actor)
        companies = (
            list(self.s.scalars(select(ListedCompany).where(ListedCompany.id.in_(ids))))
            if ids
            else list(self.s.scalars(select(ListedCompany)))
        )
        for c in companies:
            write_audit_log(
                self.s,
                entity_type="listed_company",
                entity_id=c.id,
                action="STOCK_FUNDAMENTAL_SYNC_STARTED",
                event_type="STOCK_FUNDAMENTAL_SYNC_STARTED",
                user_id=user.id,
            )
            for p in self.p.get_company_fundamentals(c):
                h = digest(p)
                run = self.s.scalar(
                    select(StockFundamentalRun).where(
                        StockFundamentalRun.listed_company_id == c.id,
                        StockFundamentalRun.input_hash == h,
                    )
                )
                if run:
                    continue
                run = StockFundamentalRun(
                    listed_company_id=c.id,
                    provider=self.p.provider_name,
                    provider_version=self.p.provider_version,
                    period_type=p.period_type,
                    statement_scope=p.scope,
                    currency=p.currency,
                    reporting_period=f"FY{p.period_end.year}",
                    period_start=p.period_start,
                    period_end=p.period_end,
                    availability_date=p.availability_date,
                    input_hash=h,
                    status="COMPLETED" if p.availability_date else "NEEDS_REVIEW",
                    started_at=now(),
                    completed_at=now(),
                )
                self.s.add(run)
                self.s.flush()
                for code, value in p.metrics.items():
                    self.s.add(
                        StockFundamental(
                            fundamental_run_id=run.id,
                            listed_company_id=c.id,
                            metric_code=code,
                            metric_name=code.replace("_", " ").title(),
                            value=value,
                            raw_value=value,
                            raw_unit="CRORE" if code != "SHARES_OUTSTANDING" else "CRORE_SHARES",
                            unit="CRORE" if code != "SHARES_OUTSTANDING" else "CRORE_SHARES",
                            currency=p.currency
                            if code
                            not in {"ROE", "ROA", "EBITDA_MARGIN", "NET_MARGIN", "DEBT_TO_EQUITY"}
                            else None,
                            period_end=p.period_end,
                            availability_date=p.availability_date,
                            statement_scope=p.scope,
                            provenance_type="REPORTED",
                            source_provider=self.p.provider_name,
                            source_reference=f"fixture:{c.id}:{p.period_end}",
                            normalization_version=NORMALIZER,
                            confidence_score=Decimal("1"),
                            status="AVAILABLE" if p.availability_date else "NEEDS_REVIEW",
                            created_at=now(),
                        )
                    )
            write_audit_log(
                self.s,
                entity_type="listed_company",
                entity_id=c.id,
                action="STOCK_FUNDAMENTAL_SYNC_COMPLETED",
                event_type="STOCK_FUNDAMENTAL_SYNC_COMPLETED",
                user_id=user.id,
            )
        return len(companies)


class ValuationService:
    def __init__(self, s):
        self.s = s
        self.policy = json.loads(
            Path(__file__).with_name("stock_valuation_policy_v1.json").read_text()
        )

    def build(self, listing_id, day, actor):
        user = CreditRagIndexService(self.s)._user(actor)
        listing = self.s.get(StockListing, listing_id)
        if not listing:
            raise AppError("STOCK_LISTING_NOT_FOUND", "Stock listing not found", 404)
        price = self.s.scalar(
            select(StockPrice)
            .where(StockPrice.stock_listing_id == listing.id, StockPrice.trade_date <= day)
            .order_by(desc(StockPrice.trade_date))
            .limit(1)
        )
        fr = self.s.scalar(
            select(StockFundamentalRun)
            .where(
                StockFundamentalRun.listed_company_id == listing.listed_company_id,
                StockFundamentalRun.availability_date <= day,
                StockFundamentalRun.status == "COMPLETED",
            )
            .order_by(desc(StockFundamentalRun.period_end))
            .limit(1)
        )
        h = digest((listing.id, day, price.id if price else None, fr.id if fr else None))
        old = self.s.scalar(
            select(StockValuationRun).where(
                StockValuationRun.stock_listing_id == listing.id, StockValuationRun.input_hash == h
            )
        )
        if old:
            return old
        run = StockValuationRun(
            listed_company_id=listing.listed_company_id,
            stock_listing_id=listing.id,
            valuation_date=day,
            fundamental_run_id=fr.id if fr else None,
            price_record_id=price.id if price else None,
            policy_version=self.policy["version"],
            engine_version=VAL_ENGINE,
            input_hash=h,
            status="COMPLETED" if price and fr else "INSUFFICIENT_INPUTS",
            created_at=now(),
        )
        self.s.add(run)
        self.s.flush()
        write_audit_log(
            self.s,
            entity_type="stock_valuation_run",
            entity_id=run.id,
            action="STOCK_VALUATION_BUILD_STARTED",
            event_type="STOCK_VALUATION_BUILD_STARTED",
            user_id=user.id,
        )
        vals = (
            {
                x.metric_code: x
                for x in self.s.scalars(
                    select(StockFundamental).where(StockFundamental.fundamental_run_id == fr.id)
                )
            }
            if fr
            else {}
        )

        def v(c):
            return vals[c].value if c in vals else None

        pricev = price.close if price else None
        shares = v("SHARES_OUTSTANDING")
        cap = pricev * shares if pricev and shares else None
        ev = (
            cap + v("TOTAL_DEBT") - v("CASH_AND_EQUIVALENTS")
            if cap and v("TOTAL_DEBT") is not None and v("CASH_AND_EQUIVALENTS") is not None
            else None
        )
        specs = {
            "MARKET_CAP": (cap, "AVAILABLE"),
            "ENTERPRISE_VALUE": (ev, "AVAILABLE"),
            "PE": (
                cap / v("PAT") if cap and v("PAT") and v("PAT") > 0 else None,
                "NOT_MEANINGFUL"
                if v("PAT") is not None and v("PAT") <= 0
                else "INSUFFICIENT_INPUTS",
            ),
            "PB": (
                cap / v("TOTAL_EQUITY")
                if cap and v("TOTAL_EQUITY") and v("TOTAL_EQUITY") > 0
                else None,
                "NOT_MEANINGFUL"
                if v("TOTAL_EQUITY") is not None and v("TOTAL_EQUITY") <= 0
                else "INSUFFICIENT_INPUTS",
            ),
            "PS": (cap / v("REVENUE") if cap and v("REVENUE") else None, "INSUFFICIENT_INPUTS"),
            "EV_TO_EBITDA": (
                ev / v("EBITDA") if ev and v("EBITDA") and v("EBITDA") > 0 else None,
                "NOT_MEANINGFUL"
                if v("EBITDA") is not None and v("EBITDA") <= 0
                else "INSUFFICIENT_INPUTS",
            ),
            "EV_TO_EBIT": (ev / v("EBIT") if ev and v("EBIT") else None, "INSUFFICIENT_INPUTS"),
            "FCF_YIELD": (
                v("FREE_CASH_FLOW") / cap if cap and v("FREE_CASH_FLOW") is not None else None,
                "INSUFFICIENT_INPUTS",
            ),
            "EARNINGS_YIELD": (
                v("PAT") / cap if cap and v("PAT") is not None else None,
                "INSUFFICIENT_INPUTS",
            ),
            "DIVIDEND_YIELD": (
                v("DIVIDEND_PER_SHARE") / pricev
                if pricev and v("DIVIDEND_PER_SHARE") is not None
                else None,
                "INSUFFICIENT_INPUTS",
            ),
            "DEBT_TO_MARKET_CAP": (
                v("TOTAL_DEBT") / cap if cap and v("TOTAL_DEBT") is not None else None,
                "INSUFFICIENT_INPUTS",
            ),
            "PRICE_TO_FCF": (
                cap / v("FREE_CASH_FLOW")
                if cap and v("FREE_CASH_FLOW") and v("FREE_CASH_FLOW") > 0
                else None,
                "INVALID_DENOMINATOR"
                if v("FREE_CASH_FLOW") is not None and v("FREE_CASH_FLOW") <= 0
                else "INSUFFICIENT_INPUTS",
            ),
        }
        for code, (value, fallback) in specs.items():
            metric = StockValuation(
                valuation_run_id=run.id,
                metric_code=code,
                value=value,
                status="AVAILABLE" if value is not None else fallback,
                formula_version=VAL_ENGINE,
                created_at=now(),
            )
            self.s.add(metric)
            self.s.flush()
            for name, obj in [("price", price), ("fundamental_run", fr)]:
                if obj:
                    self.s.add(
                        StockValuationInput(
                            stock_valuation_id=metric.id,
                            source_type=name.upper(),
                            source_reference_id=obj.id,
                            input_name=name,
                            input_value=pricev if name == "price" else None,
                            created_at=now(),
                        )
                    )
        write_audit_log(
            self.s,
            entity_type="stock_valuation_run",
            entity_id=run.id,
            action="STOCK_VALUATION_BUILD_COMPLETED",
            event_type="STOCK_VALUATION_BUILD_COMPLETED",
            user_id=user.id,
        )
        return run


class RelativeMetricService:
    def __init__(self, session: Session):
        self.s = session
        self.policy = json.loads(
            Path(__file__).with_name("sector_metrics_policy_v1.json").read_text()
        )

    def build(
        self,
        as_of: date,
        actor: UUID,
        sector: str | None = None,
        industry: str | None = None,
    ) -> list[SectorMetricRun]:
        CreditRagIndexService(self.s)._user(actor)
        company_query = select(ListedCompany)
        if sector:
            company_query = company_query.where(ListedCompany.sector == sector)
        if industry:
            company_query = company_query.where(ListedCompany.industry == industry)
        companies = list(self.s.scalars(company_query))
        eligible_ids = {company.id for company in companies}
        groups: dict[tuple[str, str], list[ListedCompany]] = {}
        for company in companies:
            groups.setdefault(("SECTOR", company.sector or "UNKNOWN"), []).append(company)
            groups.setdefault(("INDUSTRY", company.industry or "UNKNOWN"), []).append(company)
        peer_groups = list(
            self.s.scalars(select(PeerGroup).where(PeerGroup.status.in_(("READY", "PARTIAL"))))
        )
        for peer_group in peer_groups:
            member_ids = list(
                dict.fromkeys(
                    self.s.scalars(
                        select(PeerGroupMember.listed_company_id)
                        .where(PeerGroupMember.peer_group_id == peer_group.id)
                        .order_by(PeerGroupMember.rank)
                    )
                )
            )
            members = [
                member
                for member in self.s.scalars(
                    select(ListedCompany).where(ListedCompany.id.in_(member_ids))
                )
                if member.id in eligible_ids
            ]
            if members:
                groups[("PEER_GROUP", str(peer_group.id))] = members
        output = []
        for (kind, name), members in groups.items():
            snapshot = digest(sorted((str(x.id), x.universe_snapshot_hash) for x in members))
            run = SectorMetricRun(
                as_of_date=as_of,
                group_type=kind,
                sector=name
                if kind == "SECTOR"
                else (members[0].sector or "UNKNOWN" if members else "UNKNOWN"),
                industry=name if kind == "INDUSTRY" else None,
                domain=name if kind == "PEER_GROUP" else None,
                policy_version=self.policy["version"],
                universe_snapshot_hash=snapshot,
                status="COMPLETED",
                created_at=now(),
            )
            self.s.add(run)
            self.s.flush()
            output.append(run)
            has_insufficient_metric = False
            for code in ("PE", "PB", "EV_TO_EBITDA", "FCF_YIELD"):
                values = []
                for company in members:
                    valuation_run = self.s.scalar(
                        select(StockValuationRun)
                        .where(
                            StockValuationRun.listed_company_id == company.id,
                            StockValuationRun.valuation_date <= as_of,
                        )
                        .order_by(desc(StockValuationRun.valuation_date))
                        .limit(1)
                    )
                    metric = (
                        self.s.scalar(
                            select(StockValuation).where(
                                StockValuation.valuation_run_id == valuation_run.id,
                                StockValuation.metric_code == code,
                                StockValuation.status == "AVAILABLE",
                            )
                        )
                        if valuation_run
                        else None
                    )
                    if metric and metric.value is not None:
                        values.append((company, metric.value))
                values.sort(key=lambda item: (item[1], str(item[0].id)))
                count = len(values)
                mean = (
                    sum((item[1] for item in values), Decimal(0)) / count if count else Decimal(0)
                )
                deviation = (
                    Decimal(str(statistics.pstdev([float(item[1]) for item in values])))
                    if count > 1
                    else Decimal(0)
                )
                enough = count >= self.policy["minimum_group_size"]
                has_insufficient_metric = has_insufficient_metric or not enough
                for rank, (company, value) in enumerate(values, 1):
                    self.s.add(
                        SectorMetric(
                            sector_metric_run_id=run.id,
                            listed_company_id=company.id,
                            metric_code=code,
                            raw_value=value,
                            percentile=Decimal(rank - 1) / Decimal(count - 1)
                            if enough and count > 1
                            else None,
                            z_score=(value - mean) / deviation if enough and deviation else None,
                            rank=rank if enough else None,
                            eligible_company_count=count,
                            status="AVAILABLE" if enough else "INSUFFICIENT_GROUP_SIZE",
                            created_at=now(),
                        )
                    )
            if has_insufficient_metric:
                run.status = "INSUFFICIENT_GROUP_SIZE"
        return output


class FeatureService:
    def __init__(self, session: Session):
        self.s = session

    def _fundamental_feature(
        self,
        run: StockFeatureRun,
        name: str,
        group: str,
        value: Decimal | None,
        status: str,
        sources: list[StockFundamental],
    ) -> None:
        feature = StockFeature(
            feature_run_id=run.id,
            feature_name=name,
            feature_group=group,
            value=value,
            status=status,
            source_count=len(sources),
            created_at=now(),
        )
        self.s.add(feature)
        self.s.flush()
        for source in sources:
            self.s.add(
                StockFeatureInput(
                    stock_feature_id=feature.id,
                    source_type="FUNDAMENTAL",
                    source_reference_id=source.id,
                    input_name=name,
                    input_value=source.value,
                    created_at=now(),
                )
            )

    def _price_feature(
        self,
        run: StockFeatureRun,
        name: str,
        group: str,
        value: Decimal | None,
        status: str,
        sources: list[StockPrice],
    ) -> None:
        feature = StockFeature(
            feature_run_id=run.id,
            feature_name=name,
            feature_group=group,
            value=value,
            status=status,
            source_count=len(sources),
            created_at=now(),
        )
        self.s.add(feature)
        self.s.flush()
        for source in sources:
            self.s.add(
                StockFeatureInput(
                    stock_feature_id=feature.id,
                    source_type="PRICE",
                    source_reference_id=source.id,
                    input_name=name,
                    input_value=source.close,
                    created_at=now(),
                )
            )

    def _relative_feature(
        self,
        run: StockFeatureRun,
        name: str,
        group: str,
        value: Decimal | None,
        status: str,
        source: SectorMetric,
    ) -> None:
        feature = StockFeature(
            feature_run_id=run.id,
            feature_name=name,
            feature_group=group,
            value=value,
            status=status,
            source_count=1,
            created_at=now(),
        )
        self.s.add(feature)
        self.s.flush()
        self.s.add(
            StockFeatureInput(
                stock_feature_id=feature.id,
                source_type="RELATIVE_METRIC",
                source_reference_id=source.id,
                input_name=name,
                input_value=source.percentile,
                created_at=now(),
            )
        )

    def build(self, listing_id: UUID, as_of: date, actor: UUID) -> StockFeatureRun:
        user = CreditRagIndexService(self.s)._user(actor)
        listing = self.s.get(StockListing, listing_id)
        if listing is None:
            raise AppError("STOCK_LISTING_NOT_FOUND", "Stock listing not found", 404)
        prices = list(
            self.s.scalars(
                select(StockPrice)
                .where(StockPrice.stock_listing_id == listing.id, StockPrice.trade_date <= as_of)
                .order_by(StockPrice.trade_date)
            )
        )
        runs = list(
            self.s.scalars(
                select(StockFundamentalRun)
                .where(
                    StockFundamentalRun.listed_company_id == listing.listed_company_id,
                    StockFundamentalRun.availability_date <= as_of,
                    StockFundamentalRun.status == "COMPLETED",
                )
                .order_by(desc(StockFundamentalRun.period_end))
            )
        )
        relative_rows = list(
            self.s.execute(
                select(SectorMetric, SectorMetricRun)
                .join(SectorMetricRun)
                .where(
                    SectorMetric.listed_company_id == listing.listed_company_id,
                    SectorMetricRun.as_of_date <= as_of,
                )
                .order_by(desc(SectorMetricRun.as_of_date), desc(SectorMetricRun.created_at))
            )
        )
        input_hash = digest(
            {
                "price_ids": [str(x.id) for x in prices],
                "fundamental_hashes": [x.input_hash for x in runs],
                "relative_metric_ids": [str(metric.id) for metric, _ in relative_rows],
                "as_of": as_of,
                "version": FEATURE_SET,
            }
        )
        existing = self.s.scalar(
            select(StockFeatureRun).where(
                StockFeatureRun.stock_listing_id == listing.id,
                StockFeatureRun.input_hash == input_hash,
            )
        )
        if existing:
            return existing
        run = StockFeatureRun(
            listed_company_id=listing.listed_company_id,
            stock_listing_id=listing.id,
            as_of_date=as_of,
            feature_set_version=FEATURE_SET,
            input_hash=input_hash,
            status="COMPLETED",
            created_at=now(),
        )
        self.s.add(run)
        self.s.flush()
        write_audit_log(
            self.s,
            entity_type="stock_feature_run",
            entity_id=run.id,
            action="STOCK_FEATURE_BUILD_STARTED",
            event_type="STOCK_FEATURE_BUILD_STARTED",
            user_id=user.id,
        )
        current = (
            {
                x.metric_code: x
                for x in self.s.scalars(
                    select(StockFundamental).where(
                        StockFundamental.fundamental_run_id == runs[0].id
                    )
                )
            }
            if runs
            else {}
        )
        prior = (
            {
                x.metric_code: x
                for x in self.s.scalars(
                    select(StockFundamental).where(
                        StockFundamental.fundamental_run_id == runs[1].id
                    )
                )
            }
            if len(runs) > 1
            else {}
        )
        for code in (
            "REVENUE",
            "EBITDA",
            "PAT",
            "ROE",
            "ROA",
            "EBITDA_MARGIN",
            "NET_MARGIN",
            "DEBT_TO_EQUITY",
            "OPERATING_CASH_FLOW",
            "FREE_CASH_FLOW",
        ):
            sources: list[StockFundamental] = [current[code]] if code in current else []
            self._fundamental_feature(
                run,
                code,
                "FUNDAMENTAL",
                current[code].value if code in current else None,
                "AVAILABLE" if code in current else "UNAVAILABLE",
                sources,
            )
        for code in ("REVENUE", "EBITDA", "PAT", "EPS", "OPERATING_CASH_FLOW", "FREE_CASH_FLOW"):
            value = (
                current[code].value / prior[code].value - 1
                if code in current and code in prior and prior[code].value
                else None
            )
            fundamental_sources: list[StockFundamental] = []
            if code in current:
                fundamental_sources.append(current[code])
            if code in prior:
                fundamental_sources.append(prior[code])
            self._fundamental_feature(
                run,
                f"{code}_YOY",
                "GROWTH",
                value,
                "AVAILABLE" if value is not None else "UNAVAILABLE",
                fundamental_sources,
            )
        closes = [x.close for x in prices]
        for days, label in (
            (22, "RETURN_1M"),
            (66, "RETURN_3M"),
            (132, "RETURN_6M"),
            (264, "RETURN_12M"),
        ):
            value = closes[-1] / closes[-days] - Decimal("1") if len(closes) >= days else None
            self._price_feature(
                run,
                label,
                "MOMENTUM",
                value,
                "AVAILABLE" if value is not None else "INSUFFICIENT_HISTORY",
                prices[-days:] if len(closes) >= days else prices,
            )
        returns = [float(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
        for days in (20, 60, 252):
            value = (
                Decimal(str(statistics.pstdev(returns[-days:]) * math.sqrt(252)))
                if len(returns) >= days
                else None
            )
            self._price_feature(
                run,
                f"VOLATILITY_{days}D",
                "VOLATILITY",
                value,
                "AVAILABLE" if value is not None else "INSUFFICIENT_HISTORY",
                prices[-(days + 1) :] if len(returns) >= days else prices,
            )
        for days in (20, 50, 200):
            value = (
                closes[-1] / (sum(closes[-days:], Decimal("0")) / Decimal(days))
                if len(closes) >= days
                else None
            )
            self._price_feature(
                run,
                f"PRICE_TO_SMA{days}",
                "MOMENTUM",
                value,
                "AVAILABLE" if value is not None else "INSUFFICIENT_HISTORY",
                prices[-days:] if len(closes) >= days else prices,
            )
        for days, label in (
            (66, "MAX_DRAWDOWN_3M"),
            (132, "MAX_DRAWDOWN_6M"),
            (264, "MAX_DRAWDOWN_12M"),
        ):
            window = prices[-days:] if len(prices) >= days else prices
            peak: Decimal | None = None
            drawdown: Decimal | None = None
            if len(window) >= days:
                drawdown = Decimal("0")
                for price in window:
                    peak = price.close if peak is None or price.close > peak else peak
                    current_drawdown = price.close / peak - Decimal("1")
                    if current_drawdown < drawdown:
                        drawdown = current_drawdown
            self._price_feature(
                run,
                label,
                "VOLATILITY",
                drawdown,
                "AVAILABLE" if drawdown is not None else "INSUFFICIENT_HISTORY",
                window,
            )
        seen_relative: set[tuple[str, str]] = set()
        for metric, relative_run in relative_rows:
            key = (relative_run.group_type, metric.metric_code)
            if key in seen_relative:
                continue
            seen_relative.add(key)
            feature_group = (
                "PEER_RELATIVE" if relative_run.group_type == "PEER_GROUP" else "SECTOR_RELATIVE"
            )
            self._relative_feature(
                run,
                f"{relative_run.group_type}_{metric.metric_code}_PERCENTILE",
                feature_group,
                metric.percentile,
                metric.status,
                metric,
            )
        if prices:
            recent = prices[-20:]
            self._price_feature(
                run,
                "AVG_VOLUME_20D",
                "LIQUIDITY",
                Decimal(sum(x.volume for x in recent)) / Decimal(len(recent)),
                "AVAILABLE",
                recent,
            )
        write_audit_log(
            self.s,
            entity_type="stock_feature_run",
            entity_id=run.id,
            action="STOCK_FEATURE_BUILD_COMPLETED",
            event_type="STOCK_FEATURE_BUILD_COMPLETED",
            user_id=user.id,
        )
        return run
