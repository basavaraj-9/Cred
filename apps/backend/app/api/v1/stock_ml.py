from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.stock_ml import (
    StockMLDataset,
    StockMLDatasetRow,
    StockMLMetric,
    StockMLModel,
    StockMLPrediction,
    StockMLRun,
    StockMLSplit,
    StockMLSplitRow,
)
from app.services.rag.service import CreditRagIndexService
from app.services.stock_ml.service import (
    StockMlDatasetBuilder,
    StockModelTrainer,
    StockWalkForwardBuilder,
)

router = APIRouter(prefix="/stock-ml", tags=["stock ml research"])


class DatasetBuild(BaseModel):
    actor_user_id: UUID
    start_date: date
    end_date: date
    label_horizon: str = "3M"
    feature_set_version: str = "stock_features_v1"


class Actor(BaseModel):
    actor_user_id: UUID


class TrainRequest(Actor):
    models: list[str] | None = None


def dataset_payload(session: Session, dataset: StockMLDataset) -> dict[str, object]:
    return {
        "id": dataset.id,
        "dataset_version": dataset.dataset_version,
        "feature_set_version": dataset.feature_set_version,
        "label_policy_version": dataset.label_policy_version,
        "benchmark_policy_version": dataset.benchmark_policy_version,
        "split_policy_version": dataset.split_policy_version,
        "label_horizon": dataset.label_horizon,
        "status": dataset.status,
        "readiness": dataset.dataset_readiness,
        "row_count": dataset.row_count,
        "company_count": dataset.company_count,
        "listing_count": dataset.listing_count,
        "positive_count": dataset.positive_count,
        "negative_count": dataset.negative_count,
        "neutral_count": dataset.neutral_count,
        "censored_count": dataset.censored_count,
        "start_date": dataset.start_date,
        "end_date": dataset.end_date,
        "feature_count": len(dataset.feature_catalog_json),
        "feature_schema_hash": dataset.feature_schema_hash,
        "rows": [
            {
                "id": row.id,
                "listing_id": row.stock_listing_id,
                "as_of_date": row.as_of_date,
                "label_reference_date": row.label_reference_date,
                "forward_return": row.forward_return,
                "benchmark_return": row.benchmark_return,
                "relative_return": row.relative_return,
                "label_class": row.label_class,
                "rank_target": row.rank_target,
                "benchmark_type": row.benchmark_type,
                "eligibility_status": row.eligibility_status,
            }
            for row in session.scalars(
                select(StockMLDatasetRow)
                .where(StockMLDatasetRow.dataset_id == dataset.id)
                .order_by(StockMLDatasetRow.as_of_date, StockMLDatasetRow.stock_listing_id)
            )
        ],
    }


def split_payload(session: Session, split: StockMLSplit) -> dict[str, object]:
    counts: dict[str, int] = {}
    for assignment in session.scalars(
        select(StockMLSplitRow).where(StockMLSplitRow.split_id == split.id)
    ):
        counts[assignment.partition] = counts.get(assignment.partition, 0) + 1
    return {
        "id": split.id,
        "split_index": split.split_index,
        "policy_version": split.split_policy_version,
        "train_start": split.train_start,
        "train_end": split.train_end,
        "validation_start": split.validation_start,
        "validation_end": split.validation_end,
        "test_start": split.test_start,
        "test_end": split.test_end,
        "embargo_days": split.embargo_days,
        "purged_count": split.purged_count,
        "status": split.status,
        "partition_counts": counts,
    }


@router.post("/datasets/build")
def build_dataset(body: DatasetBuild, session: Session = Depends(get_db)) -> dict[str, object]:
    with session.begin():
        dataset = StockMlDatasetBuilder(session).build(
            body.start_date,
            body.end_date,
            body.actor_user_id,
            body.label_horizon,
            body.feature_set_version,
        )
    return dataset_payload(session, dataset)


@router.get("/datasets/{dataset_id}")
def get_dataset(
    dataset_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    CreditRagIndexService(session)._user(actor_user_id)
    dataset = session.get(StockMLDataset, dataset_id)
    if dataset is None:
        from app.core.exceptions import AppError

        raise AppError("STOCK_ML_DATASET_NOT_FOUND", "Stock ML dataset not found", 404)
    return dataset_payload(session, dataset)


@router.post("/datasets/{dataset_id}/splits/build")
def build_splits(
    dataset_id: UUID, body: Actor, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    with session.begin():
        splits = StockWalkForwardBuilder(session).build(dataset_id, body.actor_user_id)
    return [split_payload(session, split) for split in splits]


@router.get("/datasets/{dataset_id}/splits")
def get_splits(
    dataset_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    return [
        split_payload(session, split)
        for split in session.scalars(
            select(StockMLSplit)
            .where(StockMLSplit.dataset_id == dataset_id)
            .order_by(StockMLSplit.split_index)
        )
    ]


@router.post("/splits/{split_id}/train")
def train(
    split_id: UUID, body: TrainRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        runs = StockModelTrainer(session).train(split_id, body.actor_user_id, body.models)
    return {"split_id": split_id, "run_ids": [run.id for run in runs], "run_count": len(runs)}


@router.get("/runs")
def get_runs(
    actor_user_id: UUID,
    dataset: UUID | None = None,
    model: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    query = select(StockMLRun)
    if dataset:
        query = query.where(StockMLRun.dataset_id == dataset)
    if model:
        query = query.where(StockMLRun.model_name == model)
    if status:
        query = query.where(StockMLRun.status == status)
    return [
        {
            "id": run.id,
            "dataset_id": run.dataset_id,
            "split_id": run.split_id,
            "model_name": run.model_name,
            "model_version": run.model_version,
            "task_type": run.task_type,
            "lifecycle": run.lifecycle,
            "status": run.status,
            "random_state": run.random_state,
        }
        for run in session.scalars(query.order_by(StockMLRun.created_at))
    ]


@router.get("/runs/{run_id}/metrics")
def get_metrics(
    run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    return [
        {
            "partition": metric.partition,
            "name": metric.metric_name,
            "value": metric.metric_value,
            "details": metric.metric_json,
        }
        for metric in session.scalars(
            select(StockMLMetric)
            .where(StockMLMetric.ml_run_id == run_id)
            .order_by(StockMLMetric.partition, StockMLMetric.metric_name)
        )
    ]


@router.get("/runs/{run_id}/predictions")
def get_predictions(
    run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    return [
        {
            "dataset_row_id": prediction.dataset_row_id,
            "partition": prediction.partition,
            "probability": prediction.prediction_probability,
            "predicted_class": prediction.predicted_class,
            "rank_score": prediction.rank_score,
            "research_only": True,
        }
        for prediction in session.scalars(
            select(StockMLPrediction).where(StockMLPrediction.ml_run_id == run_id)
        )
    ]


@router.get("/models")
def get_models(actor_user_id: UUID, session: Session = Depends(get_db)) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    return [
        {
            "id": model.id,
            "run_id": model.ml_run_id,
            "model_name": model.model_name,
            "model_version": model.model_version,
            "lifecycle": model.lifecycle,
            "selected_for_research": model.selected_for_research,
            "production_use_permitted": False,
            "artifact_hash": model.artifact_hash,
            "feature_schema_hash": model.feature_schema_hash,
        }
        for model in session.scalars(select(StockMLModel).order_by(StockMLModel.created_at))
    ]
