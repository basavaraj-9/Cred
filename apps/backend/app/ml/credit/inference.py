from __future__ import annotations

from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.repositories.audit_log import write_audit_log
from app.ml.credit.artifacts import load_verified_artifact
from app.ml.credit.feature_schema import validate_features
from app.ml.credit.training import TASK_TYPE, WARNING
from app.models.credit_ml import CreditMLFeatureSnapshot
from app.models.ml import MLModel


class CreditMLInferenceService:
    def __init__(self, session: Session, storage_root: Path) -> None:
        self.session = session
        self.storage_root = storage_root

    def predict(self, feature_snapshot_id: object) -> dict[str, object]:
        model_row = self.session.scalar(
            select(MLModel).where(MLModel.task_type == TASK_TYPE, MLModel.is_active.is_(True))
        )
        if model_row is None:
            raise ValueError("CREDIT_ML_ACTIVE_MODEL_UNAVAILABLE")
        snapshot = self.session.get(CreditMLFeatureSnapshot, feature_snapshot_id)
        if snapshot is None:
            raise ValueError("CREDIT_ML_FEATURE_SNAPSHOT_NOT_FOUND")
        if snapshot.feature_group != model_row.feature_group:
            raise ValueError("MODEL_METADATA_MISMATCH")
        validate_features(snapshot.features_json, snapshot.feature_group)
        bundle = load_verified_artifact(
            self.storage_root, model_row.artifact_uri, model_row.artifact_sha256
        )
        feature_names = cast(list[str], bundle["feature_names"])
        model = bundle["model"]
        row = [[snapshot.features_json.get(name) for name in feature_names]]
        probability = float(model.predict_proba(row)[0, 1])
        threshold = float(model_row.selected_threshold or 0.5)
        write_audit_log(
            self.session,
            entity_type="ml_model",
            entity_id=model_row.id,
            action="CREDIT_ML_INFERENCE_EXECUTED",
            event_type="CREDIT_ML_INFERENCE_EXECUTED",
            company_id=snapshot.company_id,
            metadata_json={
                "model_version": model_row.model_version,
                "feature_snapshot_id": str(snapshot.id),
                "readiness": model_row.model_readiness_status,
            },
        )
        return {
            "probability_of_default": probability,
            "classification_threshold": threshold,
            "predicted_class": int(probability >= threshold),
            "model_id": model_row.id,
            "model_version": model_row.model_version,
            "dataset_id": model_row.dataset_id,
            "feature_snapshot_hash": snapshot.input_hash,
            "model_readiness": model_row.model_readiness_status,
            "production_use_permitted": False,
            "warning": WARNING,
        }
