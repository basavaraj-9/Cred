from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.stock_analytics import (
    feature_payload,
    fundamentals,
    relative,
    valuation_payload,
)
from app.api.v1.stock_analytics import (
    router as analytics_router,
)
from app.models.stock import ListedCompany, StockListing, StockPrice
from app.models.stock_analytics import (
    SectorMetric,
    SectorMetricRun,
    StockFeature,
    StockFeatureInput,
    StockFundamental,
    StockFundamentalRun,
    StockValuation,
    StockValuationInput,
)
from app.services.stock.service import MarketDataService, PeerDiscoveryService
from app.services.stock_analytics.service import (
    FEATURE_SET,
    FeatureService,
    FundamentalService,
    RelativeMetricService,
    ValuationService,
)
from tests.test_day22_stock import _stock_context


def _context(session: Session):
    case, admin, manager, _ = _stock_context(session)
    PeerDiscoveryService(session).discover(case.document_id, manager.id)
    FundamentalService(session).sync(admin.id)
    listings = list(
        session.scalars(
            select(StockListing).where(
                StockListing.is_primary.is_(True), StockListing.listing_status == "ACTIVE"
            )
        )
    )
    MarketDataService(session).sync(
        admin.id, date(2025, 8, 1), date(2026, 9, 25), symbols=[x.symbol for x in listings]
    )
    return admin, listings


def test_fundamental_sync_periods_availability_currency_and_idempotency(
    db_session: Session,
) -> None:
    admin, listings = _context(db_session)
    company_id = listings[0].listed_company_id
    before = list(
        db_session.scalars(
            select(StockFundamentalRun).where(StockFundamentalRun.listed_company_id == company_id)
        )
    )
    FundamentalService(db_session).sync(admin.id, [company_id])
    after = list(
        db_session.scalars(
            select(StockFundamentalRun).where(StockFundamentalRun.listed_company_id == company_id)
        )
    )
    assert len(before) == len(after) == 2 and all(
        x.availability_date > x.period_end for x in after if x.availability_date
    )
    values = list(
        db_session.scalars(
            select(StockFundamental).where(StockFundamental.listed_company_id == company_id)
        )
    )
    assert {x.currency for x in values if x.metric_code == "REVENUE"} == {"INR"}
    assert any(
        x.metric_code == "PAT" and x.value < 0
        for x in db_session.scalars(
            select(StockFundamental)
            .join(ListedCompany)
            .where(ListedCompany.canonical_name.contains("Oil Foods"))
        )
    )


def test_valuation_formulas_negative_states_and_asof_leakage(db_session: Session) -> None:
    admin, listings = _context(db_session)
    # PostgreSQL does not guarantee row order; choose a profitable fixture for
    # the positive-denominator assertions below.
    listing = next(
        item
        for item in sorted(listings, key=lambda row: row.symbol)
        if db_session.scalar(
            select(StockFundamental.id)
            .where(
                StockFundamental.listed_company_id == item.listed_company_id,
                StockFundamental.metric_code == "PAT",
                StockFundamental.period_end == date(2026, 3, 31),
                StockFundamental.value > 0,
            )
            .limit(1)
        )
        is not None
    )
    service = ValuationService(db_session)
    early = service.build(listing.id, date(2026, 4, 30), admin.id)
    assert early.fundamental_run_id is not None
    selected = db_session.get(StockFundamentalRun, early.fundamental_run_id)
    assert selected and selected.period_end == date(2025, 3, 31)
    run = service.build(listing.id, date(2026, 9, 25), admin.id)
    metrics = {
        x.metric_code: x
        for x in db_session.scalars(
            select(StockValuation).where(StockValuation.valuation_run_id == run.id)
        )
    }
    assert metrics["MARKET_CAP"].value and metrics["ENTERPRISE_VALUE"].value and metrics["PE"].value
    assert db_session.scalar(
        select(StockValuationInput).where(
            StockValuationInput.stock_valuation_id == metrics["MARKET_CAP"].id
        )
    )
    assert valuation_payload(db_session, run)["metrics"]
    oil = next(x for x in listings if "OILFOOD" == x.symbol)
    oil_run = service.build(oil.id, date(2026, 9, 25), admin.id)
    pe = db_session.scalar(
        select(StockValuation).where(
            StockValuation.valuation_run_id == oil_run.id, StockValuation.metric_code == "PE"
        )
    )
    assert pe and pe.value is None and pe.status == "NOT_MEANINGFUL"


def test_relative_metrics_group_controls_and_feature_store(db_session: Session) -> None:
    admin, listings = _context(db_session)
    valuation = ValuationService(db_session)
    for listing in listings:
        valuation.build(listing.id, date(2026, 9, 25), admin.id)
    RelativeMetricService(db_session).build(date(2026, 9, 25), admin.id)
    metrics = list(db_session.scalars(select(SectorMetric)))
    assert metrics
    assert {
        metric_run.group_type for metric_run in db_session.scalars(select(SectorMetricRun))
    } >= {
        "PEER_GROUP",
        "INDUSTRY",
        "SECTOR",
    }
    assert all(x.percentile is None or Decimal(0) <= x.percentile <= Decimal(1) for x in metrics)
    peer_company_id = db_session.scalar(
        select(SectorMetric.listed_company_id)
        .join(SectorMetricRun)
        .where(SectorMetricRun.group_type == "PEER_GROUP")
        .limit(1)
    )
    assert peer_company_id is not None
    listing = next(item for item in listings if item.listed_company_id == peer_company_id)
    service = FeatureService(db_session)
    run = service.build(listing.id, date(2026, 9, 25), admin.id)
    repeated = service.build(listing.id, date(2026, 9, 25), admin.id)
    assert repeated.id == run.id and run.feature_set_version == FEATURE_SET
    features = {
        x.feature_name: x
        for x in db_session.scalars(
            select(StockFeature).where(StockFeature.feature_run_id == run.id)
        )
    }
    assert (
        features["REVENUE_YOY"].status == "AVAILABLE"
        and features["RETURN_1M"].status == "AVAILABLE"
        and features["VOLATILITY_20D"].status == "AVAILABLE"
        and features["PRICE_TO_SMA20"].status == "AVAILABLE"
        and features["MAX_DRAWDOWN_3M"].status == "AVAILABLE"
    )
    relative_groups = {
        feature.feature_group
        for feature in features.values()
        if feature.feature_group in {"PEER_RELATIVE", "SECTOR_RELATIVE"}
    }
    assert relative_groups == {"PEER_RELATIVE", "SECTOR_RELATIVE"}
    assert db_session.scalar(
        select(StockFeatureInput).where(
            StockFeatureInput.stock_feature_id == features["RETURN_1M"].id
        )
    )
    assert fundamentals(peer_company_id, admin.id, session=db_session)
    assert relative(peer_company_id, admin.id, session=db_session)
    assert feature_payload(db_session, run)["features"]


def test_feature_asof_excludes_future_prices_and_fundamentals(db_session: Session) -> None:
    admin, listings = _context(db_session)
    listing = listings[0]
    cutoff = date(2026, 4, 30)
    for candidate in listings:
        ValuationService(db_session).build(candidate.id, date(2026, 9, 25), admin.id)
    RelativeMetricService(db_session).build(date(2026, 9, 25), admin.id)
    run = FeatureService(db_session).build(listing.id, cutoff, admin.id)
    inputs = list(
        db_session.scalars(
            select(StockFeatureInput)
            .join(StockFeature)
            .where(StockFeature.feature_run_id == run.id)
        )
    )
    price_ids = [x.source_reference_id for x in inputs if x.source_type == "PRICE"]
    assert all(
        x.trade_date <= cutoff
        for x in db_session.scalars(select(StockPrice).where(StockPrice.id.in_(price_ids)))
    )
    fundamental_ids = [x.source_reference_id for x in inputs if x.source_type == "FUNDAMENTAL"]
    assert all(
        x.availability_date and x.availability_date <= cutoff
        for x in db_session.scalars(
            select(StockFundamental).where(StockFundamental.id.in_(fundamental_ids))
        )
    )
    relative_ids = [x.source_reference_id for x in inputs if x.source_type == "RELATIVE_METRIC"]
    assert relative_ids == []
    assert all(
        metric_run.as_of_date <= cutoff
        for metric_run in db_session.scalars(
            select(SectorMetricRun).join(SectorMetric).where(SectorMetric.id.in_(relative_ids))
        )
    )


def test_day23_routes_registered() -> None:
    paths = {r.path for r in analytics_router.routes if hasattr(r, "path")}
    assert {
        "/stock-fundamentals/sync",
        "/stocks/{company_id}/fundamentals",
        "/stocks/{listing_id}/valuations/build",
        "/stocks/{listing_id}/valuations",
        "/sector-metrics/build",
        "/stocks/{company_id}/relative-metrics",
        "/stocks/{listing_id}/features/build",
        "/stocks/{listing_id}/features",
    }.issubset(paths)
