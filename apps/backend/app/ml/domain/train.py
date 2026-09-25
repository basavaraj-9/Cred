import argparse
import hashlib
import json
import os
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import joblib  # type: ignore[import-untyped]
from sklearn.calibration import CalibratedClassifierCV  # type: ignore[import-untyped]
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    top_k_accuracy_score,
)
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.svm import LinearSVC  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.repositories.audit_log import write_audit_log
from app.database.session import create_database_engine
from app.ml.domain.dataset import (
    DATASET_PATH,
    DATASET_VERSION,
    DomainExample,
    dataset_report,
    load_dataset,
    split_by_company,
)
from app.ml.domain.taxonomy import Taxonomy, load_taxonomy
from app.ml.domain.text_builder import INPUT_BUILDER_VERSION
from app.models.enums import MLRunStatus
from app.models.ml import MLDataset, MLMetric, MLModel, MLRun

TASK_TYPE = "DOMAIN_CLASSIFICATION"
MODEL_VERSION = "domain_classifier_v2"
SEED = 42


def candidate_pipeline(name: str, seed: int = SEED) -> Pipeline:
    if name == "tfidf_logistic_regression":
        classifier: Any = LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=seed
        )
    elif name == "tfidf_calibrated_linear_svm":
        classifier = CalibratedClassifierCV(
            LinearSVC(class_weight="balanced", random_state=seed), cv=3
        )
    else:
        raise ValueError(f"Unknown model candidate: {name}")
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
            ("classifier", classifier),
        ]
    )


def evaluate(
    model: Pipeline, rows: Sequence[DomainExample], taxonomy: Taxonomy
) -> dict[str, object]:
    texts = [row.input_text() for row in rows]
    true = [row.sub_domain for row in rows]
    predicted = list(model.predict(texts))
    probabilities = model.predict_proba(texts)
    classes = list(model.classes_)
    result: dict[str, object] = {}
    for level, label in enumerate(("sector", "industry", "domain", "sub_domain")):
        actual_labels = [getattr(row, label) for row in rows]
        predicted_labels = [taxonomy.path_for(str(item))[level] for item in predicted]
        result[label] = {
            "accuracy": float(accuracy_score(actual_labels, predicted_labels)),
            "macro_precision": float(
                precision_score(actual_labels, predicted_labels, average="macro", zero_division=0)
            ),
            "macro_recall": float(
                recall_score(actual_labels, predicted_labels, average="macro", zero_division=0)
            ),
            "macro_f1": float(
                f1_score(actual_labels, predicted_labels, average="macro", zero_division=0)
            ),
            "weighted_f1": float(
                f1_score(actual_labels, predicted_labels, average="weighted", zero_division=0)
            ),
            "per_class": classification_report(
                actual_labels, predicted_labels, output_dict=True, zero_division=0
            ),
            "confusion_matrix": confusion_matrix(
                actual_labels,
                predicted_labels,
                labels=sorted(set(actual_labels) | set(predicted_labels)),
            ).tolist(),
            "confusion_labels": sorted(set(actual_labels) | set(predicted_labels)),
        }
    result["full_path_accuracy"] = float(sum(t == p for t, p in zip(true, predicted)) / len(rows))
    result["sub_domain_top2_accuracy"] = float(
        top_k_accuracy_score(true, probabilities, k=min(2, len(classes)), labels=classes)
    )
    return result


def train_candidates(
    splits: dict[str, list[DomainExample]], taxonomy: Taxonomy, seed: int = SEED
) -> tuple[str, Pipeline, dict[str, dict[str, dict[str, object]]]]:
    train_rows = splits["train"]
    validation_rows = splits["validation"]
    results: dict[str, dict[str, dict[str, object]]] = {}
    models: dict[str, Pipeline] = {}
    for name in ("tfidf_logistic_regression", "tfidf_calibrated_linear_svm"):
        model = candidate_pipeline(name, seed)
        model.fit([row.input_text() for row in train_rows], [row.sub_domain for row in train_rows])
        models[name] = model
        results[name] = {"validation": evaluate(model, validation_rows, taxonomy)}
    logistic_group = cast(
        dict[str, object], results["tfidf_logistic_regression"]["validation"]["sub_domain"]
    )
    svm_group = cast(
        dict[str, object], results["tfidf_calibrated_linear_svm"]["validation"]["sub_domain"]
    )
    logistic = float(cast(float, logistic_group["macro_f1"]))
    svm = float(cast(float, svm_group["macro_f1"]))
    selected = (
        "tfidf_calibrated_linear_svm" if svm > logistic + 0.03 else "tfidf_logistic_regression"
    )
    final_model = candidate_pipeline(selected, seed)
    fit_rows = train_rows + validation_rows
    final_model.fit([row.input_text() for row in fit_rows], [row.sub_domain for row in fit_rows])
    results[selected]["test"] = evaluate(final_model, splits["test"], taxonomy)
    return selected, final_model, results


def _artifact_path(settings: Settings, version: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", version):
        raise ValueError("Model version must use letters, numbers, underscores, or hyphens")
    return settings.storage_root / "models" / "domain" / version / "model.joblib"


def _save_artifact(
    settings: Settings, version: str, model: Pipeline, metadata: dict[str, object]
) -> tuple[str, str]:
    path = _artifact_path(settings, version)
    if path.exists():
        metadata_path = path.parent / "metadata.json"
        if not metadata_path.is_file():
            raise ValueError("Model version artifact already exists without metadata")
        previous = json.loads(metadata_path.read_text(encoding="utf-8"))
        keys = (
            "model_version",
            "model_name",
            "dataset_version",
            "dataset_sha256",
            "taxonomy_version",
            "input_builder_version",
            "seed",
        )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if (
            any(previous.get(key) != metadata.get(key) for key in keys)
            or previous.get("artifact_sha256") != digest
        ):
            raise ValueError("Model version artifact conflicts with this training run")
        return f"local://models/domain/{version}/model.joblib", digest
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    joblib.dump(model, temporary)
    digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
    os.replace(temporary, path)
    metadata["artifact_sha256"] = digest
    (path.parent / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    return f"local://models/domain/{version}/model.joblib", digest


def _metric_rows(session: Session, run_id: Any, split: str, metrics: dict[str, object]) -> None:
    for level in ("sector", "industry", "domain", "sub_domain"):
        group = metrics[level]
        assert isinstance(group, dict)
        for name in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1"):
            session.add(
                MLMetric(
                    run_id=run_id,
                    split=split,
                    metric_name=f"{level}_{name}",
                    metric_value=float(group[name]),
                )
            )
    for name in ("full_path_accuracy", "sub_domain_top2_accuracy"):
        session.add(
            MLMetric(
                run_id=run_id,
                split=split,
                metric_name=name,
                metric_value=float(cast(float, metrics[name])),
            )
        )


def _mark_runs_failed(engine: Engine, run_ids: dict[str, Any], version: str) -> None:
    with Session(engine) as session, session.begin():
        for run_id in run_ids.values():
            record = session.get(MLRun, run_id)
            if record is None:
                continue
            record.status = MLRunStatus.FAILED
            record.completed_at = datetime.now(UTC)
            record.error_code = "MODEL_TRAINING_FAILED"
            write_audit_log(
                session,
                entity_type="ml_run",
                entity_id=record.id,
                action="MODEL_TRAINING_FAILED",
                event_type="MODEL_TRAINING_FAILED",
                metadata_json={"model_version": version},
            )


@contextmanager
def _registration_transaction(
    engine: Engine, run_ids: dict[str, Any], version: str
) -> Iterator[Session]:
    try:
        with Session(engine) as session, session.begin():
            yield session
    except Exception:
        try:
            _mark_runs_failed(engine, run_ids, version)
        except Exception:
            pass  # Keep the registration error; the previous active model remains committed.
        raise


def run_training(
    settings: Settings,
    dataset_path: Path = DATASET_PATH,
    version: str = MODEL_VERSION,
    seed: int = SEED,
) -> dict[str, object]:
    taxonomy = load_taxonomy()
    rows, dataset_hash = load_dataset(dataset_path, taxonomy)
    splits = split_by_company(rows, seed)
    report = dataset_report(rows, splits)
    database_url = (
        settings.test_database_url if settings.app_env == "test" else settings.database_url
    )
    engine = create_database_engine(database_url)
    names = ("tfidf_logistic_regression", "tfidf_calibrated_linear_svm")
    run_ids: dict[str, Any] = {}
    try:
        with Session(engine) as session, session.begin():
            existing_model = session.scalar(
                select(MLModel).where(
                    MLModel.task_type == TASK_TYPE, MLModel.model_version == version
                )
            )
            if existing_model is not None:
                raise ValueError("Model version is already registered")
            dataset = session.scalar(
                select(MLDataset).where(
                    MLDataset.name == "domain", MLDataset.version == DATASET_VERSION
                )
            )
            if dataset is None:
                dataset = MLDataset(
                    name="domain",
                    task_type=TASK_TYPE,
                    version=DATASET_VERSION,
                    description=(
                        "Versioned domain training snapshot; source quality tracked per example"
                    ),
                    taxonomy_version=taxonomy.version,
                    record_count=len(rows),
                    storage_uri=f"data://ml/domain/versions/{dataset_path.name}",
                    sha256_hash=dataset_hash,
                )
                session.add(dataset)
                session.flush()
            elif (
                dataset.sha256_hash != dataset_hash or dataset.taxonomy_version != taxonomy.version
            ):
                raise ValueError("Existing dataset version has different contents or taxonomy")
            for name in names:
                run = MLRun(
                    task_type=TASK_TYPE,
                    model_name=name,
                    model_version=version,
                    dataset_id=dataset.id,
                    status=MLRunStatus.RUNNING,
                    parameters_json={
                        "seed": seed,
                        "input_builder_version": INPUT_BUILDER_VERSION,
                        "dataset_sha256": dataset_hash,
                    },
                    started_at=datetime.now(UTC),
                )
                session.add(run)
                session.flush()
                run_ids[name] = run.id
                write_audit_log(
                    session,
                    entity_type="ml_run",
                    entity_id=run.id,
                    action="MODEL_TRAINING_STARTED",
                    event_type="MODEL_TRAINING_STARTED",
                    metadata_json={
                        "model_version": version,
                        "dataset_version": DATASET_VERSION,
                        "taxonomy_version": taxonomy.version,
                    },
                )
        try:
            selected, model, metrics = train_candidates(splits, taxonomy, seed)
            artifact_uri, artifact_hash = _save_artifact(
                settings,
                version,
                model,
                {
                    "model_version": version,
                    "model_name": selected,
                    "dataset_version": DATASET_VERSION,
                    "dataset_sha256": dataset_hash,
                    "taxonomy_version": taxonomy.version,
                    "input_builder_version": INPUT_BUILDER_VERSION,
                    "classes": list(model.classes_),
                    "seed": seed,
                    "validation_metrics": metrics[selected]["validation"],
                    "test_metrics": metrics[selected]["test"],
                },
            )
        except Exception:
            _mark_runs_failed(engine, run_ids, version)
            raise
        with _registration_transaction(engine, run_ids, version) as session:
            dataset = session.scalar(
                select(MLDataset).where(
                    MLDataset.name == "domain", MLDataset.version == DATASET_VERSION
                )
            )
            assert dataset is not None
            for name in names:
                record = session.get(MLRun, run_ids[name])
                assert record is not None
                record.status = MLRunStatus.COMPLETED
                record.completed_at = datetime.now(UTC)
                if name == selected:
                    record.artifact_uri = artifact_uri
                for split, values in metrics[name].items():
                    _metric_rows(session, record.id, split, values)
                write_audit_log(
                    session,
                    entity_type="ml_run",
                    entity_id=record.id,
                    action="MODEL_TRAINING_COMPLETED",
                    event_type="MODEL_TRAINING_COMPLETED",
                    metadata_json={"model_version": version, "selected": name == selected},
                )
            for old in session.scalars(
                select(MLModel).where(MLModel.task_type == TASK_TYPE, MLModel.is_active.is_(True))
            ).all():
                old.is_active = False
            session.flush()
            registered = MLModel(
                task_type=TASK_TYPE,
                model_name=selected,
                model_version=version,
                run_id=run_ids[selected],
                artifact_uri=artifact_uri,
                artifact_sha256=artifact_hash,
                dataset_id=dataset.id,
                taxonomy_version=taxonomy.version,
                input_builder_version=INPUT_BUILDER_VERSION,
                is_active=True,
            )
            session.add(registered)
            session.flush()
            write_audit_log(
                session,
                entity_type="ml_model",
                entity_id=registered.id,
                action="MODEL_ACTIVATED",
                event_type="MODEL_ACTIVATED",
                metadata_json={
                    "model_version": version,
                    "dataset_version": DATASET_VERSION,
                    "taxonomy_version": taxonomy.version,
                },
            )
        return {
            "dataset_version": DATASET_VERSION,
            "dataset_sha256": dataset_hash,
            "taxonomy_version": taxonomy.version,
            "input_builder_version": INPUT_BUILDER_VERSION,
            "model_version": version,
            "selected": selected,
            "dataset": report,
            "metrics": metrics,
            "artifact_uri": artifact_uri,
            "artifact_sha256": artifact_hash,
            "warning": (
                "Synthetic development baseline; test metrics are not production "
                "accuracy estimates."
            ),
        }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the versioned domain classifier")
    parser.add_argument("--dataset-version", default=DATASET_VERSION)
    parser.add_argument("--taxonomy", default="domain_taxonomy_v1")
    parser.add_argument("--model-version", default=MODEL_VERSION)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if args.dataset_version != DATASET_VERSION or args.taxonomy != load_taxonomy().version:
        parser.error("Unsupported dataset or taxonomy version")
    report = run_training(Settings(), version=args.model_version, seed=args.seed)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
