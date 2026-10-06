from __future__ import annotations

import hashlib
import json
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import joblib  # type: ignore[import-untyped]
from sklearn.compose import ColumnTransformer  # type: ignore[import-untyped]
from sklearn.ensemble import RandomForestClassifier  # type: ignore[import-untyped]
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from xgboost import XGBClassifier  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.stock import ListedCompany, StockPrice
from app.models.stock_analytics import StockFeature, StockFeatureRun
from app.models.stock_ml import (
    StockMLDataset,
    StockMLDatasetFeature,
    StockMLDatasetRow,
    StockMLMetric,
    StockMLModel,
    StockMLPrediction,
    StockMLRun,
    StockMLSplit,
    StockMLSplitRow,
)
from app.services.stock.authorization import require_stock_actor

DATASET_VERSION = "stock_ml_dataset_v1"
FEATURE_SET_VERSION = "stock_features_v1"
PREPROCESSING_VERSION = "stock_preprocessing_v1"
MODEL_VERSIONS = {
    "logistic_regression": "stock_logreg_v1",
    "random_forest": "stock_random_forest_v1",
    "xgboost": "stock_xgboost_v1",
}
FORBIDDEN_FEATURES = {
    "forward_return",
    "benchmark_return",
    "relative_return",
    "future_price",
    "label_class",
    "rank_target",
}


def now() -> datetime:
    return datetime.now(UTC)


def digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def policy(name: str) -> dict[str, object]:
    return json.loads(Path(__file__).with_name(name).read_text())


def policy_int(value: object) -> int:
    if not isinstance(value, int):
        raise ValueError("Policy value must be an integer")
    return value


def decimal_float(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0


def optional_decimal_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


class StockLabelBuilder:
    def __init__(self, session: Session, horizon: str = "3M"):
        self.s = session
        self.label_policy = policy("stock_label_policy_v1.json")
        horizons = self.label_policy["horizons"]
        assert isinstance(horizons, dict)
        if horizon not in horizons:
            raise AppError("STOCK_LABEL_HORIZON_INVALID", "Unsupported label horizon", 422)
        self.horizon = horizon
        self.observations = policy_int(horizons[horizon])

    def forward_return(
        self, feature_run: StockFeatureRun
    ) -> tuple[StockPrice | None, StockPrice | None, Decimal | None, str]:
        start = self.s.scalar(
            select(StockPrice)
            .where(
                StockPrice.stock_listing_id == feature_run.stock_listing_id,
                StockPrice.trade_date <= feature_run.as_of_date,
            )
            .order_by(desc(StockPrice.trade_date))
            .limit(1)
        )
        if start is None:
            return None, None, None, "INSUFFICIENT_PRICE_HISTORY"
        future = list(
            self.s.scalars(
                select(StockPrice)
                .where(
                    StockPrice.stock_listing_id == feature_run.stock_listing_id,
                    StockPrice.trade_date > start.trade_date,
                )
                .order_by(StockPrice.trade_date)
                .limit(self.observations)
            )
        )
        if len(future) < self.observations:
            return start, None, None, "CENSORED"
        end = future[-1]
        start_value = start.adjusted_close or start.close
        end_value = end.adjusted_close or end.close
        return start, end, end_value / start_value - Decimal("1"), "LABELED"

    def label_class(self, relative_return: Decimal) -> str:
        positive = Decimal(str(self.label_policy["positive_threshold"]))
        negative = Decimal(str(self.label_policy["negative_threshold"]))
        if relative_return > positive:
            return "OUTPERFORM"
        if relative_return < negative:
            return "UNDERPERFORM"
        return "NEUTRAL"


class StockMlDatasetBuilder:
    def __init__(self, session: Session):
        self.s = session
        self.label_policy = policy("stock_label_policy_v1.json")
        self.benchmark_policy = policy("stock_benchmark_policy_v1.json")
        self.split_policy = policy("stock_walk_forward_policy_v1.json")

    def build(
        self,
        start_date: date,
        end_date: date,
        actor_id: UUID,
        horizon: str = "3M",
        feature_set_version: str = FEATURE_SET_VERSION,
    ) -> StockMLDataset:
        actor = require_stock_actor(self.s, actor_id, write=True)
        runs = list(
            self.s.scalars(
                select(StockFeatureRun)
                .where(
                    StockFeatureRun.as_of_date >= start_date,
                    StockFeatureRun.as_of_date <= end_date,
                    StockFeatureRun.feature_set_version == feature_set_version,
                    StockFeatureRun.status == "COMPLETED",
                )
                .order_by(StockFeatureRun.as_of_date, StockFeatureRun.stock_listing_id)
            )
        )
        if not runs:
            raise AppError("STOCK_ML_FEATURES_MISSING", "No eligible feature runs", 422)
        label_builder = StockLabelBuilder(self.s, horizon)
        features_by_run: dict[UUID, list[StockFeature]] = {}
        labels: dict[UUID, tuple[StockPrice | None, StockPrice | None, Decimal | None, str]] = {}
        state: list[object] = []
        for run in runs:
            features = list(
                self.s.scalars(
                    select(StockFeature)
                    .where(StockFeature.feature_run_id == run.id)
                    .order_by(StockFeature.feature_name)
                )
            )
            features_by_run[run.id] = features
            label = label_builder.forward_return(run)
            labels[run.id] = label
            state.append(
                {
                    "run": str(run.id),
                    "input_hash": run.input_hash,
                    "features": [(x.feature_name, x.value, x.status) for x in features],
                    "label_prices": (
                        str(label[0].id) if label[0] else None,
                        label[0].close if label[0] else None,
                        str(label[1].id) if label[1] else None,
                        label[1].close if label[1] else None,
                    ),
                }
            )
        universe_hash = digest(
            sorted(
                self.s.scalars(
                    select(ListedCompany.universe_snapshot_hash).where(
                        ListedCompany.id.in_({x.listed_company_id for x in runs})
                    )
                )
            )
        )
        input_hash = digest(
            {
                "dataset": DATASET_VERSION,
                "feature_set": feature_set_version,
                "label_policy": self.label_policy,
                "benchmark_policy": self.benchmark_policy,
                "split_policy": self.split_policy,
                "horizon": horizon,
                "universe": universe_hash,
                "state": state,
            }
        )
        existing = self.s.scalar(
            select(StockMLDataset).where(StockMLDataset.input_hash == input_hash)
        )
        if existing:
            return existing
        catalog = sorted(
            {
                feature.feature_name
                for features in features_by_run.values()
                for feature in features
                if feature.feature_name.lower() not in FORBIDDEN_FEATURES
            }
        )
        dataset = StockMLDataset(
            dataset_version=DATASET_VERSION,
            feature_set_version=feature_set_version,
            label_policy_version=str(self.label_policy["version"]),
            benchmark_policy_version=str(self.benchmark_policy["version"]),
            split_policy_version=str(self.split_policy["version"]),
            universe_snapshot_hash=universe_hash,
            feature_schema_hash=digest(catalog),
            feature_catalog_json=catalog,
            input_hash=input_hash,
            status="BUILDING",
            dataset_readiness="INSUFFICIENT_DATA",
            label_horizon=horizon,
            row_count=0,
            company_count=len({x.listed_company_id for x in runs}),
            listing_count=len({x.stock_listing_id for x in runs}),
            positive_count=0,
            negative_count=0,
            neutral_count=0,
            censored_count=0,
            start_date=start_date,
            end_date=end_date,
            created_at=now(),
        )
        self.s.add(dataset)
        self.s.flush()
        write_audit_log(
            self.s,
            entity_type="stock_ml_dataset",
            entity_id=dataset.id,
            action="STOCK_ML_DATASET_BUILD_STARTED",
            event_type="STOCK_ML_DATASET_BUILD_STARTED",
            user_id=actor.id,
        )
        by_date: dict[date, list[tuple[StockFeatureRun, Decimal]]] = defaultdict(list)
        for run in runs:
            result = labels[run.id][2]
            if result is not None:
                by_date[run.as_of_date].append((run, result))
        minimum = policy_int(self.benchmark_policy["minimum_members"])
        benchmarks = {
            day: sum((value for _, value in values), Decimal("0")) / Decimal(len(values))
            for day, values in by_date.items()
            if len(values) >= minimum
        }
        pending_rows: list[tuple[StockMLDatasetRow, Decimal | None]] = []
        for run in runs:
            start, end, forward, label_status = labels[run.id]
            benchmark = benchmarks.get(run.as_of_date)
            relative = (
                forward - benchmark if forward is not None and benchmark is not None else None
            )
            status = label_status
            if forward is not None and benchmark is None:
                status = "INSUFFICIENT_BENCHMARK"
            label_class = label_builder.label_class(relative) if relative is not None else None
            row = StockMLDatasetRow(
                dataset_id=dataset.id,
                listed_company_id=run.listed_company_id,
                stock_listing_id=run.stock_listing_id,
                feature_run_id=run.id,
                as_of_date=run.as_of_date,
                label_reference_date=end.trade_date if end else None,
                start_price_id=start.id if start else None,
                end_price_id=end.id if end else None,
                forward_return=forward,
                benchmark_return=benchmark,
                relative_return=relative,
                label_class=label_class,
                rank_target=None,
                benchmark_type="BROAD_UNIVERSE_MEAN_RETURN" if benchmark is not None else None,
                benchmark_reference=run.as_of_date.isoformat() if benchmark is not None else None,
                eligibility_status=status,
                created_at=now(),
            )
            self.s.add(row)
            self.s.flush()
            pending_rows.append((row, relative))
            for feature in features_by_run[run.id]:
                if feature.feature_name.lower() in FORBIDDEN_FEATURES:
                    continue
                self.s.add(
                    StockMLDatasetFeature(
                        dataset_row_id=row.id,
                        feature_name=feature.feature_name,
                        feature_value=feature.value if feature.status == "AVAILABLE" else None,
                        feature_status=feature.status,
                        created_at=now(),
                    )
                )
        rows_by_date: dict[date, list[tuple[StockMLDatasetRow, Decimal]]] = defaultdict(list)
        for row, value in pending_rows:
            if value is not None:
                rows_by_date[row.as_of_date].append((row, value))
        for values in rows_by_date.values():
            values.sort(key=lambda item: (item[1], str(item[0].id)))
            for rank, (row, _) in enumerate(values):
                row.rank_target = (
                    Decimal(rank) / Decimal(len(values) - 1) if len(values) > 1 else Decimal("0.5")
                )
        dataset.row_count = len(pending_rows)
        dataset.positive_count = sum(row.label_class == "OUTPERFORM" for row, _ in pending_rows)
        dataset.negative_count = sum(row.label_class == "UNDERPERFORM" for row, _ in pending_rows)
        dataset.neutral_count = sum(row.label_class == "NEUTRAL" for row, _ in pending_rows)
        dataset.censored_count = sum(
            row.eligibility_status == "CENSORED" for row, _ in pending_rows
        )
        labeled = dataset.positive_count + dataset.negative_count + dataset.neutral_count
        dataset.dataset_readiness = "PIPELINE_VALIDATED" if labeled >= 20 else "INSUFFICIENT_DATA"
        dataset.status = "PIPELINE_VALIDATED" if labeled else "PARTIAL"
        write_audit_log(
            self.s,
            entity_type="stock_ml_dataset",
            entity_id=dataset.id,
            action="STOCK_ML_DATASET_BUILD_COMPLETED",
            event_type="STOCK_ML_DATASET_BUILD_COMPLETED",
            user_id=actor.id,
            metadata_json={"rows": dataset.row_count, "labeled": labeled},
        )
        return dataset


class StockWalkForwardBuilder:
    def __init__(self, session: Session):
        self.s = session
        self.policy = policy("stock_walk_forward_policy_v1.json")

    def build(self, dataset_id: UUID, actor_id: UUID) -> list[StockMLSplit]:
        actor = require_stock_actor(self.s, actor_id, write=True)
        dataset = self.s.get(StockMLDataset, dataset_id)
        if dataset is None:
            raise AppError("STOCK_ML_DATASET_NOT_FOUND", "Stock ML dataset not found", 404)
        existing = list(
            self.s.scalars(
                select(StockMLSplit)
                .where(StockMLSplit.dataset_id == dataset.id)
                .order_by(StockMLSplit.split_index)
            )
        )
        if existing:
            return existing
        rows = list(
            self.s.scalars(
                select(StockMLDatasetRow)
                .where(StockMLDatasetRow.dataset_id == dataset.id)
                .order_by(StockMLDatasetRow.as_of_date)
            )
        )
        dates = sorted({row.as_of_date for row in rows})
        minimum_train_dates = policy_int(self.policy["minimum_train_dates"])
        step = policy_int(self.policy["step_dates"])
        embargo = policy_int(self.policy["embargo_calendar_days"])
        result: list[StockMLSplit] = []
        split_index = 1
        for cursor in range(minimum_train_dates, len(dates) - 1, step):
            validation_date = dates[cursor]
            test_date = dates[cursor + 1]
            train_dates = dates[:cursor]
            split = StockMLSplit(
                dataset_id=dataset.id,
                split_policy_version=str(self.policy["version"]),
                split_index=split_index,
                train_start=train_dates[0],
                train_end=train_dates[-1],
                validation_start=validation_date,
                validation_end=validation_date,
                test_start=test_date,
                test_end=test_date,
                embargo_days=embargo,
                purged_count=0,
                status="READY",
                created_at=now(),
            )
            self.s.add(split)
            self.s.flush()
            training_cutoff = validation_date - timedelta(days=embargo)
            for row in rows:
                partition: str | None = None
                if row.eligibility_status != "LABELED":
                    if row.as_of_date <= test_date:
                        partition = "CENSORED"
                elif row.as_of_date in train_dates:
                    if (
                        row.as_of_date >= training_cutoff
                        or row.label_reference_date is None
                        or row.label_reference_date >= validation_date
                    ):
                        partition = "PURGED"
                        split.purged_count += 1
                    else:
                        partition = "TRAIN"
                elif row.as_of_date == validation_date:
                    partition = "VALIDATION"
                elif row.as_of_date == test_date:
                    partition = "TEST"
                if partition:
                    self.s.add(
                        StockMLSplitRow(
                            split_id=split.id,
                            dataset_row_id=row.id,
                            partition=partition,
                            created_at=now(),
                        )
                    )
            result.append(split)
            split_index += 1
        if not result:
            raise AppError("STOCK_ML_SPLITS_INSUFFICIENT_DATES", "Not enough dates for splits", 422)
        write_audit_log(
            self.s,
            entity_type="stock_ml_dataset",
            entity_id=dataset.id,
            action="STOCK_ML_SPLITS_BUILT",
            event_type="STOCK_ML_SPLITS_BUILT",
            user_id=actor.id,
            metadata_json={"split_count": len(result)},
        )
        return result


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    result = [0.0] * len(values)
    for rank, index in enumerate(order):
        result[index] = float(rank)
    return result


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_scale = sum((x - left_mean) ** 2 for x in left) ** 0.5
    right_scale = sum((y - right_mean) ** 2 for y in right) ** 0.5
    return numerator / (left_scale * right_scale) if left_scale and right_scale else None


class StockModelTrainer:
    def __init__(self, session: Session):
        self.s = session
        self.selection_policy = policy("stock_model_selection_policy_v1.json")

    def _data(
        self, split: StockMLSplit
    ) -> tuple[
        StockMLDataset,
        list[str],
        dict[str, list[tuple[StockMLDatasetRow, list[float | None], int]]],
    ]:
        dataset = self.s.get(StockMLDataset, split.dataset_id)
        assert dataset is not None
        names = list(dataset.feature_catalog_json)
        assignments = list(
            self.s.execute(
                select(StockMLSplitRow, StockMLDatasetRow)
                .join(StockMLDatasetRow, StockMLDatasetRow.id == StockMLSplitRow.dataset_row_id)
                .where(
                    StockMLSplitRow.split_id == split.id,
                    StockMLSplitRow.partition.in_(("TRAIN", "VALIDATION", "TEST")),
                    StockMLDatasetRow.label_class.in_(("OUTPERFORM", "UNDERPERFORM")),
                )
                .order_by(StockMLDatasetRow.as_of_date, StockMLDatasetRow.stock_listing_id)
            )
        )
        output: dict[str, list[tuple[StockMLDatasetRow, list[float | None], int]]] = defaultdict(
            list
        )
        for assignment, row in assignments:
            values = {
                feature.feature_name: feature.feature_value
                for feature in self.s.scalars(
                    select(StockMLDatasetFeature).where(
                        StockMLDatasetFeature.dataset_row_id == row.id
                    )
                )
            }
            output[assignment.partition].append(
                (
                    row,
                    [optional_decimal_float(values.get(name)) for name in names],
                    1 if row.label_class == "OUTPERFORM" else 0,
                )
            )
        return dataset, names, output

    def _pipeline(
        self, model_name: str, feature_count: int, seed: int
    ) -> tuple[Pipeline, dict[str, object]]:
        numeric = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                (
                    "scaler",
                    StandardScaler() if model_name == "logistic_regression" else "passthrough",
                ),
            ]
        )
        preprocessor = ColumnTransformer([("numeric", numeric, list(range(feature_count)))])
        if model_name == "logistic_regression":
            parameters: dict[str, object] = {
                "max_iter": 500,
                "class_weight": "balanced",
                "random_state": seed,
            }
            classifier: Any = LogisticRegression(**parameters)
        elif model_name == "random_forest":
            parameters = {
                "n_estimators": 100,
                "max_depth": 5,
                "min_samples_leaf": 2,
                "class_weight": "balanced",
                "random_state": seed,
                "n_jobs": 1,
            }
            classifier = RandomForestClassifier(**parameters)
        elif model_name == "xgboost":
            parameters = {
                "n_estimators": 50,
                "max_depth": 3,
                "learning_rate": 0.05,
                "subsample": 0.9,
                "colsample_bytree": 0.9,
                "objective": "binary:logistic",
                "eval_metric": "logloss",
                "random_state": seed,
                "n_jobs": 1,
            }
            classifier = XGBClassifier(**parameters)
        else:
            raise AppError("STOCK_ML_MODEL_INVALID", "Unsupported stock model", 422)
        return Pipeline([("preprocessor", preprocessor), ("classifier", classifier)]), parameters

    def train(
        self, split_id: UUID, actor_id: UUID, models: list[str] | None = None
    ) -> list[StockMLRun]:
        actor = require_stock_actor(self.s, actor_id, write=True)
        split = self.s.get(StockMLSplit, split_id)
        if split is None:
            raise AppError("STOCK_ML_SPLIT_NOT_FOUND", "Stock ML split not found", 404)
        dataset, feature_names, data = self._data(split)
        train_rows = data["TRAIN"]
        if len(train_rows) < 2 or len({row[2] for row in train_rows}) < 2:
            raise AppError(
                "STOCK_ML_TRAINING_DATA_INSUFFICIENT", "Training needs both classes", 422
            )
        selected_models = models or ["logistic_regression", "random_forest", "xgboost"]
        seed = policy_int(self.selection_policy["random_state"])
        result: list[StockMLRun] = []
        for model_name in selected_models:
            version = MODEL_VERSIONS.get(model_name)
            if version is None:
                raise AppError("STOCK_ML_MODEL_INVALID", "Unsupported stock model", 422)
            existing = self.s.scalar(
                select(StockMLRun).where(
                    StockMLRun.split_id == split.id,
                    StockMLRun.model_name == model_name,
                    StockMLRun.model_version == version,
                )
            )
            if existing:
                result.append(existing)
                continue
            pipeline, parameters = self._pipeline(model_name, len(feature_names), seed)
            run = StockMLRun(
                dataset_id=dataset.id,
                split_id=split.id,
                model_name=model_name,
                model_version=version,
                task_type="BINARY_OUTPERFORMANCE_CLASSIFICATION",
                hyperparameters_json=parameters,
                preprocessing_version=PREPROCESSING_VERSION,
                random_state=seed,
                lifecycle=str(self.selection_policy["lifecycle"]),
                status="RUNNING",
                started_at=now(),
                completed_at=None,
                created_at=now(),
            )
            self.s.add(run)
            self.s.flush()
            x_train = [row[1] for row in train_rows]
            y_train = [row[2] for row in train_rows]
            pipeline.fit(x_train, y_train)
            for partition in ("VALIDATION", "TEST"):
                partition_rows = data[partition]
                if not partition_rows:
                    continue
                x_values = [row[1] for row in partition_rows]
                targets = [row[2] for row in partition_rows]
                probabilities = [float(value) for value in pipeline.predict_proba(x_values)[:, 1]]
                predictions = [int(value >= 0.5) for value in probabilities]
                for (row, _, _), probability, predicted in zip(
                    partition_rows, probabilities, predictions
                ):
                    self.s.add(
                        StockMLPrediction(
                            ml_run_id=run.id,
                            dataset_row_id=row.id,
                            partition=partition,
                            prediction_score=Decimal(str(probability)),
                            prediction_probability=Decimal(str(probability)),
                            predicted_class="OUTPERFORM" if predicted else "UNDERPERFORM",
                            rank_score=Decimal(str(probability)),
                            created_at=now(),
                        )
                    )
                metrics: dict[str, float] = {
                    "support": float(len(targets)),
                    "precision": float(precision_score(targets, predictions, zero_division=0)),
                    "recall": float(recall_score(targets, predictions, zero_division=0)),
                    "f1": float(f1_score(targets, predictions, zero_division=0)),
                    "brier_score": float(brier_score_loss(targets, probabilities)),
                }
                if len(set(targets)) > 1:
                    metrics["roc_auc"] = float(roc_auc_score(targets, probabilities))
                    metrics["pr_auc"] = float(average_precision_score(targets, probabilities))
                relative = [decimal_float(row[0].relative_return) for row in partition_rows]
                spearman = _correlation(_ranks(probabilities), _ranks(relative))
                if spearman is not None:
                    metrics["spearman"] = spearman
                ordered = sorted(zip(probabilities, relative), key=lambda item: item[0])
                quintile = max(1, len(ordered) // 5)
                bottom = sum(value for _, value in ordered[:quintile]) / quintile
                top = sum(value for _, value in ordered[-quintile:]) / quintile
                metrics["top_quintile_relative_return"] = top
                metrics["bottom_quintile_relative_return"] = bottom
                metrics["top_bottom_spread"] = top - bottom
                for name, value in metrics.items():
                    self.s.add(
                        StockMLMetric(
                            ml_run_id=run.id,
                            partition=partition,
                            metric_name=name,
                            metric_value=Decimal(str(value)),
                            metric_json=None,
                            created_at=now(),
                        )
                    )
                matrix = confusion_matrix(targets, predictions, labels=[0, 1]).tolist()
                self.s.add(
                    StockMLMetric(
                        ml_run_id=run.id,
                        partition=partition,
                        metric_name="confusion_matrix",
                        metric_value=None,
                        metric_json={"labels": ["UNDERPERFORM", "OUTPERFORM"], "values": matrix},
                        created_at=now(),
                    )
                )
            artifact_dir = (
                get_settings().storage_root / "models" / "stock" / str(dataset.id) / str(run.id)
            )
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact = artifact_dir / "pipeline.joblib"
            joblib.dump(
                {
                    "pipeline": pipeline,
                    "feature_names": feature_names,
                    "feature_schema_hash": dataset.feature_schema_hash,
                    "dataset_input_hash": dataset.input_hash,
                },
                artifact,
            )
            artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
            self.s.add(
                StockMLModel(
                    ml_run_id=run.id,
                    artifact_path=(f"local://models/stock/{dataset.id}/{run.id}/pipeline.joblib"),
                    artifact_hash=artifact_hash,
                    model_name=model_name,
                    model_version=version,
                    feature_schema_hash=dataset.feature_schema_hash,
                    lifecycle=str(self.selection_policy["lifecycle"]),
                    selected_for_research=False,
                    production_use_permitted=False,
                    created_at=now(),
                )
            )
            run.status = "COMPLETED"
            run.completed_at = now()
            result.append(run)
        self.s.flush()
        for run in result:
            window_metrics = list(
                self.s.execute(
                    select(StockMLMetric.metric_name, StockMLMetric.metric_value)
                    .join(StockMLRun, StockMLRun.id == StockMLMetric.ml_run_id)
                    .where(
                        StockMLRun.dataset_id == dataset.id,
                        StockMLRun.model_name == run.model_name,
                        StockMLMetric.partition == "TEST",
                        StockMLMetric.metric_value.is_not(None),
                    )
                )
            )
            grouped: dict[str, list[Decimal]] = defaultdict(list)
            for name, value in window_metrics:
                if value is not None:
                    grouped[name].append(value)
            for name, values in grouped.items():
                summaries = {
                    f"{name}_mean": statistics.mean(values),
                    f"{name}_median": statistics.median(values),
                    f"{name}_std": statistics.pstdev(values),
                    f"{name}_min": min(values),
                    f"{name}_max": max(values),
                }
                for summary_name, aggregate_value in summaries.items():
                    aggregate_metric = self.s.scalar(
                        select(StockMLMetric).where(
                            StockMLMetric.ml_run_id == run.id,
                            StockMLMetric.partition == "AGGREGATE",
                            StockMLMetric.metric_name == summary_name,
                        )
                    )
                    if aggregate_metric is None:
                        self.s.add(
                            StockMLMetric(
                                ml_run_id=run.id,
                                partition="AGGREGATE",
                                metric_name=summary_name,
                                metric_value=aggregate_value,
                                metric_json={"window_count": len(values)},
                                created_at=now(),
                            )
                        )
                    else:
                        aggregate_metric.metric_value = aggregate_value
                        aggregate_metric.metric_json = {"window_count": len(values)}
        candidates: list[tuple[Decimal, Decimal, StockMLModel]] = []
        for run in result:
            model = self.s.scalar(select(StockMLModel).where(StockMLModel.ml_run_id == run.id))
            if model is None:
                continue
            pr_auc = self.s.scalar(
                select(StockMLMetric.metric_value).where(
                    StockMLMetric.ml_run_id == run.id,
                    StockMLMetric.partition == "AGGREGATE",
                    StockMLMetric.metric_name == "pr_auc_mean",
                )
            ) or Decimal("-1")
            roc_auc = self.s.scalar(
                select(StockMLMetric.metric_value).where(
                    StockMLMetric.ml_run_id == run.id,
                    StockMLMetric.partition == "AGGREGATE",
                    StockMLMetric.metric_name == "roc_auc_mean",
                )
            ) or Decimal("-1")
            candidates.append((pr_auc, roc_auc, model))
        if candidates:
            for model in self.s.scalars(
                select(StockMLModel).join(StockMLRun).where(StockMLRun.dataset_id == dataset.id)
            ):
                model.selected_for_research = False
            max(candidates, key=lambda item: (item[0], item[1], item[2].model_name))[
                2
            ].selected_for_research = True
        write_audit_log(
            self.s,
            entity_type="stock_ml_split",
            entity_id=split.id,
            action="STOCK_ML_TRAINING_COMPLETED",
            event_type="STOCK_ML_TRAINING_COMPLETED",
            user_id=actor.id,
            metadata_json={"models": selected_models},
        )
        return result


class StockMlService:
    def __init__(self, session: Session):
        self.datasets = StockMlDatasetBuilder(session)
        self.splits = StockWalkForwardBuilder(session)
        self.training = StockModelTrainer(session)
