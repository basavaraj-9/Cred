from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.stock import router as stock_router
from app.models.company_profile import CompanyProfile
from app.models.domain_classification import DomainClassification
from app.models.enums import ClassificationStatus, MLRunStatus
from app.models.ml import MLDataset, MLModel, MLRun
from app.models.stock import (
    ListedCompany,
    MarketDataError,
    PeerGroupMember,
    StockListing,
    StockPrice,
)
from app.services.stock.service import (
    DailyBar,
    FixtureMarketDataProvider,
    MarketDataService,
    PeerDiscoveryService,
    StockUniverseService,
)
from tests.test_day20_reporting import _review


def _stock_context(session: Session):
    _, case, admin, manager, _ = _review(session)
    profile = session.scalar(
        select(CompanyProfile).where(CompanyProfile.document_id == case.document_id)
    )
    assert profile is not None
    version = str(uuid4())
    dataset = MLDataset(
        name=f"day22-{version}",
        task_type="DOMAIN_CLASSIFICATION",
        version=version,
        description="test",
        taxonomy_version="domain_taxonomy_v1",
        record_count=1,
        storage_uri="local://test",
        sha256_hash="a" * 64,
    )
    session.add(dataset)
    session.flush()
    run = MLRun(
        task_type="DOMAIN_CLASSIFICATION",
        model_name="test",
        model_version=version,
        dataset_id=dataset.id,
        status=MLRunStatus.COMPLETED,
        parameters_json={},
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()
    model = MLModel(
        task_type="DOMAIN_CLASSIFICATION",
        model_name="test",
        model_version=version,
        run_id=run.id,
        artifact_uri="local://test",
        artifact_sha256="b" * 64,
        dataset_id=dataset.id,
        taxonomy_version="domain_taxonomy_v1",
        input_builder_version="test",
        is_active=False,
    )
    session.add(model)
    session.flush()
    classification = DomainClassification(
        analysis_job_id=profile.analysis_job_id,
        company_id=profile.company_id,
        document_id=profile.document_id,
        company_profile_id=profile.id,
        model_id=model.id,
        sector="Industrials",
        industry="Electrical Equipment",
        domain="Power Distribution Equipment",
        sub_domain="Transformers & Switchgear",
        sector_confidence=0.95,
        industry_confidence=0.94,
        domain_confidence=0.93,
        sub_domain_confidence=0.92,
        overall_confidence=0.92,
        status=ClassificationStatus.VERIFIED,
        taxonomy_version="domain_taxonomy_v1",
        model_version=version,
        dataset_version=version,
        input_builder_version="test",
        input_text_hash="c" * 64,
    )
    session.add(classification)
    session.flush()
    universe = StockUniverseService(session).sync(admin.id)
    return case, admin, manager, universe


def test_fixture_universe_nse_bse_idempotency_dual_listing_and_primary(
    db_session: Session,
) -> None:
    _, admin, _, first = _stock_context(db_session)
    second = StockUniverseService(db_session).sync(admin.id)
    assert first == second and first["version"] == "indian_listed_universe_v1"
    company = db_session.scalar(select(ListedCompany).where(ListedCompany.isin == "INE000A01001"))
    assert company is not None
    listings = list(
        db_session.scalars(select(StockListing).where(StockListing.listed_company_id == company.id))
    )
    assert {row.exchange for row in listings} == {"NSE", "BSE"}
    assert sum(row.is_primary for row in listings) == 1
    assert next(row for row in listings if row.is_primary).exchange == "NSE"
    assert db_session.scalar(select(func.count()).select_from(ListedCompany)) == 11


def test_peer_discovery_scores_rationale_exclusions_and_idempotency(db_session: Session) -> None:
    case, _, manager, _ = _stock_context(db_session)
    classification = db_session.scalar(
        select(DomainClassification).where(DomainClassification.document_id == case.document_id)
    )
    assert classification is not None
    group = PeerDiscoveryService(db_session).discover(case.document_id, manager.id)
    repeated = PeerDiscoveryService(db_session).discover(case.document_id, manager.id)
    assert repeated.id == group.id and group.status == "READY"
    members = list(
        db_session.scalars(
            select(PeerGroupMember)
            .where(PeerGroupMember.peer_group_id == group.id)
            .order_by(PeerGroupMember.rank)
        )
    )
    assert members and [row.rank for row in members] == list(range(1, len(members) + 1))
    assert all(Decimal("0") <= row.similarity_score <= Decimal("1") for row in members)
    assert any("Same domain" in reason for reason in members[0].rationale_json)
    peer_names = set(
        db_session.scalars(
            select(ListedCompany.canonical_name).where(
                ListedCompany.id.in_([row.listed_company_id for row in members])
            )
        )
    )
    assert "Example Consumer Appliances Ltd" not in peer_names
    assert "Example Power Industries Ltd" not in peer_names


def test_low_confidence_classification_gates_high_confidence(db_session: Session) -> None:
    case, _, manager, _ = _stock_context(db_session)
    classification = db_session.scalar(
        select(DomainClassification).where(DomainClassification.document_id == case.document_id)
    )
    assert classification is not None
    classification.overall_confidence = 0.58
    classification.status = "NEEDS_REVIEW"  # type: ignore[assignment]
    group = PeerDiscoveryService(db_session).discover(case.document_id, manager.id)
    members = list(
        db_session.scalars(select(PeerGroupMember).where(PeerGroupMember.peer_group_id == group.id))
    )
    assert group.status == "NEEDS_REVIEW"
    assert all(row.status == "NEEDS_REVIEW" and row.review_required for row in members)


def test_daily_prices_decimal_weekends_idempotency_and_freshness(db_session: Session) -> None:
    _, admin, _, _ = _stock_context(db_session)
    listing = db_session.scalar(
        select(StockListing).where(StockListing.exchange == "NSE", StockListing.symbol == "EXTRANS")
    )
    assert listing is not None
    service = MarketDataService(db_session)
    run = service.sync(admin.id, date(2026, 9, 21), date(2026, 9, 27), symbols=["EXTRANS"])
    repeated = service.sync(admin.id, date(2026, 9, 21), date(2026, 9, 27), symbols=["EXTRANS"])
    prices = list(
        db_session.scalars(select(StockPrice).where(StockPrice.stock_listing_id == listing.id))
    )
    assert repeated.id == run.id and len(prices) == 5
    assert all(isinstance(row.close, Decimal) and row.trade_date.weekday() < 5 for row in prices)
    assert listing.price_data_status == "CURRENT"
    assert service.status(date(2026, 8, 1), date(2026, 9, 27)) == "MISSING"
    assert service.status(None) == "MISSING"


def test_market_data_partial_symbol_failure_does_not_rollback_success(db_session: Session) -> None:
    _, admin, _, _ = _stock_context(db_session)
    failed = db_session.scalar(select(StockListing).where(StockListing.symbol == "EXPOWER"))
    assert failed is not None
    failed.symbol = "FAIL"
    run = MarketDataService(db_session).sync(
        admin.id, date(2026, 9, 24), date(2026, 9, 25), symbols=["EXTRANS", "FAIL"]
    )
    assert run.status == "PARTIAL" and run.success_count == 1 and run.failure_count == 1
    assert db_session.scalar(
        select(MarketDataError).where(MarketDataError.market_data_run_id == run.id)
    )
    assert db_session.scalar(
        select(StockPrice).join(StockListing).where(StockListing.symbol == "EXTRANS")
    )


def test_ohlc_validation_rejects_invalid_symbol_without_losing_run(db_session: Session) -> None:
    class InvalidProvider(FixtureMarketDataProvider):
        provider_version = "invalid_fixture_v1"

        def get_daily_bars(self, exchange: str, symbol: str, start_date: date, end_date: date):
            return [
                DailyBar(
                    start_date, Decimal("10"), Decimal("9"), Decimal("8"), Decimal("11"), None, -1
                )
            ]

    _, admin, _, _ = _stock_context(db_session)
    run = MarketDataService(db_session, InvalidProvider()).sync(
        admin.id, date(2026, 9, 25), date(2026, 9, 25), symbols=["EXTRANS"]
    )
    assert run.status == "FAILED" and run.failure_count == 1


def test_day22_api_routes_are_registered() -> None:
    paths = {route.path for route in stock_router.routes if hasattr(route, "path")}
    assert {
        "/stock-universe/sync",
        "/stock-universe",
        "/stock-universe/{company_id}",
        "/documents/{document_id}/peers/discover",
        "/documents/{document_id}/peers",
        "/peer-groups/{group_id}",
        "/market-data/sync",
        "/stocks/{listing_id}/prices",
        "/stocks/{listing_id}/market-data-status",
    }.issubset(paths)
