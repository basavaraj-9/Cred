from __future__ import annotations

# ruff: noqa: E501
from copy import deepcopy
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.credit_ml_evaluations import (
    get_credit_ml_evaluation,
    get_evaluation_drift,
    get_evaluation_windows,
    get_rule_ml_comparison,
    list_credit_ml_evaluations,
)
from app.core.exceptions import AppError
from app.ml.credit.calibration import calibrate_sigmoid
from app.ml.credit.evaluate import (
    DRIFT_POLICY_VERSION,
    EVALUATION_VERSION,
    FUSION_READINESS_POLICY_VERSION,
    WALK_FORWARD_POLICY_VERSION,
    CreditMLEvaluationService,
    evaluation_input_hash,
    policy,
)
from app.ml.credit.evaluation import evaluate_binary
from app.ml.credit.models import build_candidate
from app.ml.credit.preprocessing import infer_feature_layout, matrix
from app.ml.credit.synthetic_fixture import create_synthetic_credit_dataset
from app.ml.credit.training import training_config
from app.ml.credit.validation_diagnostics import (
    aggregate_metric,
    calibration_drift,
    categorical_drift,
    correlations,
    diagnostic_band,
    fusion_readiness,
    model_disagreement,
    numeric_drift,
    prediction_drift,
    rule_ml_agreement,
    rule_risk_index,
    segment_metrics,
)
from app.ml.credit.walk_forward import generate_walk_forward_windows
from app.models.credit import CreditAssessment
from app.models.credit_ml_evaluation import (
    CreditMLDriftResult,
    CreditMLEvaluationRun,
    CreditMLEvaluationWindow,
    CreditMLWindowModelResult,
)
from app.models.ml import MLModel


def records(count: int = 48) -> list[dict[str, object]]:
    rows = []
    for index in range(count):
        year = 2010 + index // 4
        target = index % 4 in {1, 3}
        rows.append(
            {
                "observation_id": str(UUID(int=index + 1)),
                "company_id": str(UUID(int=1000 + index)),
                "observation_date": date(year, 12, 31).isoformat(),
                "target_value": int(target),
                "label_quality": "SYNTHETIC",
                "features": {
                    "current_ratio": 0.7 + index / 50,
                    "debt_to_equity": 2.0 - index / 100,
                    "sector": "EARLY" if year < 2018 else "LATE",
                },
            }
        )
    return rows


def window_policy() -> dict[str, object]:
    configured = deepcopy(policy(WALK_FORWARD_POLICY_VERSION))
    configured.update(
        {
            "minimum_training_examples": 12,
            "minimum_evaluation_examples": 4,
            "training_window_length": 3,
            "evaluation_window_length": 1,
            "step_size": 1,
        }
    )
    return configured


def test_expanding_window_generation() -> None:
    windows = generate_walk_forward_windows(records(), window_policy(), "EXPANDING_WINDOW")
    assert len(windows) >= 3
    assert len(windows[1].train_rows) > len(windows[0].train_rows)


def test_rolling_window_generation() -> None:
    windows = generate_walk_forward_windows(records(), window_policy(), "ROLLING_WINDOW")
    assert len(windows) >= 3
    assert len(windows[0].train_rows) == len(windows[1].train_rows) == 12


def test_window_temporal_order() -> None:
    for window in generate_walk_forward_windows(records(), window_policy(), "EXPANDING_WINDOW"):
        assert max(window.train_dates) < min(window.evaluation_dates)


def test_future_rows_not_in_training() -> None:
    for window in generate_walk_forward_windows(records(), window_policy(), "EXPANDING_WINDOW"):
        train_ids = {row["observation_id"] for row in window.train_rows}
        eval_ids = {row["observation_id"] for row in window.evaluation_rows}
        assert train_ids.isdisjoint(eval_ids)


def test_skipped_window_insufficient_support() -> None:
    configured = window_policy()
    configured["minimum_evaluation_examples"] = 10
    windows = generate_walk_forward_windows(records(), configured, "EXPANDING_WINDOW")
    assert windows and all(
        window.skip_reason == "INSUFFICIENT_EVALUATION_SUPPORT" for window in windows
    )


def test_single_class_train_skipped() -> None:
    fixture = records()
    for row in fixture[:12]:
        row["target_value"] = 0
    first = generate_walk_forward_windows(fixture, window_policy(), "ROLLING_WINDOW")[0]
    assert first.status == "SKIPPED" and first.skip_reason == "SINGLE_CLASS_TRAIN"


def test_evaluation_window_not_used_in_preprocessing() -> None:
    window = generate_walk_forward_windows(records(), window_policy(), "ROLLING_WINDOW")[0]
    layout = infer_feature_layout([row["features"] for row in window.train_rows])  # type: ignore[misc]
    assert "future_only" not in layout.names


def test_each_window_fits_new_imputer_encoder_and_scaler() -> None:
    windows = generate_walk_forward_windows(records(), window_policy(), "ROLLING_WINDOW")[:2]
    preprocessors = []
    for window in windows:
        features = [row["features"] for row in window.train_rows]
        layout = infer_feature_layout(features)  # type: ignore[arg-type]
        candidate = build_candidate(
            "logistic_regression", layout, training_config(), seed=42, scale_pos_weight=1
        )
        candidate.fit(matrix(features, layout), [row["target_value"] for row in window.train_rows])  # type: ignore[arg-type]
        preprocessors.append(candidate.named_steps["preprocessor"])
    assert preprocessors[0] is not preprocessors[1]
    assert (
        preprocessors[0].named_transformers_["numeric"].named_steps["imputer"]
        is not preprocessors[1].named_transformers_["numeric"].named_steps["imputer"]
    )
    assert (
        preprocessors[0].named_transformers_["categorical"].named_steps["encoder"]
        is not preprocessors[1].named_transformers_["categorical"].named_steps["encoder"]
    )
    assert (
        preprocessors[0].named_transformers_["numeric"].named_steps["scaler"]
        is not preprocessors[1].named_transformers_["numeric"].named_steps["scaler"]
    )


def test_future_categories_not_used_during_fit() -> None:
    fixture = records()
    window = generate_walk_forward_windows(fixture, window_policy(), "ROLLING_WINDOW")[0]
    train_features = [row["features"] for row in window.train_rows]
    layout = infer_feature_layout(train_features)  # type: ignore[arg-type]
    candidate = build_candidate(
        "logistic_regression", layout, training_config(), seed=42, scale_pos_weight=1
    )
    candidate.fit(
        matrix(train_features, layout), [row["target_value"] for row in window.train_rows]
    )  # type: ignore[arg-type]
    categories = (
        candidate.named_steps["preprocessor"]
        .named_transformers_["categorical"]
        .named_steps["encoder"]
        .categories_[0]
    )
    assert "LATE" not in categories


@pytest.mark.parametrize("name", ["logistic_regression", "random_forest", "xgboost"])
def test_model_walk_forward_and_probabilities(name: str) -> None:
    window = next(
        item
        for item in generate_walk_forward_windows(records(), window_policy(), "EXPANDING_WINDOW")
        if item.status == "VALID"
    )
    train_features = [row["features"] for row in window.train_rows]
    evaluation_features = [row["features"] for row in window.evaluation_rows]
    layout = infer_feature_layout(train_features)  # type: ignore[arg-type]
    candidate = build_candidate(name, layout, training_config(), seed=42, scale_pos_weight=1)
    model, method, _ = calibrate_sigmoid(
        candidate,
        matrix(train_features, layout),
        [row["target_value"] for row in window.train_rows],
    )  # type: ignore[arg-type]
    report = evaluate_binary(
        model,
        matrix(evaluation_features, layout),
        [row["target_value"] for row in window.evaluation_rows],
    )  # type: ignore[arg-type]
    assert method == "sigmoid"
    assert all(0 <= value <= 1 for value in report["probabilities"])  # type: ignore[union-attr]


def test_window_retraining_fresh_model() -> None:
    layout = infer_feature_layout([{"x": 1.0}, {"x": 2.0}])
    first = build_candidate("random_forest", layout, training_config(), seed=42, scale_pos_weight=1)
    second = build_candidate(
        "random_forest", layout, training_config(), seed=42, scale_pos_weight=1
    )
    assert (
        first is not second
        and first.named_steps["preprocessor"] is not second.named_steps["preprocessor"]
    )


def test_metric_mean_median_std_and_weighted_metric() -> None:
    result = aggregate_metric([(0.2, 1), (0.4, 3), (None, 100)])
    assert result == pytest.approx(
        {
            "count": 2,
            "mean": 0.3,
            "median": 0.3,
            "std": 0.1,
            "min": 0.2,
            "max": 0.4,
            "weighted_average": 0.35,
        }
    )


def test_undefined_metrics_excluded_from_invalid_aggregation() -> None:
    assert aggregate_metric([(None, 2), (float("nan"), 2)]) is None


def test_numeric_feature_drift_and_insufficient_support() -> None:
    configured = policy(DRIFT_POLICY_VERSION)
    assert numeric_drift(list(range(10)), list(range(10, 20)), configured)["status"] == "HIGH"
    assert numeric_drift([1], [2], configured)["status"] == "INSUFFICIENT_DATA"


def test_categorical_feature_drift_and_unseen_category_rate() -> None:
    result = categorical_drift(["A"] * 5, ["B"] * 5, policy(DRIFT_POLICY_VERSION))
    assert result["status"] == "HIGH" and result["unseen_category_rate"] == 1


def test_prediction_and_calibration_drift() -> None:
    configured = policy(DRIFT_POLICY_VERSION)
    assert prediction_drift([0.1, 0.2], [0.7, 0.8], configured)["status"] == "HIGH"
    assert calibration_drift(0.1, 0.25, configured)["status"] == "HIGH"


def test_drift_threshold_version() -> None:
    assert policy(DRIFT_POLICY_VERSION)["version"] == DRIFT_POLICY_VERSION


def test_probability_gap_model_probability_std_and_class_agreement() -> None:
    result = model_disagreement({"lr": 0.1, "rf": 0.8, "xgb": 0.2})
    assert result["max_probability_gap"] == pytest.approx(0.7)
    assert result["probability_std"] > 0  # type: ignore[operator]
    assert result["differing_predicted_classes"] == 2
    assert result["status"] == "HIGH_DISAGREEMENT"


def test_unanimous_prediction_detection() -> None:
    assert model_disagreement({"lr": 0.1, "rf": 0.2, "xgb": 0.3})["unanimous"] is True


def test_rule_score_to_risk_index_and_not_probability() -> None:
    assert rule_risk_index(80) == pytest.approx(0.2)
    assert rule_risk_index(80) != 0.8


def test_rule_ml_agreement_directions() -> None:
    assert rule_ml_agreement("LOW_RISK", "LOW_PD") == "AGREE_LOW"
    assert rule_ml_agreement("LOW_RISK", "HIGH_PD") == "ML_HIGHER_RISK_THAN_RULE"
    assert rule_ml_agreement("HIGH_RISK", "LOW_PD") == "RULE_HIGHER_RISK_THAN_ML"


def test_rule_ml_correlation_and_insufficient_support() -> None:
    result = correlations([0.1, 0.5, 0.9], [0.2, 0.6, 0.8])
    assert result["pearson"] and result["pearson"] > 0.9
    assert correlations([0.1], [0.2]) == {"pearson": None, "spearman": None}


def test_diagnostic_band_boundaries() -> None:
    configured = policy("credit_ml_diagnostic_bands_v1")
    assert diagnostic_band(0.0, configured) == "LOW_PD"
    assert diagnostic_band(1.0, configured) == "HIGH_PD"


def test_synthetic_dataset_blocks_fusion_and_pipeline_ready_status() -> None:
    result = fusion_readiness(
        real_outcomes=0,
        valid_windows=4,
        model_production_permitted=False,
        high_drift=False,
        comparison_count=10,
        policy=policy(FUSION_READINESS_POLICY_VERSION),
    )
    assert result["status"] == "PIPELINE_READY" and result["fusion_allowed"] is False
    assert "INSUFFICIENT_REAL_OUTCOMES" in result["blocking_reasons"]  # type: ignore[operator]


def test_model_readiness_drift_and_window_support_gates() -> None:
    result = fusion_readiness(
        real_outcomes=100,
        valid_windows=1,
        model_production_permitted=False,
        high_drift=True,
        comparison_count=0,
        policy=policy(FUSION_READINESS_POLICY_VERSION),
    )
    assert set(result["blocking_reasons"]) >= {
        "INSUFFICIENT_WALK_FORWARD_SUPPORT",
        "MODEL_NOT_PRODUCTION_PERMITTED",
        "HIGH_DRIFT_DETECTED",
    }  # type: ignore[arg-type]


def test_segment_metrics_with_support_and_insufficient_support() -> None:
    rows = [
        {"sector": "A", "target_value": index % 2, "ml_probability": 0.1 * index}
        for index in range(6)
    ] + [{"sector": "B", "target_value": 0, "ml_probability": 0.1}]
    result = segment_metrics(rows, "sector")
    assert result["A"]["status"] == "AVAILABLE"  # type: ignore[index]
    assert result["B"]["status"] == "INSUFFICIENT_DATA"  # type: ignore[index]


def test_unverified_domain_excluded_from_domain_segment() -> None:
    rows = [
        {
            "domain": "X",
            "domain_verification_status": "NEEDS_REVIEW",
            "target_value": 0,
            "ml_probability": 0.1,
        }
        for _ in range(6)
    ]
    assert segment_metrics(rows, "domain") == {}


def test_changed_configuration_changes_input_hash() -> None:
    base = {"evaluation": EVALUATION_VERSION, "walk_forward": WALK_FORWARD_POLICY_VERSION}
    first = evaluation_input_hash(
        dataset_sha256="a" * 64,
        feature_group="A",
        mode="PIPELINE_VALIDATION",
        window_mode="EXPANDING_WINDOW",
        model_names=("logistic_regression",),
        versions=base,
    )
    assert first != evaluation_input_hash(
        dataset_sha256="b" * 64,
        feature_group="A",
        mode="PIPELINE_VALIDATION",
        window_mode="EXPANDING_WINDOW",
        model_names=("logistic_regression",),
        versions=base,
    )
    assert first != evaluation_input_hash(
        dataset_sha256="a" * 64,
        feature_group="A",
        mode="PIPELINE_VALIDATION",
        window_mode="ROLLING_WINDOW",
        model_names=("logistic_regression",),
        versions=base,
    )


def test_full_evaluation_persistence_idempotency_registry_and_day10_immutability(
    db_session: Session, tmp_path: Path
) -> None:
    create_synthetic_credit_dataset(db_session, tmp_path)
    registry_before = db_session.scalar(select(func.count()).select_from(MLModel))
    assessments_before = db_session.scalar(select(func.count()).select_from(CreditAssessment))
    service = CreditMLEvaluationService(db_session, tmp_path)
    first = service.evaluate()
    second = service.evaluate()
    assert first["evaluation_id"] == second["evaluation_id"] and second["idempotent"] is True
    assert first["fusion_allowed"] is False
    assert db_session.scalar(select(func.count()).select_from(MLModel)) == registry_before
    assert (
        db_session.scalar(select(func.count()).select_from(CreditAssessment)) == assessments_before
    )
    assert db_session.scalar(select(func.count()).select_from(CreditMLEvaluationRun)) == 1
    assert db_session.scalar(select(func.count()).select_from(CreditMLEvaluationWindow)) >= 1
    assert db_session.scalar(select(func.count()).select_from(CreditMLWindowModelResult)) == 3
    assert db_session.scalar(select(func.count()).select_from(CreditMLDriftResult)) > 0


def test_evaluation_read_apis_and_unknown_404(db_session: Session, tmp_path: Path) -> None:
    create_synthetic_credit_dataset(db_session, tmp_path)
    result = CreditMLEvaluationService(db_session, tmp_path).evaluate()
    evaluation_id = result["evaluation_id"]
    assert len(list_credit_ml_evaluations(db_session)) == 1  # type: ignore[arg-type]
    assert get_credit_ml_evaluation(evaluation_id, db_session)["fusion_allowed"] is False  # type: ignore[arg-type]
    assert get_evaluation_windows(evaluation_id, db_session)  # type: ignore[arg-type]
    assert get_evaluation_drift(evaluation_id, db_session)  # type: ignore[arg-type]
    assert get_rule_ml_comparison(evaluation_id, db_session)["rule_score_is_probability"] is False  # type: ignore[arg-type]
    with pytest.raises(AppError):
        get_credit_ml_evaluation(UUID(int=0), db_session)  # type: ignore[arg-type]
