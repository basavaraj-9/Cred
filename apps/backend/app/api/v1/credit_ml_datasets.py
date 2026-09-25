from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.credit_ml import CreditMLDatasetReport
from app.models.ml import MLDataset

router = APIRouter(tags=["credit ML datasets"])


@router.get("/ml/credit/datasets/{dataset_id}")
def get_credit_ml_dataset(
    dataset_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    dataset = session.get(MLDataset, dataset_id)
    if dataset is None or dataset.task_type != "CREDIT_RISK":
        raise AppError("CREDIT_ML_DATASET_NOT_FOUND", "Credit ML dataset not found", 404)
    report = session.scalar(
        select(CreditMLDatasetReport).where(CreditMLDatasetReport.dataset_id == dataset.id)
    )
    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "version": dataset.version,
        "task_type": dataset.task_type,
        "target_name": dataset.target_name,
        "prediction_horizon_days": dataset.prediction_horizon_days,
        "label_policy_version": dataset.label_policy_version,
        "feature_builder_version": dataset.feature_builder_version,
        "feature_schema_version": dataset.feature_schema_version,
        "split_policy_version": dataset.split_policy_version,
        "record_count": dataset.record_count,
        "sha256": dataset.sha256_hash,
        "storage_uri": dataset.storage_uri,
        "quality_status": report.quality_status if report else None,
        "training_readiness": report.training_readiness if report else None,
        "report": report.report_json if report else dataset.metadata_json,
    }
