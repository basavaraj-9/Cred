from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import joblib  # type: ignore[import-untyped]
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.stock_ml import dataset_payload, split_payload
from app.api.v1.stock_ml import router as stock_ml_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.stock import StockListing, StockPrice
from app.models.stock_analytics import StockFeature, StockFeatureRun
from app.models.stock_ml import (
    StockMLDatasetFeature,
    StockMLDatasetRow,
    StockMLMetric,
    StockMLModel,
    StockMLPrediction,
    StockMLSplitRow,
)
from app.services.stock.service import MarketDataService
from app.services.stock_ml.service import (
    FORBIDDEN_FEATURES,
    StockLabelBuilder,
    StockMlDatasetBuilder,
    StockModelTrainer,
    StockWalkForwardBuilder,
    _correlation,
    _ranks,
)
from tests.test_day22_stock import _stock_context


def _add_feature_run(session: Session, listing: StockListing, as_of: date, index: int) -> None:
    created_at = datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC)
    run = StockFeatureRun(
        listed_company_id=listing.listed_company_id,
        stock_listing_id=listing.id,
        as_of_date=as_of,
        feature_set_version="stock_features_v1",
        input_hash=hashlib.sha256(f"day24:{listing.id}:{as_of}".encode()).hexdigest(),
        status="COMPLETED",
        created_at=created_at,
    )
    session.add(run)
    session.flush()
    for name, value, status in (
        ("VALUE_LEVEL", Decimal(index), "AVAILABLE"),
        ("VALUE_TREND", Decimal(as_of.toordinal() % 1000), "AVAILABLE"),
        ("MISSING_SIGNAL", None, "UNAVAILABLE"),
    ):
        session.add(
            StockFeature(
                feature_run_id=run.id,
                feature_name=name,
                feature_group="FUNDAMENTAL",
                value=value,
                status=status,
                source_count=1 if value is not None else 0,
                created_at=created_at,
            )
        )


def _ml_context(session: Session):
    _, admin, _, _ = _stock_context(session)
    listings = list(
        session.scalars(
            select(StockListing)
            .where(StockListing.is_primary.is_(True), StockListing.listing_status == "ACTIVE")
            .order_by(StockListing.symbol)
        )
    )
    MarketDataService(session).sync(
        admin.id,
        date(2023, 12, 1),
        date(2027, 12, 31),
        symbols=[listing.symbol for listing in listings],
    )
    as_of_dates = [
        date(2024, 1, 2),
        date(2024, 4, 1),
        date(2024, 6, 3),
        date(2024, 12, 2),
        date(2025, 6, 2),
        date(2025, 12, 1),
        date(2026, 6, 1),
        date(2027, 12, 30),
    ]
    for day in as_of_dates:
        for index, listing in enumerate(listings):
            _add_feature_run(session, listing, day, index)
    session.flush()
    return admin, listings, as_of_dates


def test_label_policy_thresholds_and_rank_diagnostics(db_session: Session) -> None:
    builder = StockLabelBuilder(db_session, "3M")
    assert builder.observations == 63
    assert builder.label_class(Decimal("0.006")) == "OUTPERFORM"
    assert builder.label_class(Decimal("-0.006")) == "UNDERPERFORM"
    assert builder.label_class(Decimal("0")) == "NEUTRAL"
    assert _ranks([2.0, 1.0, 3.0]) == [1.0, 0.0, 2.0]
    assert (_correlation([0.0, 1.0], [0.0, 1.0]) or 0) > 0.999


def test_stock_ml_dataset_splits_models_artifacts_and_leakage(db_session: Session) -> None:
    admin, listings, dates = _ml_context(db_session)
    day23_count = db_session.scalar(select(func.count()).select_from(StockFeatureRun))
    builder = StockMlDatasetBuilder(db_session)
    dataset = builder.build(dates[0], dates[-1], admin.id)
    repeated = builder.build(dates[0], dates[-1], admin.id)
    assert repeated.id == dataset.id
    assert dataset.dataset_version == "stock_ml_dataset_v1"
    assert dataset.feature_set_version == "stock_features_v1"
    assert dataset.row_count == len(listings) * len(dates)
    assert dataset.positive_count > 0 and dataset.negative_count > 0
    assert dataset.censored_count == len(listings)
    assert dataset.dataset_readiness == "PIPELINE_VALIDATED"
    rows = list(
        db_session.scalars(
            select(StockMLDatasetRow).where(StockMLDatasetRow.dataset_id == dataset.id)
        )
    )
    labeled = next(row for row in rows if row.eligibility_status == "LABELED")
    prices = list(
        db_session.scalars(
            select(StockPrice)
            .where(
                StockPrice.stock_listing_id == labeled.stock_listing_id,
                StockPrice.trade_date > labeled.as_of_date,
            )
            .order_by(StockPrice.trade_date)
            .limit(63)
        )
    )
    assert len(prices) == 63 and labeled.end_price_id == prices[-1].id
    assert labeled.label_reference_date and labeled.label_reference_date > labeled.as_of_date
    dataset_features = list(
        db_session.scalars(
            select(StockMLDatasetFeature).where(StockMLDatasetFeature.dataset_row_id == labeled.id)
        )
    )
    assert all(
        feature.feature_name.lower() not in FORBIDDEN_FEATURES for feature in dataset_features
    )
    missing = next(
        feature for feature in dataset_features if feature.feature_name == "MISSING_SIGNAL"
    )
    assert missing.feature_value is None and missing.feature_status == "UNAVAILABLE"
    splits = StockWalkForwardBuilder(db_session).build(dataset.id, admin.id)
    assert splits and splits[0].purged_count > 0 and splits[0].embargo_days == 7
    assert StockWalkForwardBuilder(db_session).build(dataset.id, admin.id)[0].id == splits[0].id
    assignments = list(
        db_session.scalars(select(StockMLSplitRow).where(StockMLSplitRow.split_id == splits[0].id))
    )
    assert len({assignment.dataset_row_id for assignment in assignments}) == len(assignments)
    assert {assignment.partition for assignment in assignments} >= {
        "TRAIN",
        "VALIDATION",
        "TEST",
        "PURGED",
    }
    trainer = StockModelTrainer(db_session)
    runs = [run for split in splits for run in trainer.train(split.id, admin.id)]
    assert {run.model_name for run in runs} == {
        "logistic_regression",
        "random_forest",
        "xgboost",
    }
    assert all(
        run.random_state == 24 and run.lifecycle == "PIPELINE_VALIDATION_ONLY" for run in runs
    )
    assert trainer.train(splits[0].id, admin.id)[0].id == runs[0].id
    models = list(db_session.scalars(select(StockMLModel)))
    assert len(models) == len(splits) * 3
    assert sum(model.selected_for_research for model in models) == 1
    assert all(not model.production_use_permitted for model in models)
    for model in models:
        artifact = get_settings().storage_root / model.artifact_path.removeprefix("local://")
        assert (
            artifact.is_file()
            and hashlib.sha256(artifact.read_bytes()).hexdigest() == model.artifact_hash
        )
        bundle = joblib.load(artifact)
        assert bundle["feature_schema_hash"] == dataset.feature_schema_hash
        saved_prediction = db_session.scalar(
            select(StockMLPrediction).where(StockMLPrediction.ml_run_id == model.ml_run_id).limit(1)
        )
        assert saved_prediction and saved_prediction.prediction_probability is not None
        saved_values = {
            feature.feature_name: feature.feature_value
            for feature in db_session.scalars(
                select(StockMLDatasetFeature).where(
                    StockMLDatasetFeature.dataset_row_id == saved_prediction.dataset_row_id
                )
            )
        }
        vector = [
            float(saved_values[name]) if saved_values.get(name) is not None else None
            for name in bundle["feature_names"]
        ]
        reloaded_probability = Decimal(str(float(bundle["pipeline"].predict_proba([vector])[0, 1])))
        assert abs(reloaded_probability - saved_prediction.prediction_probability) < Decimal(
            "0.000000001"
        )
    predictions = list(db_session.scalars(select(StockMLPrediction)))
    assert predictions and all(
        prediction.prediction_probability is not None
        and Decimal("0") <= prediction.prediction_probability <= Decimal("1")
        for prediction in predictions
    )
    metric_names = set(db_session.scalars(select(StockMLMetric.metric_name)))
    assert {
        "f1",
        "brier_score",
        "confusion_matrix",
        "spearman",
        "f1_mean",
        "f1_std",
    } <= metric_names
    selected_model = next(model for model in models if model.selected_for_research)
    aggregate_window_count = db_session.scalar(
        select(StockMLMetric.metric_json).where(
            StockMLMetric.ml_run_id == selected_model.ml_run_id,
            StockMLMetric.partition == "AGGREGATE",
            StockMLMetric.metric_name == "pr_auc_mean",
        )
    )
    assert aggregate_window_count is not None
    assert 2 <= aggregate_window_count["window_count"] <= len(splits)
    assert dataset_payload(db_session, dataset)["rows"]
    assert split_payload(db_session, splits[0])["partition_counts"]
    source_feature = db_session.scalar(
        select(StockFeature).where(StockFeature.feature_name == "VALUE_LEVEL").limit(1)
    )
    assert source_feature and source_feature.value is not None
    original_value = source_feature.value
    source_feature.value += Decimal("1")
    db_session.flush()
    changed_dataset = builder.build(dates[0], dates[-1], admin.id)
    assert changed_dataset.id != dataset.id
    source_feature.value = original_value
    assert db_session.scalar(select(func.count()).select_from(StockFeatureRun)) == day23_count


def test_stock_ml_routes_and_day24_status(client: TestClient) -> None:
    paths = {route.path for route in stock_ml_router.routes if hasattr(route, "path")}
    assert {
        "/stock-ml/datasets/build",
        "/stock-ml/datasets/{dataset_id}",
        "/stock-ml/datasets/{dataset_id}/splits/build",
        "/stock-ml/datasets/{dataset_id}/splits",
        "/stock-ml/splits/{split_id}/train",
        "/stock-ml/runs",
        "/stock-ml/runs/{run_id}/metrics",
        "/stock-ml/runs/{run_id}/predictions",
        "/stock-ml/models",
    } <= paths
    status = client.get("/api/v1/status").json()
    assert status["development_stage"]["day"] == 25
    assert "stock_ml_dataset" in status["components"]
    assert status["components"]["live_stock_predictions"] == "disabled"


def test_stock_ml_failure_paths_leave_no_partial_records(db_session: Session) -> None:
    _, admin, _, _ = _stock_context(db_session)
    with pytest.raises(AppError, match="No eligible feature runs"):
        StockMlDatasetBuilder(db_session).build(date(2030, 1, 1), date(2030, 12, 31), admin.id)
    with pytest.raises(AppError, match="Stock ML split not found"):
        StockModelTrainer(db_session).train(uuid4(), admin.id)
    assert db_session.scalar(select(func.count()).select_from(StockMLDatasetRow)) == 0
