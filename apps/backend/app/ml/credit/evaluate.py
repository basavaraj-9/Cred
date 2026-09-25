from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.repositories.audit_log import write_audit_log
from app.database.session import get_engine
from app.ml.credit.calibration import calibrate_sigmoid
from app.ml.credit.dataset import DATASET_NAME
from app.ml.credit.evaluation import evaluate_binary
from app.ml.credit.models import MODEL_VERSIONS, build_candidate
from app.ml.credit.preprocessing import infer_feature_layout, matrix
from app.ml.credit.selection import SELECTION_POLICY_VERSION
from app.ml.credit.training import TRAINING_CONFIG_VERSION, load_verified_dataset, training_config
from app.ml.credit.validation_diagnostics import (
    aggregate_model_metrics,
    calibration_drift,
    correlations,
    diagnostic_band,
    feature_drift,
    fusion_readiness,
    model_disagreement,
    prediction_drift,
    rule_ml_agreement,
    rule_risk_index,
    stability_status,
)
from app.ml.credit.walk_forward import WalkForwardWindow, generate_walk_forward_windows
from app.models.credit_ml import (
    CreditMLDatasetReport,
)
from app.models.credit_ml_evaluation import (
    CreditMLDriftResult,
    CreditMLEvaluationRun,
    CreditMLEvaluationWindow,
    CreditMLWindowModelResult,
    CreditRuleMLComparison,
)
from app.models.ml import MLDataset

EVALUATION_VERSION = "credit_ml_evaluation_v1"
WALK_FORWARD_POLICY_VERSION = "credit_walk_forward_policy_v1"
DRIFT_POLICY_VERSION = "credit_drift_policy_v1"
DIAGNOSTIC_BAND_VERSION = "credit_ml_diagnostic_bands_v1"
FUSION_READINESS_POLICY_VERSION = "credit_fusion_readiness_policy_v1"
WARNING = (
    "Synthetic development data: walk-forward results validate evaluation architecture only. "
    "They do not establish real-world credit-model quality."
)


@lru_cache
def policy(version: str) -> dict[str, object]:
    path = Path(__file__).with_name("taxonomy") / f"{version}.json"
    if not path.is_file():
        raise ValueError(f"POLICY_NOT_FOUND: {version}")
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _configuration_digest(version: str) -> str:
    path = Path(__file__).with_name("taxonomy") / f"{version}.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluation_input_hash(
    *,
    dataset_sha256: str,
    feature_group: str,
    mode: str,
    window_mode: str,
    model_names: tuple[str, ...],
    versions: dict[str, str],
) -> str:
    value = {
        "dataset_sha256": dataset_sha256,
        "feature_group": feature_group,
        "mode": mode,
        "window_mode": window_mode,
        "models": sorted(model_names),
        "versions": versions,
        "training_config": training_config(),
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _features(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [cast(dict[str, object], row["features"]) for row in rows]


def _targets(rows: list[dict[str, object]]) -> list[int]:
    return [int(cast(int, row["target_value"])) for row in rows]


def _rule_band_from_score(score: float) -> str:
    if score >= 80:
        return "LOW_RISK"
    if score >= 65:
        return "MODERATE_LOW_RISK"
    if score >= 50:
        return "MODERATE_RISK"
    if score >= 35:
        return "ELEVATED_RISK"
    return "HIGH_RISK"


def _as_date(value: object) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _window_row(run_id: UUID, window: WalkForwardWindow) -> CreditMLEvaluationWindow:
    train_dates = window.train_dates
    evaluation_dates = window.evaluation_dates
    train_y, evaluation_y = _targets(window.train_rows), _targets(window.evaluation_rows)
    return CreditMLEvaluationWindow(
        evaluation_run_id=run_id,
        window_number=window.number,
        mode=window.mode,
        train_start=min(train_dates) if train_dates else None,
        train_end=max(train_dates) if train_dates else None,
        evaluation_start=min(evaluation_dates) if evaluation_dates else None,
        evaluation_end=max(evaluation_dates) if evaluation_dates else None,
        train_count=len(train_y),
        evaluation_count=len(evaluation_y),
        train_positive=sum(train_y),
        train_negative=len(train_y) - sum(train_y),
        evaluation_positive=sum(evaluation_y),
        evaluation_negative=len(evaluation_y) - sum(evaluation_y),
        status=window.status,
        skip_reason=window.skip_reason,
        metadata_json={
            "train_observation_ids": [str(row["observation_id"]) for row in window.train_rows],
            "evaluation_observation_ids": [
                str(row["observation_id"]) for row in window.evaluation_rows
            ],
        },
        created_at=datetime.now(UTC),
    )


class CreditMLEvaluationService:
    def __init__(self, session: Session, project_root: Path) -> None:
        self.session = session
        self.project_root = project_root

    def evaluate(self, **kwargs: Any) -> dict[str, object]:
        try:
            return self._evaluate(**kwargs)
        except Exception as exc:
            try:
                with Session(self.session.get_bind()) as audit_session, audit_session.begin():
                    write_audit_log(
                        audit_session,
                        entity_type="credit_ml_evaluation_run",
                        entity_id=UUID(int=0),
                        action="CREDIT_ML_EVALUATION_FAILED",
                        event_type="CREDIT_ML_EVALUATION_FAILED",
                        metadata_json={"error_type": type(exc).__name__},
                    )
            except Exception:
                pass
            raise

    def _evaluate(
        self,
        *,
        dataset_version: str = "credit_dataset_v1",
        feature_group: str = "ANOMALY_ENRICHED_V1",
        mode: str = "PIPELINE_VALIDATION",
        walk_forward_policy_version: str = WALK_FORWARD_POLICY_VERSION,
        window_mode: str = "EXPANDING_WINDOW",
        model_names: tuple[str, ...] = (
            "logistic_regression",
            "random_forest",
            "xgboost",
        ),
    ) -> dict[str, object]:
        if mode not in {"PIPELINE_VALIDATION", "REAL_EVALUATION"}:
            raise ValueError("UNSUPPORTED_EVALUATION_MODE")
        if set(model_names) - set(MODEL_VERSIONS):
            raise ValueError("UNKNOWN_MODEL_FAMILY")
        dataset = self.session.scalar(
            select(MLDataset).where(
                MLDataset.name == DATASET_NAME, MLDataset.version == dataset_version
            )
        )
        if dataset is None:
            raise ValueError("CREDIT_DATASET_NOT_FOUND")
        report = self.session.scalar(
            select(CreditMLDatasetReport).where(CreditMLDatasetReport.dataset_id == dataset.id)
        )
        if report is None:
            raise ValueError("CREDIT_DATASET_REPORT_NOT_FOUND")
        records, metadata = load_verified_dataset(dataset, report, self.project_root)
        if metadata.get("feature_group") != feature_group:
            raise ValueError("DATASET_FEATURE_GROUP_MISMATCH")
        real_count = int(cast(int, metadata.get("real_count", 0)))
        if mode == "REAL_EVALUATION" and real_count == 0:
            raise ValueError("REAL_EVALUATION_REQUIRES_REAL_OUTCOMES")
        versions = {
            "evaluation": EVALUATION_VERSION,
            "walk_forward": walk_forward_policy_version,
            "training": TRAINING_CONFIG_VERSION,
            "selection": SELECTION_POLICY_VERSION,
            "drift": DRIFT_POLICY_VERSION,
            "diagnostic_bands": DIAGNOSTIC_BAND_VERSION,
            "fusion_readiness": FUSION_READINESS_POLICY_VERSION,
            "walk_forward_digest": _configuration_digest(walk_forward_policy_version),
            "selection_digest": _configuration_digest(SELECTION_POLICY_VERSION),
            "drift_digest": _configuration_digest(DRIFT_POLICY_VERSION),
            "diagnostic_bands_digest": _configuration_digest(DIAGNOSTIC_BAND_VERSION),
            "fusion_readiness_digest": _configuration_digest(FUSION_READINESS_POLICY_VERSION),
        }
        input_hash = evaluation_input_hash(
            dataset_sha256=dataset.sha256_hash,
            feature_group=feature_group,
            mode=mode,
            window_mode=window_mode,
            model_names=model_names,
            versions=versions,
        )
        existing = self.session.scalar(
            select(CreditMLEvaluationRun).where(CreditMLEvaluationRun.input_hash == input_hash)
        )
        if existing is not None:
            return self._result(existing, idempotent=True)
        run = CreditMLEvaluationRun(
            dataset_id=dataset.id,
            evaluation_version=EVALUATION_VERSION,
            walk_forward_policy_version=walk_forward_policy_version,
            model_selection_policy_version=SELECTION_POLICY_VERSION,
            fusion_readiness_policy_version=FUSION_READINESS_POLICY_VERSION,
            drift_policy_version=DRIFT_POLICY_VERSION,
            diagnostic_band_version=DIAGNOSTIC_BAND_VERSION,
            mode=mode,
            window_mode=window_mode,
            status="RUNNING",
            input_hash=input_hash,
            valid_window_count=0,
            skipped_window_count=0,
            summary_json={},
            fusion_readiness="NOT_READY",
            fusion_allowed=False,
            started_at=datetime.now(UTC),
        )
        self.session.add(run)
        self.session.flush()
        write_audit_log(
            self.session,
            entity_type="credit_ml_evaluation_run",
            entity_id=run.id,
            action="CREDIT_ML_EVALUATION_STARTED",
            event_type="CREDIT_ML_EVALUATION_STARTED",
            metadata_json={
                "dataset_version": dataset_version,
                "mode": mode,
                "window_mode": window_mode,
            },
        )
        window_policy = policy(walk_forward_policy_version)
        drift_policy = policy(DRIFT_POLICY_VERSION)
        band_policy = policy(DIAGNOSTIC_BAND_VERSION)
        windows = generate_walk_forward_windows(records, window_policy, window_mode)
        model_reports: dict[str, list[dict[str, object]]] = {name: [] for name in model_names}
        previous_probabilities: dict[str, list[float]] = {}
        previous_brier: dict[str, float] = {}
        disagreement_rows: list[dict[str, object]] = []
        comparison_rows: list[dict[str, object]] = []
        all_drift_statuses: list[str] = []
        for window in windows:
            persisted = _window_row(run.id, window)
            self.session.add(persisted)
            self.session.flush()
            if window.status == "SKIPPED":
                run.skipped_window_count += 1
                write_audit_log(
                    self.session,
                    entity_type="credit_ml_evaluation_window",
                    entity_id=persisted.id,
                    action="CREDIT_ML_WINDOW_SKIPPED",
                    event_type="CREDIT_ML_WINDOW_SKIPPED",
                    metadata_json={"window_number": window.number, "reason": window.skip_reason},
                )
                continue
            run.valid_window_count += 1
            train_features, evaluation_features = (
                _features(window.train_rows),
                _features(window.evaluation_rows),
            )
            for drift in feature_drift(train_features, evaluation_features, drift_policy):
                all_drift_statuses.append(str(drift["status"]))
                self.session.add(
                    CreditMLDriftResult(
                        evaluation_window_id=persisted.id,
                        feature_name=str(drift["feature_name"]),
                        drift_type="FEATURE_DRIFT",
                        metric_name=str(drift["metric_name"]),
                        metric_value=cast(float | None, drift.get("metric_value")),
                        status=str(drift["status"]),
                        threshold_version=DRIFT_POLICY_VERSION,
                        metadata_json={
                            key: value
                            for key, value in drift.items()
                            if key not in {"feature_name", "metric_name", "metric_value", "status"}
                        },
                        created_at=datetime.now(UTC),
                    )
                )
            layout = infer_feature_layout(train_features)
            train_x, evaluation_x = (
                matrix(train_features, layout),
                matrix(evaluation_features, layout),
            )
            train_y, evaluation_y = _targets(window.train_rows), _targets(window.evaluation_rows)
            counts = Counter(train_y)
            scale_pos_weight = counts[0] / counts[1]
            per_observation: list[dict[str, float]] = [dict() for _ in evaluation_y]
            for name in model_names:
                candidate = build_candidate(
                    name,
                    layout,
                    training_config(),
                    seed=int(cast(int, training_config()["random_seed"])),
                    scale_pos_weight=scale_pos_weight,
                )
                model, calibration_method, calibration_warning = calibrate_sigmoid(
                    candidate, train_x, train_y
                )
                threshold = float(cast(float, training_config()["threshold"]))
                report_json = evaluate_binary(model, evaluation_x, evaluation_y, threshold)
                report_json["calibration_method"] = calibration_method
                report_json["calibration_warning"] = calibration_warning
                model_reports[name].append(report_json)
                probabilities = cast(list[float], report_json["probabilities"])
                for index, probability in enumerate(probabilities):
                    per_observation[index][name] = probability
                prediction = prediction_drift(
                    previous_probabilities.get(name), probabilities, drift_policy
                )
                brier = cast(dict[str, float], report_json["metrics"]).get("brier_score")
                calibration = calibration_drift(previous_brier.get(name), brier, drift_policy)
                previous_probabilities[name] = probabilities
                if brier is not None:
                    previous_brier[name] = brier
                for drift_type, metric_name, drift in (
                    ("PREDICTION_DRIFT", "mean_probability_shift", prediction),
                    ("CALIBRATION_DRIFT", "brier_score_shift", calibration),
                ):
                    all_drift_statuses.append(str(drift["status"]))
                    self.session.add(
                        CreditMLDriftResult(
                            evaluation_window_id=persisted.id,
                            feature_name=None,
                            drift_type=drift_type,
                            metric_name=metric_name,
                            metric_value=cast(float | None, drift.get("metric_value")),
                            status=str(drift["status"]),
                            threshold_version=DRIFT_POLICY_VERSION,
                            metadata_json={
                                key: value
                                for key, value in drift.items()
                                if key not in {"metric_value", "status"}
                            },
                            created_at=datetime.now(UTC),
                        )
                    )
                self.session.add(
                    CreditMLWindowModelResult(
                        evaluation_window_id=persisted.id,
                        model_family=name,
                        model_version=f"{MODEL_VERSIONS[name]}:walk_forward:{window.number}",
                        calibration_method=calibration_method,
                        threshold=threshold,
                        metric_summary_json=report_json,
                        artifact_uri=None,
                        status="PIPELINE_DIAGNOSTIC_ONLY",
                        created_at=datetime.now(UTC),
                    )
                )
            for row, observation_probabilities in zip(window.evaluation_rows, per_observation):
                disagreement = model_disagreement(observation_probabilities)
                disagreement_rows.append(disagreement)
                selected_name = (
                    "random_forest"
                    if "random_forest" in observation_probabilities
                    else model_names[0]
                )
                selected_probability = observation_probabilities[selected_name]
                row_features = cast(dict[str, object], row["features"])
                rule_score = row.get("rule_score", row_features.get("credit_score"))
                rule_band = row.get("rule_risk_band")
                if isinstance(rule_score, (int, float)) and not isinstance(rule_band, str):
                    rule_band = _rule_band_from_score(float(rule_score))
                if isinstance(rule_score, (int, float)) and isinstance(rule_band, str):
                    risk_index = rule_risk_index(float(rule_score))
                    ml_band = diagnostic_band(selected_probability, band_policy)
                    comparison = {
                        "rule_risk_index": risk_index,
                        "ml_probability": selected_probability,
                        "agreement_status": rule_ml_agreement(rule_band, ml_band),
                    }
                    comparison_rows.append(comparison)
                    self.session.add(
                        CreditRuleMLComparison(
                            evaluation_run_id=run.id,
                            observation_id=UUID(str(row["observation_id"])),
                            credit_assessment_id=UUID(str(row["credit_assessment_id"]))
                            if row.get("credit_assessment_id")
                            else None,
                            ml_model_family=selected_name,
                            ml_probability=selected_probability,
                            ml_predicted_class=int(selected_probability >= 0.5),
                            rule_score=float(rule_score),
                            rule_risk_index=risk_index,
                            rule_risk_band=rule_band,
                            ml_diagnostic_band=ml_band,
                            agreement_status=str(comparison["agreement_status"]),
                            probability_gap=abs(selected_probability - risk_index),
                            metadata_json={
                                "model_probabilities": observation_probabilities,
                                "model_disagreement": disagreement,
                            },
                            created_at=datetime.now(UTC),
                        )
                    )
            write_audit_log(
                self.session,
                entity_type="credit_ml_evaluation_window",
                entity_id=persisted.id,
                action="CREDIT_ML_WINDOW_COMPLETED",
                event_type="CREDIT_ML_WINDOW_COMPLETED",
                metadata_json={"window_number": window.number, "model_count": len(model_names)},
            )
        aggregate = {
            name: aggregate_model_metrics(reports) for name, reports in model_reports.items()
        }
        stability = {name: stability_status(metrics) for name, metrics in aggregate.items()}
        fusion = fusion_readiness(
            real_outcomes=real_count,
            valid_windows=run.valid_window_count,
            model_production_permitted=False,
            high_drift="HIGH" in all_drift_statuses,
            comparison_count=len(comparison_rows),
            policy=policy(FUSION_READINESS_POLICY_VERSION),
        )
        agreement_counts = Counter(str(row["agreement_status"]) for row in comparison_rows)
        correlation = correlations(
            [float(cast(float, row["rule_risk_index"])) for row in comparison_rows],
            [float(cast(float, row["ml_probability"])) for row in comparison_rows],
        )
        run.summary_json = {
            "dataset_version": dataset_version,
            "dataset_sha256": dataset.sha256_hash,
            "feature_group": feature_group,
            "candidate_windows": len(windows),
            "aggregate_metrics": aggregate,
            "stability": stability,
            "drift_status_counts": dict(Counter(all_drift_statuses)),
            "model_disagreement": {
                "count": len(disagreement_rows),
                "status_counts": dict(Counter(str(row["status"]) for row in disagreement_rows)),
                "unanimous_count": sum(bool(row.get("unanimous")) for row in disagreement_rows),
            },
            "rule_ml_comparison": {
                "comparable_observations": len(comparison_rows),
                "agreement_status_counts": dict(agreement_counts),
                "correlations": correlation,
                "rule_score_is_probability": False,
            },
            "fusion": fusion,
            "warning": WARNING,
        }
        run.fusion_readiness = str(fusion["status"])
        run.fusion_allowed = bool(fusion["fusion_allowed"])
        run.status = "COMPLETED"
        run.completed_at = datetime.now(UTC)
        if "HIGH" in all_drift_statuses or "MODERATE" in all_drift_statuses:
            write_audit_log(
                self.session,
                entity_type="credit_ml_evaluation_run",
                entity_id=run.id,
                action="CREDIT_ML_DRIFT_DETECTED",
                event_type="CREDIT_ML_DRIFT_DETECTED",
                metadata_json={"status_counts": dict(Counter(all_drift_statuses))},
            )
        write_audit_log(
            self.session,
            entity_type="credit_ml_evaluation_run",
            entity_id=run.id,
            action="CREDIT_RULE_ML_COMPARISON_COMPLETED",
            event_type="CREDIT_RULE_ML_COMPARISON_COMPLETED",
            metadata_json={"comparable_observations": len(comparison_rows)},
        )
        write_audit_log(
            self.session,
            entity_type="credit_ml_evaluation_run",
            entity_id=run.id,
            action="CREDIT_ML_EVALUATION_COMPLETED",
            event_type="CREDIT_ML_EVALUATION_COMPLETED",
            metadata_json={
                "valid_windows": run.valid_window_count,
                "skipped_windows": run.skipped_window_count,
                "fusion_readiness": run.fusion_readiness,
                "fusion_allowed": False,
            },
        )
        self.session.flush()
        return self._result(run, idempotent=False)

    @staticmethod
    def _result(run: CreditMLEvaluationRun, *, idempotent: bool) -> dict[str, object]:
        return {
            "evaluation_id": run.id,
            "evaluation_version": run.evaluation_version,
            "mode": run.mode,
            "window_mode": run.window_mode,
            "status": run.status,
            "valid_windows": run.valid_window_count,
            "skipped_windows": run.skipped_window_count,
            "fusion_readiness": run.fusion_readiness,
            "fusion_allowed": run.fusion_allowed,
            "summary": run.summary_json,
            "idempotent": idempotent,
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run leakage-safe credit ML walk-forward evaluation"
    )
    parser.add_argument("--dataset-version", default="credit_dataset_v1")
    parser.add_argument("--feature-group", default="ANOMALY_ENRICHED_V1")
    parser.add_argument("--mode", default="PIPELINE_VALIDATION")
    parser.add_argument("--walk-forward-policy", default=WALK_FORWARD_POLICY_VERSION)
    parser.add_argument("--window-mode", default="EXPANDING_WINDOW")
    parser.add_argument("--models", default="logistic_regression,random_forest,xgboost")
    args = parser.parse_args()
    settings = get_settings()
    project_root = Path(__file__).resolve().parents[5]
    with Session(get_engine(settings.database_url)) as session, session.begin():
        result = CreditMLEvaluationService(session, project_root).evaluate(
            dataset_version=args.dataset_version,
            feature_group=args.feature_group,
            mode=args.mode,
            walk_forward_policy_version=args.walk_forward_policy,
            window_mode=args.window_mode,
            model_names=tuple(name.strip() for name in args.models.split(",") if name.strip()),
        )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
