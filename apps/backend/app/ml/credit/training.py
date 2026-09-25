from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
from collections import Counter
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import sklearn  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.repositories.audit_log import write_audit_log
from app.database.session import get_engine
from app.ml.credit.artifacts import save_artifact
from app.ml.credit.calibration import calibrate_sigmoid
from app.ml.credit.dataset import DATASET_NAME, canonical_dataset_hash
from app.ml.credit.evaluation import evaluate_binary
from app.ml.credit.models import MODEL_VERSIONS, build_candidate, feature_diagnostics
from app.ml.credit.preprocessing import infer_feature_layout, matrix
from app.ml.credit.selection import SELECTION_POLICY_VERSION, select_model
from app.models.credit_ml import CreditMLDatasetReport
from app.models.enums import CreditDatasetQuality, MLRunStatus
from app.models.ml import MLDataset, MLMetric, MLModel, MLRun

TASK_TYPE = "CREDIT_RISK"
TRAINING_CONFIG_VERSION = "credit_training_config_v1"
WARNING = (
    "The current credit ML model was trained on a small synthetic development dataset and "
    "is intended only to validate the ML pipeline. Its metrics must not be interpreted as "
    "evidence of real-world credit-default prediction performance."
)


@lru_cache
def training_config() -> dict[str, object]:
    path = Path(__file__).with_name("taxonomy") / f"{TRAINING_CONFIG_VERSION}.json"
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _canonical_metadata(metadata: dict[str, object]) -> dict[str, object]:
    keys = (
        "dataset_version",
        "target_name",
        "horizon_days",
        "label_policy_version",
        "feature_builder_version",
        "feature_schema_version",
        "split_policy_version",
        "feature_group",
    )
    return {key: metadata[key] for key in keys}


def _dataset_path(project_root: Path, storage_uri: str) -> Path:
    prefix = "data://"
    if not storage_uri.startswith(prefix):
        raise ValueError("DATASET_STORAGE_URI_INVALID")
    path = (project_root / "data" / storage_uri.removeprefix(prefix)).resolve()
    if not path.is_relative_to(project_root.resolve()):
        raise ValueError("DATASET_STORAGE_URI_INVALID")
    return path


def load_verified_dataset(
    dataset: MLDataset, report: CreditMLDatasetReport, project_root: Path
) -> tuple[list[dict[str, object]], dict[str, object]]:
    metadata = report.report_json
    if report.quality_status == CreditDatasetQuality.INVALID:
        raise ValueError("INVALID_DATASET")
    leakage = metadata.get("leakage", {})
    if not isinstance(leakage, dict) or leakage.get("critical_failure") is not False:
        raise ValueError("DATASET_LEAKAGE_CHECK_FAILED")
    path = _dataset_path(project_root, dataset.storage_uri)
    if not path.is_file():
        raise ValueError("DATASET_ARTIFACT_UNAVAILABLE")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    digest = canonical_dataset_hash(records, _canonical_metadata(metadata))
    if digest != dataset.sha256_hash or metadata.get("sha256") != digest:
        raise ValueError("DATASET_INTEGRITY_FAILED")
    splits = Counter(str(record.get("split")) for record in records)
    if not all(splits[name] for name in ("TRAIN", "VALIDATION", "TEST")):
        raise ValueError("DATASET_SPLITS_INCOMPLETE")
    if any(record.get("target_value") not in {0, 1} for record in records):
        raise ValueError("DATASET_TARGET_INVALID")
    return cast(list[dict[str, object]], records), metadata


def _persist_metrics(session: Session, run_id: Any, split: str, report: dict[str, object]) -> None:
    metrics = report.get("metrics", {})
    if not isinstance(metrics, dict):
        return
    for name, value in metrics.items():
        session.add(
            MLMetric(
                run_id=run_id,
                split=split,
                metric_name=str(name),
                metric_value=float(value),
            )
        )


class CreditMLTrainingService:
    def __init__(self, session: Session, project_root: Path, storage_root: Path) -> None:
        self.session = session
        self.project_root = project_root
        self.storage_root = storage_root

    def train(
        self,
        *,
        dataset_version: str = "credit_dataset_v1",
        feature_group: str = "ANOMALY_ENRICHED_V1",
        training_mode: str = "PIPELINE_VALIDATION",
        model_names: tuple[str, ...] = (
            "logistic_regression",
            "random_forest",
            "xgboost",
        ),
    ) -> dict[str, object]:
        if training_mode != "PIPELINE_VALIDATION":
            raise ValueError("PRODUCTION_TRAINING_REQUIRES_REAL_CURATED_OUTCOMES")
        unknown = set(model_names) - set(MODEL_VERSIONS)
        if unknown:
            raise ValueError(f"Unknown model candidates: {sorted(unknown)}")
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
        records, dataset_metadata = load_verified_dataset(dataset, report, self.project_root)
        if dataset_metadata.get("feature_group") != feature_group:
            raise ValueError("DATASET_FEATURE_GROUP_MISMATCH")
        if int(cast(int, dataset_metadata.get("real_count", 0))) > 0:
            raise ValueError("PIPELINE_VALIDATION_EXPECTS_SYNTHETIC_DATA")
        existing = self.session.scalar(
            select(MLModel).where(
                MLModel.task_type == TASK_TYPE,
                MLModel.model_version.in_([MODEL_VERSIONS[name] for name in model_names]),
            )
        )
        if existing:
            raise ValueError("CREDIT_MODEL_VERSION_ALREADY_REGISTERED")

        split_rows = {
            name: [record for record in records if record["split"] == name]
            for name in ("TRAIN", "VALIDATION", "TEST")
        }
        train_features = [cast(dict[str, object], row["features"]) for row in split_rows["TRAIN"]]
        layout = infer_feature_layout(train_features)
        split_x = {
            name: matrix([cast(dict[str, object], row["features"]) for row in rows], layout)
            for name, rows in split_rows.items()
        }
        split_y = {
            name: [int(cast(int, row["target_value"])) for row in rows]
            for name, rows in split_rows.items()
        }
        train_counts = Counter(split_y["TRAIN"])
        if not train_counts[0] or not train_counts[1]:
            raise ValueError("TRAIN_SPLIT_REQUIRES_BOTH_CLASSES")
        scale_pos_weight = train_counts[0] / train_counts[1]
        config = training_config()
        seed = int(cast(int, config["random_seed"]))
        threshold = float(cast(float, config["threshold"]))
        run_ids: dict[str, Any] = {}
        for name in model_names:
            run = MLRun(
                task_type=TASK_TYPE,
                model_name=name,
                model_version=MODEL_VERSIONS[name],
                dataset_id=dataset.id,
                status=MLRunStatus.RUNNING,
                parameters_json={
                    "training_config": config,
                    "dataset_sha256": dataset.sha256_hash,
                    "scale_pos_weight": scale_pos_weight if name == "xgboost" else None,
                    "library_versions": {
                        "python": platform.python_version(),
                        "scikit_learn": sklearn.__version__,
                        "xgboost": importlib.metadata.version("xgboost"),
                        "numpy": importlib.metadata.version("numpy"),
                    },
                },
                started_at=datetime.now(UTC),
                training_mode=training_mode,
                feature_group=feature_group,
                training_config_version=TRAINING_CONFIG_VERSION,
            )
            self.session.add(run)
            self.session.flush()
            run_ids[name] = run.id
            write_audit_log(
                self.session,
                entity_type="ml_run",
                entity_id=run.id,
                action="CREDIT_ML_TRAINING_STARTED",
                event_type="CREDIT_ML_TRAINING_STARTED",
                metadata_json={
                    "model_version": MODEL_VERSIONS[name],
                    "dataset_version": dataset_version,
                    "training_mode": training_mode,
                },
            )

        validation_reports: dict[str, dict[str, object]] = {}
        trained: dict[str, dict[str, object]] = {}
        failures: dict[str, str] = {}
        for name in model_names:
            current_run = self.session.get(MLRun, run_ids[name])
            assert current_run is not None
            try:
                base_model = build_candidate(
                    name,
                    layout,
                    config,
                    seed=seed,
                    scale_pos_weight=scale_pos_weight,
                )
                base_model.fit(split_x["TRAIN"], split_y["TRAIN"])
                diagnostics = feature_diagnostics(base_model)
                model_for_calibration = build_candidate(
                    name,
                    layout,
                    config,
                    seed=seed,
                    scale_pos_weight=scale_pos_weight,
                )
                model, calibration_method, calibration_warning = calibrate_sigmoid(
                    model_for_calibration, split_x["TRAIN"], split_y["TRAIN"]
                )
                validation = evaluate_binary(
                    model, split_x["VALIDATION"], split_y["VALIDATION"], threshold
                )
                validation_reports[name] = validation
                metadata = {
                    "model_name": name,
                    "model_version": MODEL_VERSIONS[name],
                    "dataset_version": dataset_version,
                    "dataset_sha256": dataset.sha256_hash,
                    "feature_group": feature_group,
                    "feature_names": layout.names,
                    "training_mode": training_mode,
                    "model_readiness": "PIPELINE_VALIDATED",
                    "production_use_permitted": False,
                    "calibration_method": calibration_method,
                    "calibration_warning": calibration_warning,
                    "selected_threshold": threshold,
                    "validation": validation,
                    "feature_diagnostics": diagnostics,
                    "feature_diagnostics_status": "PIPELINE_DIAGNOSTIC_ONLY",
                    "warning": WARNING,
                }
                uri, digest = save_artifact(
                    self.storage_root,
                    MODEL_VERSIONS[name],
                    {
                        "model": model,
                        "feature_names": layout.names,
                        "feature_group": feature_group,
                        "model_version": MODEL_VERSIONS[name],
                    },
                    metadata,
                )
                trained[name] = {
                    "model": model,
                    "artifact_uri": uri,
                    "artifact_sha256": digest,
                    "calibration_method": calibration_method,
                    "metadata": metadata,
                }
                current_run.status = MLRunStatus.COMPLETED
                current_run.completed_at = datetime.now(UTC)
                current_run.artifact_uri = uri
                current_run.parameters_json = {
                    **current_run.parameters_json,
                    "evaluation": {"validation": validation},
                }
                _persist_metrics(self.session, current_run.id, "VALIDATION", validation)
                write_audit_log(
                    self.session,
                    entity_type="ml_run",
                    entity_id=current_run.id,
                    action="CREDIT_ML_MODEL_TRAINED",
                    event_type="CREDIT_ML_MODEL_TRAINED",
                    metadata_json={"model_version": MODEL_VERSIONS[name]},
                )
                if calibration_method == "sigmoid":
                    write_audit_log(
                        self.session,
                        entity_type="ml_run",
                        entity_id=current_run.id,
                        action="CREDIT_ML_MODEL_CALIBRATED",
                        event_type="CREDIT_ML_MODEL_CALIBRATED",
                        metadata_json={"method": calibration_method},
                    )
            except Exception as exc:
                current_run.status = MLRunStatus.FAILED
                current_run.completed_at = datetime.now(UTC)
                current_run.error_code = "CREDIT_ML_MODEL_TRAINING_FAILED"
                failures[name] = type(exc).__name__
                write_audit_log(
                    self.session,
                    entity_type="ml_run",
                    entity_id=current_run.id,
                    action="CREDIT_ML_TRAINING_FAILED",
                    event_type="CREDIT_ML_TRAINING_FAILED",
                    metadata_json={
                        "model_version": MODEL_VERSIONS[name],
                        "error_type": type(exc).__name__,
                    },
                )

        selected, selection_reason = select_model(validation_reports)
        selected_data = trained[selected]
        selected_model = selected_data["model"]
        test_report = evaluate_binary(selected_model, split_x["TEST"], split_y["TEST"], threshold)
        selected_run = self.session.get(MLRun, run_ids[selected])
        assert selected_run is not None
        selected_run.parameters_json = {
            **selected_run.parameters_json,
            "evaluation": {
                "validation": validation_reports[selected],
                "test": test_report,
            },
            "selection_reason": selection_reason,
        }
        _persist_metrics(self.session, selected_run.id, "TEST", test_report)
        for name, details in trained.items():
            selected_candidate = name == selected
            metadata = cast(dict[str, object], details["metadata"])
            if selected_candidate:
                metadata["test"] = test_report
                metadata["selection_reason"] = selection_reason
            model_row = MLModel(
                task_type=TASK_TYPE,
                model_name=name,
                model_version=MODEL_VERSIONS[name],
                run_id=run_ids[name],
                artifact_uri=str(details["artifact_uri"]),
                artifact_sha256=str(details["artifact_sha256"]),
                dataset_id=dataset.id,
                taxonomy_version=str(dataset.label_policy_version),
                input_builder_version=str(dataset.feature_builder_version),
                is_active=selected_candidate,
                training_mode=training_mode,
                model_readiness_status="PIPELINE_VALIDATED",
                lifecycle_status=(
                    "PIPELINE_VALIDATION_ONLY" if selected_candidate else "CANDIDATE"
                ),
                calibration_method=str(details["calibration_method"]),
                selected_threshold=threshold,
                feature_group=feature_group,
                selection_policy_version=SELECTION_POLICY_VERSION,
                metadata_json=metadata,
            )
            self.session.add(model_row)
            self.session.flush()
            write_audit_log(
                self.session,
                entity_type="ml_model",
                entity_id=model_row.id,
                action="CREDIT_ML_MODEL_REGISTERED",
                event_type="CREDIT_ML_MODEL_REGISTERED",
                metadata_json={
                    "model_version": model_row.model_version,
                    "readiness": model_row.model_readiness_status,
                },
            )
            if selected_candidate:
                write_audit_log(
                    self.session,
                    entity_type="ml_model",
                    entity_id=model_row.id,
                    action="CREDIT_ML_MODEL_SELECTED",
                    event_type="CREDIT_ML_MODEL_SELECTED",
                    metadata_json={"selection_policy_version": SELECTION_POLICY_VERSION},
                )
                write_audit_log(
                    self.session,
                    entity_type="ml_model",
                    entity_id=model_row.id,
                    action="CREDIT_ML_MODEL_ACTIVATED",
                    event_type="CREDIT_ML_MODEL_ACTIVATED",
                    metadata_json={"production_use_permitted": False},
                )
        self.session.flush()
        return {
            "dataset_version": dataset_version,
            "dataset_sha256": dataset.sha256_hash,
            "training_mode": training_mode,
            "feature_group": feature_group,
            "split_counts": {name: len(rows) for name, rows in split_rows.items()},
            "class_distribution": {name: dict(Counter(values)) for name, values in split_y.items()},
            "models_trained": list(trained),
            "model_failures": failures,
            "validation": validation_reports,
            "selected_model": selected,
            "selected_model_version": MODEL_VERSIONS[selected],
            "selection_policy_version": SELECTION_POLICY_VERSION,
            "selection_reason": selection_reason,
            "test": test_report,
            "calibration_method": selected_data["calibration_method"],
            "readiness": "PIPELINE_VALIDATED",
            "production_use_permitted": False,
            "warning": WARNING,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train credit ML pipeline-validation baselines")
    parser.add_argument("--dataset-version", default="credit_dataset_v1")
    parser.add_argument("--feature-group", default="ANOMALY_ENRICHED_V1")
    parser.add_argument("--training-mode", default="PIPELINE_VALIDATION")
    parser.add_argument("--models", default="logistic_regression,random_forest,xgboost")
    args = parser.parse_args()
    settings = get_settings()
    database_url = (
        settings.test_database_url
        if settings.app_env == "test" and settings.test_database_url
        else settings.database_url
    )
    project_root = Path(__file__).resolve().parents[5]
    with Session(get_engine(database_url)) as session, session.begin():
        result = CreditMLTrainingService(session, project_root, settings.storage_root).train(
            dataset_version=args.dataset_version,
            feature_group=args.feature_group,
            training_mode=args.training_mode,
            model_names=tuple(name.strip() for name in args.models.split(",") if name.strip()),
        )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
