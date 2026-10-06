from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.stock_intelligence import (
    components_payload,
    ranking_payload,
    score_payload,
)
from app.api.v1.stock_intelligence import (
    router as stock_intelligence_router,
)
from app.models.stock_analytics import StockFeature, StockFeatureRun
from app.models.stock_intelligence import (
    StockIntelligenceComponent,
    StockIntelligenceComponentInput,
    StockRankingMember,
)
from app.models.stock_ml import (
    StockMLDataset,
    StockMLModel,
    StockMLPrediction,
    StockMLRun,
)
from app.services.stock_intelligence.service import (
    COMPONENT_NAMES,
    StockIntelligenceService,
)
from app.services.stock_ml.service import (
    StockMlDatasetBuilder,
    StockModelTrainer,
    StockWalkForwardBuilder,
)
from tests.test_day24_stock_ml import _ml_context

FEATURE_VALUES = {
    "REVENUE": Decimal("100"),
    "EBITDA": Decimal("20"),
    "PAT": Decimal("10"),
    "OPERATING_CASH_FLOW": Decimal("15"),
    "FREE_CASH_FLOW": Decimal("10"),
    "ROE": Decimal("0.18"),
    "ROA": Decimal("0.10"),
    "EBITDA_MARGIN": Decimal("0.20"),
    "NET_MARGIN": Decimal("0.12"),
    "DEBT_TO_EQUITY": Decimal("0.80"),
    "REVENUE_YOY": Decimal("0.12"),
    "EBITDA_YOY": Decimal("0.10"),
    "PAT_YOY": Decimal("0.08"),
    "EPS_YOY": Decimal("0.09"),
    "OPERATING_CASH_FLOW_YOY": Decimal("0.11"),
    "FREE_CASH_FLOW_YOY": Decimal("0.10"),
    "RETURN_1M": Decimal("0.05"),
    "RETURN_3M": Decimal("0.10"),
    "RETURN_6M": Decimal("0.15"),
    "RETURN_12M": Decimal("0.20"),
    "PRICE_TO_SMA20": Decimal("1.05"),
    "PRICE_TO_SMA50": Decimal("1.08"),
    "PRICE_TO_SMA200": Decimal("1.10"),
    "VOLATILITY_20D": Decimal("0.25"),
    "VOLATILITY_60D": Decimal("0.28"),
    "VOLATILITY_252D": Decimal("0.30"),
    "MAX_DRAWDOWN_3M": Decimal("-0.12"),
    "MAX_DRAWDOWN_6M": Decimal("-0.18"),
    "MAX_DRAWDOWN_12M": Decimal("-0.25"),
}


def _add_day25_features(session: Session, runs: list[StockFeatureRun]) -> None:
    listing_order = {
        listing_id: index
        for index, listing_id in enumerate(sorted({run.stock_listing_id for run in runs}, key=str))
    }
    for run in runs:
        listing_index = listing_order[run.stock_listing_id]
        existing = set(
            session.scalars(
                select(StockFeature.feature_name).where(StockFeature.feature_run_id == run.id)
            )
        )
        for name, base_value in FEATURE_VALUES.items():
            value = base_value + Decimal(listing_index) / Decimal("100")
            if listing_index == 0 and name in {
                "PAT",
                "OPERATING_CASH_FLOW",
                "FREE_CASH_FLOW",
                "ROE",
                "ROA",
                "EBITDA_MARGIN",
                "NET_MARGIN",
            }:
                value = Decimal("-0.20")
            if listing_index == 0 and name.startswith(("RETURN_", "PRICE_TO_SMA")):
                value = Decimal("0.80") if name.startswith("RETURN_") else Decimal("1.30")
            if listing_index == 0 and name.startswith("VOLATILITY_"):
                value = Decimal("0.90")
            if listing_index == 0 and name.startswith("MAX_DRAWDOWN_"):
                value = Decimal("-0.70")
            if name not in existing:
                session.add(
                    StockFeature(
                        feature_run_id=run.id,
                        feature_name=name,
                        feature_group="DAY25_FIXTURE",
                        value=value,
                        status="AVAILABLE",
                        source_count=0,
                        created_at=run.created_at,
                    )
                )
        percentile = Decimal(listing_index) / Decimal("9")
        for group in ("PEER_GROUP", "INDUSTRY", "SECTOR"):
            for metric in ("PE", "PB", "EV_TO_EBITDA", "FCF_YIELD"):
                name = f"{group}_{metric}_PERCENTILE"
                if name not in existing:
                    session.add(
                        StockFeature(
                            feature_run_id=run.id,
                            feature_name=name,
                            feature_group=(
                                "PEER_RELATIVE" if group == "PEER_GROUP" else "SECTOR_RELATIVE"
                            ),
                            value=percentile,
                            status="AVAILABLE",
                            source_count=0,
                            created_at=run.created_at,
                        )
                    )
    session.flush()


def _day25_context(session: Session):
    admin, listings, dates = _ml_context(session)
    feature_runs = list(session.scalars(select(StockFeatureRun)))
    _add_day25_features(session, feature_runs)
    dataset = StockMlDatasetBuilder(session).build(dates[0], dates[-1], admin.id)
    splits = StockWalkForwardBuilder(session).build(dataset.id, admin.id)
    trainer = StockModelTrainer(session)
    for split in splits:
        trainer.train(split.id, admin.id)
    selected_model = session.scalar(
        select(StockMLModel).where(StockMLModel.selected_for_research.is_(True))
    )
    assert selected_model is not None
    prediction = session.scalar(
        select(StockMLPrediction)
        .where(StockMLPrediction.ml_run_id == selected_model.ml_run_id)
        .order_by(StockMLPrediction.created_at)
        .limit(1)
    )
    assert prediction is not None
    from app.models.stock_ml import StockMLDatasetRow

    row = session.get(StockMLDatasetRow, prediction.dataset_row_id)
    assert row is not None
    return admin, listings, dates, dataset, splits, selected_model, row


def test_day25_policy_score_components_lineage_and_idempotency(db_session: Session) -> None:
    admin, _, _, _, _, selected_model, row = _day25_context(db_session)
    day24_counts = (
        db_session.scalar(select(func.count()).select_from(StockMLDataset)),
        db_session.scalar(select(func.count()).select_from(StockMLRun)),
        db_session.scalar(select(func.count()).select_from(StockMLPrediction)),
    )
    service = StockIntelligenceService(db_session)
    assert sum(Decimal(str(value)) for value in service.fusion["weights"].values()) == 100
    run = service.build_score(row.stock_listing_id, row.as_of_date, admin.id)
    repeated = service.build_score(row.stock_listing_id, row.as_of_date, admin.id)
    assert repeated.id == run.id
    assert run.score is not None and Decimal("0") <= run.score <= Decimal("100")
    assert run.status in {"AVAILABLE", "PARTIAL"}
    assert run.coverage >= Decimal("0.70")
    assert run.production_use_permitted is False
    components = list(
        db_session.scalars(
            select(StockIntelligenceComponent).where(StockIntelligenceComponent.run_id == run.id)
        )
    )
    assert {component.component_name for component in components} == set(COMPONENT_NAMES)
    assert sum(component.configured_weight for component in components) == Decimal("100")
    for component in components:
        if component.normalized_score is not None:
            assert component.contribution == component.normalized_score * component.effective_weight
    ml_component = next(item for item in components if item.component_name == "ML_SIGNAL")
    assert ml_component.confidence <= Decimal("0.50")
    assert selected_model.lifecycle == "PIPELINE_VALIDATION_ONLY"
    ml_inputs = list(
        db_session.scalars(
            select(StockIntelligenceComponentInput).where(
                StockIntelligenceComponentInput.component_id == ml_component.id
            )
        )
    )
    assert {item.source_type for item in ml_inputs} == {
        "STOCK_ML_PREDICTION",
        "STOCK_ML_MODEL",
        "STOCK_ML_RUN",
        "STOCK_ML_DATASET",
    }
    assert service.validate_lineage(run.id)
    assert score_payload(run)["production_use_permitted"] is False
    assert len(components_payload(db_session, run.id)) == 11
    source = db_session.scalar(
        select(StockFeature)
        .join(StockFeatureRun)
        .where(
            StockFeatureRun.stock_listing_id == row.stock_listing_id,
            StockFeatureRun.as_of_date == row.as_of_date,
            StockFeature.feature_name == "RETURN_6M",
        )
        .limit(1)
    )
    assert source is not None and source.value is not None
    original = source.value
    source.value += Decimal("0.01")
    changed = service.build_score(row.stock_listing_id, row.as_of_date, admin.id)
    assert changed.id != run.id
    source.value = original
    assert day24_counts == (
        db_session.scalar(select(func.count()).select_from(StockMLDataset)),
        db_session.scalar(select(func.count()).select_from(StockMLRun)),
        db_session.scalar(select(func.count()).select_from(StockMLPrediction)),
    )


def test_day25_missing_ml_ranking_watchlist_and_determinism(db_session: Session) -> None:
    admin, listings, dates, _, _, _, _ = _day25_context(db_session)
    service = StockIntelligenceService(db_session)
    historical = service.build_score(listings[0].id, dates[0], admin.id)
    assert historical.score is not None and historical.coverage >= Decimal("0.70")
    components = list(
        db_session.scalars(
            select(StockIntelligenceComponent).where(
                StockIntelligenceComponent.run_id == historical.id
            )
        )
    )
    assert next(item for item in components if item.component_name == "ML_SIGNAL").status == (
        "UNAVAILABLE"
    )
    ranking = service.build_ranking(dates[0], admin.id)
    repeated = service.build_ranking(dates[0], admin.id)
    assert repeated.id == ranking.id and ranking.eligible_company_count > 1
    members = list(
        db_session.scalars(
            select(StockRankingMember)
            .where(StockRankingMember.ranking_run_id == ranking.id)
            .order_by(StockRankingMember.rank)
        )
    )
    assert [member.rank for member in members] == list(range(1, len(members) + 1))
    assert [member.score for member in members] == sorted(
        [member.score for member in members], reverse=True
    )
    assert members[0].percentile == Decimal("100")
    watchlist = service.build_watchlist(ranking.id, admin.id)
    assert watchlist and all(
        item.research_priority
        in {
            "RESEARCH_PRIORITY_HIGH",
            "RESEARCH_PRIORITY_MEDIUM",
            "RESEARCH_PRIORITY_LOW",
            "INSUFFICIENT_DATA",
        }
        for item in watchlist
    )
    payload = ranking_payload(db_session, ranking)
    forbidden = {"BUY", "SELL", "HOLD", "TARGET_PRICE", "RETURN_FORECAST"}
    assert not forbidden.intersection(str(payload).upper().replace("'", " ").split())


def test_day25_insufficient_data_and_contradictions(db_session: Session) -> None:
    admin, listings, dates, _, _, _, _ = _day25_context(db_session)
    service = StockIntelligenceService(db_session)
    missing = service.build_score(listings[0].id, date(2035, 1, 1), admin.id)
    assert missing.status == "INSUFFICIENT_DATA" and missing.score is None
    score_runs = [service.build_score(listing.id, dates[0], admin.id) for listing in listings]
    assert any(run.contradictions for run in score_runs)
    assert all(run.top_positive_drivers or run.top_negative_drivers for run in score_runs)


def test_day25_routes_and_status(client: TestClient) -> None:
    paths = {route.path for route in stock_intelligence_router.routes if hasattr(route, "path")}
    assert {
        "/stock-intelligence/scores/build",
        "/stock-intelligence/scores/{score_run_id}",
        "/stock-intelligence/scores",
        "/stock-intelligence/scores/{score_run_id}/components",
        "/stock-intelligence/scores/{score_run_id}/explanation",
        "/stock-intelligence/rankings/build",
        "/stock-intelligence/rankings/{ranking_run_id}",
        "/stock-intelligence/rankings/{ranking_run_id}/watchlist",
    } <= paths
    status = client.get("/api/v1/status").json()
    assert status["development_stage"]["day"] == 29
    assert "stock_intelligence_score" in status["components"]
    assert status["components"]["trade_execution"] == "disabled"
