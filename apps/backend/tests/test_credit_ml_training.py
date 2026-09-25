from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.credit.artifacts import ArtifactError, load_verified_artifact, save_artifact
from app.ml.credit.dataset import CreditMLDatasetService
from app.ml.credit.evaluation import evaluate_binary
from app.ml.credit.feature_schema import FEATURE_BUILDER_VERSION, FEATURE_SCHEMA_VERSION
from app.ml.credit.inference import CreditMLInferenceService
from app.ml.credit.models import MODEL_VERSIONS, build_candidate, feature_diagnostics
from app.ml.credit.observations import create_observation
from app.ml.credit.preprocessing import build_preprocessor, infer_feature_layout, matrix
from app.ml.credit.selection import SELECTION_POLICY_VERSION, select_model
from app.ml.credit.training import (
    TRAINING_CONFIG_VERSION,
    CreditMLTrainingService,
    load_verified_dataset,
    training_config,
)
from app.models import Company
from app.models.credit_ml import CreditMLDatasetReport, CreditMLFeatureSnapshot, CreditOutcome
from app.models.enums import CreditLabelQuality, CreditOutcomeType, VerificationStatus
from app.models.ml import MLDataset, MLMetric, MLModel, MLRun


def feature_rows() -> list[dict[str, object]]:
    return [
        {"current_ratio": 1.0, "sector": "A"},
        {"current_ratio": None, "sector": "B"},
        {"current_ratio": 3.0, "sector": "A"},
    ]


def test_train_only_preprocessing_and_unknown_categories() -> None:
    rows = feature_rows()
    layout = infer_feature_layout(rows)
    preprocessor = build_preprocessor(layout, scale_numeric=True)
    transformed = preprocessor.fit_transform(matrix(rows, layout))
    assert transformed.shape[0] == 3
    numeric = preprocessor.named_transformers_["numeric"]
    assert float(numeric.named_steps["imputer"].statistics_[0]) == 2.0
    categorical = preprocessor.named_transformers_["categorical"]
    assert set(categorical.named_steps["encoder"].categories_[0]) == {"A", "B"}
    unseen = preprocessor.transform(
        matrix([{"current_ratio": 10.0, "sector": "TEST_ONLY"}], layout)
    )
    assert unseen.shape[1] == transformed.shape[1]
    assert rows == feature_rows()


@pytest.mark.parametrize("name", ["logistic_regression", "random_forest", "xgboost"])
def test_candidate_training_probability_reproducibility_and_diagnostics(name: str) -> None:
    rows = [
        {"current_ratio": 0.5, "sector": "A"},
        {"current_ratio": 0.7, "sector": "A"},
        {"current_ratio": 1.5, "sector": "B"},
        {"current_ratio": 1.7, "sector": "B"},
        {"current_ratio": None, "sector": None},
        {"current_ratio": 1.2, "sector": "A"},
    ]
    y = [1, 1, 0, 0, 1, 0]
    layout = infer_feature_layout(rows)
    x = matrix(rows, layout)
    first = build_candidate(name, layout, training_config(), seed=42, scale_pos_weight=1.0)
    second = build_candidate(name, layout, training_config(), seed=42, scale_pos_weight=1.0)
    first.fit(x, y)
    second.fit(x, y)
    first_probability = first.predict_proba(x)[:, 1]
    second_probability = second.predict_proba(x)[:, 1]
    assert all(0 <= float(value) <= 1 for value in first_probability)
    assert list(first_probability) == pytest.approx(list(second_probability))
    assert feature_diagnostics(first)
    if name == "logistic_regression":
        assert (
            "scaler" in first.named_steps["preprocessor"].named_transformers_["numeric"].named_steps
        )
        assert first.named_steps["classifier"].class_weight == "balanced"
    if name == "xgboost":
        assert first.named_steps["classifier"].scale_pos_weight == 1.0


def test_binary_metrics_and_single_class_unavailable() -> None:
    class FixedModel:
        def predict_proba(self, x):
            import numpy as np

            values = [[0.8, 0.2], [0.1, 0.9], [0.7, 0.3], [0.2, 0.8]]
            return np.array(values[: len(x)])

    report = evaluate_binary(FixedModel(), [[0], [1], [2], [3]], [0, 1, 0, 1])
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    assert {
        "accuracy",
        "precision",
        "recall",
        "f1",
        "balanced_accuracy",
        "roc_auc",
        "pr_auc",
        "brier_score",
        "log_loss",
    } <= metrics.keys()
    single = evaluate_binary(FixedModel(), [[0], [1]], [0, 0])
    assert single["unavailable"] == {
        "roc_auc": "Split contains only one target class",
        "pr_auc": "Split contains only one target class",
        "balanced_accuracy": "Split contains only one target class",
    }


def test_selection_uses_validation_policy_and_fallback() -> None:
    selected, _ = select_model(
        {
            "logistic_regression": {"metrics": {"pr_auc": 0.6, "brier_score": 0.2}},
            "random_forest": {"metrics": {"pr_auc": 0.7, "brier_score": 0.3}},
        }
    )
    assert selected == "random_forest"
    fallback, reason = select_model(
        {
            "logistic_regression": {"metrics": {"brier_score": 0.2}},
            "random_forest": {"metrics": {"brier_score": 0.2}},
        }
    )
    assert fallback == "logistic_regression" and "fallback" in reason
    assert SELECTION_POLICY_VERSION == "credit_model_selection_policy_v1"


def test_artifact_integrity_and_full_pipeline_load(tmp_path: Path) -> None:
    uri, digest = save_artifact(
        tmp_path,
        "credit_test_v1",
        {"model": object(), "feature_names": ["x"]},
        {"model_version": "credit_test_v1"},
    )
    assert load_verified_artifact(tmp_path, uri, digest)["feature_names"] == ["x"]
    path = tmp_path / uri.removeprefix("local://")
    path.write_bytes(path.read_bytes() + b"corrupt")
    with pytest.raises(ArtifactError, match="INTEGRITY"):
        load_verified_artifact(tmp_path, uri, digest)
    with pytest.raises(ArtifactError, match="UNAVAILABLE"):
        load_verified_artifact(tmp_path, "local://models/credit/missing/model.joblib", digest)


def _synthetic_dataset(
    db_session: Session, root: Path
) -> tuple[MLDataset, list[CreditMLFeatureSnapshot]]:
    snapshots: list[CreditMLFeatureSnapshot] = []
    base = date(2010, 1, 1)
    for index in range(10):
        company = Company(legal_name=f"Day 12 Synthetic Company {index}")
        db_session.add(company)
        db_session.flush()
        observed = base + timedelta(days=index * 365)
        cutoff = datetime.combine(observed, datetime.max.time(), tzinfo=UTC)
        observation = create_observation(
            db_session,
            company_id=company.id,
            observation_date=observed,
            as_of_fiscal_year=f"FY{observed.year}",
            feature_cutoff_timestamp=cutoff,
        )
        positive = index in {1, 4, 8}
        db_session.add(
            CreditOutcome(
                company_id=company.id,
                observation_date=observed,
                outcome_date=(
                    observed + timedelta(days=100) if positive else observation.outcome_window_end
                ),
                outcome_type=(
                    CreditOutcomeType.DEFAULT if positive else CreditOutcomeType.NO_DEFAULT
                ),
                source_type="SYNTHETIC_FIXTURE",
                label_quality=CreditLabelQuality.SYNTHETIC,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
        features: dict[str, object] = {
            "current_ratio": None if index == 2 else 0.7 + index / 10,
            "financial_completeness": 0.8 + index / 100,
            "sector": "TRAIN_A" if index < 7 else "LATER_ONLY",
            "anomaly_persistent_net_loss": int(positive),
        }
        snapshot = CreditMLFeatureSnapshot(
            observation_id=observation.id,
            company_id=company.id,
            observation_date=observed,
            feature_cutoff_timestamp=cutoff,
            feature_builder_version=FEATURE_BUILDER_VERSION,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            feature_group="ANOMALY_ENRICHED_V1",
            features_json=features,
            feature_count=4,
            missing_feature_count=int(features["current_ratio"] is None),
            input_hash=hashlib.sha256(f"day12-{index}".encode()).hexdigest(),
            availability_complete=False,
        )
        db_session.add(snapshot)
        snapshots.append(snapshot)
    db_session.flush()
    CreditMLDatasetService(db_session, root).build()
    dataset = db_session.scalar(select(MLDataset).where(MLDataset.name == "credit_default_dataset"))
    assert dataset is not None
    return dataset, snapshots


def test_training_dataset_integrity_blocks_mutation(db_session: Session, tmp_path: Path) -> None:
    dataset, _ = _synthetic_dataset(db_session, tmp_path)
    report = db_session.scalar(
        select(CreditMLDatasetReport).where(CreditMLDatasetReport.dataset_id == dataset.id)
    )
    assert report is not None
    rows, metadata = load_verified_dataset(dataset, report, tmp_path)
    assert len(rows) == 10 and metadata["training_readiness"] == "PIPELINE_VALIDATED"
    path = tmp_path / "data" / dataset.storage_uri.removeprefix("data://")
    path.write_text(path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="INTEGRITY"):
        load_verified_dataset(dataset, report, tmp_path)


def test_full_credit_training_registry_artifacts_and_inference(
    db_session: Session, tmp_path: Path
) -> None:
    dataset, snapshots = _synthetic_dataset(db_session, tmp_path)
    result = CreditMLTrainingService(db_session, tmp_path, tmp_path / "storage").train()
    assert result["split_counts"] == {"TRAIN": 7, "VALIDATION": 2, "TEST": 1}
    assert set(result["models_trained"]) == {
        "logistic_regression",
        "random_forest",
        "xgboost",
    }
    assert result["production_use_permitted"] is False
    assert result["readiness"] == "PIPELINE_VALIDATED"
    assert result["test"]["unavailable"] == {  # type: ignore[index]
        "roc_auc": "Split contains only one target class",
        "pr_auc": "Split contains only one target class",
        "balanced_accuracy": "Split contains only one target class",
    }
    assert db_session.scalar(select(func.count()).select_from(MLRun)) == 3
    assert db_session.scalar(select(func.count()).select_from(MLModel)) == 3
    assert db_session.scalar(select(func.count()).select_from(MLMetric)) > 0
    active = db_session.scalar(
        select(MLModel).where(MLModel.task_type == "CREDIT_RISK", MLModel.is_active.is_(True))
    )
    assert active is not None
    assert active.lifecycle_status == "PIPELINE_VALIDATION_ONLY"
    assert active.model_readiness_status == "PIPELINE_VALIDATED"
    assert active.dataset_id == dataset.id
    assert active.training_mode == "PIPELINE_VALIDATION"
    assert active.selection_policy_version == SELECTION_POLICY_VERSION
    assert active.metadata_json and active.metadata_json["feature_diagnostics"]
    prediction = CreditMLInferenceService(db_session, tmp_path / "storage").predict(snapshots[0].id)
    assert 0 <= prediction["probability_of_default"] <= 1  # type: ignore[operator]
    assert prediction["production_use_permitted"] is False
    assert prediction["model_readiness"] == "PIPELINE_VALIDATED"
    assert TRAINING_CONFIG_VERSION == "credit_training_config_v1"
    for version in MODEL_VERSIONS.values():
        assert (tmp_path / "storage/models/credit" / version / "pipeline.joblib").is_file()


def test_pipeline_validation_cannot_request_production_training(
    db_session: Session, tmp_path: Path
) -> None:
    _synthetic_dataset(db_session, tmp_path)
    with pytest.raises(ValueError, match="PRODUCTION_TRAINING"):
        CreditMLTrainingService(db_session, tmp_path, tmp_path / "storage").train(
            training_mode="PRODUCTION_TRAINING"
        )
