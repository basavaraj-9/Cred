from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.ml.credit.artifacts import ArtifactError, load_verified_artifact
from app.models.ml import MLDataset, MLModel, MLRun

router = APIRouter(tags=["credit ML models"])


def _summary(model: MLModel, dataset: MLDataset, integrity: str) -> dict[str, object]:
    metadata = model.metadata_json or {}
    return {
        "model_id": model.id,
        "model_family": model.model_name,
        "model_version": model.model_version,
        "dataset_version": dataset.version,
        "feature_group": model.feature_group,
        "training_mode": model.training_mode,
        "readiness": model.model_readiness_status,
        "lifecycle_status": model.lifecycle_status,
        "calibration_method": model.calibration_method,
        "selected_threshold": model.selected_threshold,
        "is_active": model.is_active,
        "artifact_integrity": integrity,
        "validation": metadata.get("validation"),
        "production_use_permitted": False,
        "warning": metadata.get("warning"),
    }


def _integrity(model: MLModel, storage_root) -> str:
    try:
        load_verified_artifact(storage_root, model.artifact_uri, model.artifact_sha256)
        return "VERIFIED"
    except ArtifactError as exc:
        return str(exc)


@router.get("/ml/credit/models")
def list_credit_ml_models(
    request: Request, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    rows = session.execute(
        select(MLModel, MLDataset)
        .join(MLDataset, MLDataset.id == MLModel.dataset_id)
        .where(MLModel.task_type == "CREDIT_RISK")
        .order_by(MLModel.created_at.desc())
    ).all()
    return [
        _summary(model, dataset, _integrity(model, request.app.state.settings.storage_root))
        for model, dataset in rows
    ]


@router.get("/ml/credit/models/{model_id}")
def get_credit_ml_model(
    model_id: UUID, request: Request, session: Session = Depends(get_db)
) -> dict[str, object]:
    model = session.get(MLModel, model_id)
    if model is None or model.task_type != "CREDIT_RISK":
        raise AppError("CREDIT_ML_MODEL_NOT_FOUND", "Credit ML model not found", 404)
    dataset = session.get(MLDataset, model.dataset_id)
    run = session.get(MLRun, model.run_id)
    assert dataset is not None and run is not None
    return {
        **_summary(model, dataset, _integrity(model, request.app.state.settings.storage_root)),
        "dataset_id": dataset.id,
        "run_id": run.id,
        "parameters": run.parameters_json,
        "metadata": model.metadata_json,
        "label_policy_version": dataset.label_policy_version,
        "feature_schema_version": dataset.feature_schema_version,
        "feature_builder_version": dataset.feature_builder_version,
        "split_policy_version": dataset.split_policy_version,
        "selection_policy_version": model.selection_policy_version,
        "artifact_sha256": model.artifact_sha256,
    }
