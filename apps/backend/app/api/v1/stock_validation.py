from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.stock_validation import (
    StockIntelligenceAblationMetric,
    StockIntelligenceAblationRun,
    StockIntelligenceComponentCorrelation,
    StockIntelligenceComponentValidation,
    StockIntelligenceSegmentValidation,
    StockIntelligenceSensitivityRun,
    StockIntelligenceValidationBucket,
    StockIntelligenceValidationPeriod,
    StockIntelligenceValidationRun,
)
from app.services.rag.service import CreditRagIndexService
from app.services.stock_validation.service import StockIntelligenceValidationService

router = APIRouter(prefix="/stock-validation", tags=["stock intelligence validation"])


class ValidationBuild(BaseModel):
    actor_user_id: UUID
    start_date: date
    end_date: date
    score_version: str = "stock_intelligence_score_v1"


class ExperimentBuild(BaseModel):
    actor_user_id: UUID


def run_payload(run: StockIntelligenceValidationRun) -> dict[str, object]:
    return {
        "id": run.id,
        "validation_version": run.validation_version,
        "validation_policy_version": run.validation_policy_version,
        "ablation_policy_version": run.ablation_policy_version,
        "robustness_policy_version": run.robustness_policy_version,
        "score_version": run.score_version,
        "label_policy_version": run.label_policy_version,
        "start_date": run.start_date,
        "end_date": run.end_date,
        "status": run.status,
        "result_status": run.result_status,
        "historical_date_count": run.historical_date_count,
        "eligible_row_count": run.eligible_row_count,
        "censored_row_count": run.censored_row_count,
        "mean_spearman": run.mean_spearman,
        "median_spearman": run.median_spearman,
        "mean_top_bottom_spread": run.mean_top_bottom_spread,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "research_only": True,
        "production_validated": False,
    }


def _run(session: Session, run_id: UUID) -> StockIntelligenceValidationRun:
    run = session.get(StockIntelligenceValidationRun, run_id)
    if run is None:
        raise AppError("STOCK_VALIDATION_NOT_FOUND", "Stock validation run not found", 404)
    return run


@router.post("/runs/build")
def build_validation(
    body: ValidationBuild, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        run = StockIntelligenceValidationService(session).build_validation(
            body.start_date, body.end_date, body.actor_user_id, body.score_version
        )
    return run_payload(run)


@router.get("/runs/{validation_run_id}")
def get_validation(
    validation_run_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    CreditRagIndexService(session)._user(actor_user_id)
    return run_payload(_run(session, validation_run_id))


@router.get("/runs")
def list_validations(
    actor_user_id: UUID,
    status: str | None = None,
    version: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    query = select(StockIntelligenceValidationRun)
    if status:
        query = query.where(StockIntelligenceValidationRun.status == status)
    if version:
        query = query.where(StockIntelligenceValidationRun.validation_version == version)
    if start_date:
        query = query.where(StockIntelligenceValidationRun.end_date >= start_date)
    if end_date:
        query = query.where(StockIntelligenceValidationRun.start_date <= end_date)
    return [
        run_payload(run)
        for run in session.scalars(query.order_by(StockIntelligenceValidationRun.created_at.desc()))
    ]


@router.get("/runs/{validation_run_id}/periods")
def periods(
    validation_run_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    _run(session, validation_run_id)
    return [
        {
            "id": item.id,
            "as_of_date": item.as_of_date,
            "eligible_company_count": item.eligible_company_count,
            "bucket_method": item.bucket_method,
            "spearman": item.spearman,
            "top_bottom_spread": item.top_bottom_spread,
            "top_bucket_hit_rate": item.top_bucket_hit_rate,
            "monotonicity_score": item.monotonicity_score,
            "monotonicity_status": item.monotonicity_status,
            "mean_score": item.mean_score,
            "median_score": item.median_score,
            "score_std": item.score_std,
            "mean_confidence": item.mean_confidence,
            "mean_coverage": item.mean_coverage,
        }
        for item in session.scalars(
            select(StockIntelligenceValidationPeriod)
            .where(StockIntelligenceValidationPeriod.validation_run_id == validation_run_id)
            .order_by(StockIntelligenceValidationPeriod.as_of_date)
        )
    ]


@router.get("/runs/{validation_run_id}/buckets")
def buckets(
    validation_run_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    _run(session, validation_run_id)
    return [
        {
            "id": item.id,
            "validation_period_id": item.validation_period_id,
            "bucket_name": item.bucket_name,
            "bucket_order": item.bucket_order,
            "company_count": item.company_count,
            "mean_relative_return": item.mean_relative_return,
            "median_relative_return": item.median_relative_return,
            "positive_rate": item.positive_rate,
            "std_relative_return": item.std_relative_return,
            "minimum_relative_return": item.minimum_relative_return,
            "maximum_relative_return": item.maximum_relative_return,
        }
        for item in session.scalars(
            select(StockIntelligenceValidationBucket)
            .join(StockIntelligenceValidationPeriod)
            .where(StockIntelligenceValidationPeriod.validation_run_id == validation_run_id)
            .order_by(
                StockIntelligenceValidationPeriod.as_of_date,
                StockIntelligenceValidationBucket.bucket_order,
            )
        )
    ]


@router.get("/runs/{validation_run_id}/components")
def components(
    validation_run_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    _run(session, validation_run_id)
    return [
        {
            "component_name": item.component_name,
            "valid_period_count": item.valid_period_count,
            "sample_count": item.sample_count,
            "mean_spearman": item.mean_spearman,
            "median_spearman": item.median_spearman,
            "std_spearman": item.std_spearman,
            "minimum_spearman": item.minimum_spearman,
            "maximum_spearman": item.maximum_spearman,
        }
        for item in session.scalars(
            select(StockIntelligenceComponentValidation)
            .where(StockIntelligenceComponentValidation.validation_run_id == validation_run_id)
            .order_by(StockIntelligenceComponentValidation.component_name)
        )
    ]


@router.get("/runs/{validation_run_id}/correlations")
def correlations(
    validation_run_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    _run(session, validation_run_id)
    return [
        {
            "component_a": item.component_a,
            "component_b": item.component_b,
            "correlation": item.correlation,
            "sample_count": item.sample_count,
            "redundancy_status": item.redundancy_status,
        }
        for item in session.scalars(
            select(StockIntelligenceComponentCorrelation)
            .where(StockIntelligenceComponentCorrelation.validation_run_id == validation_run_id)
            .order_by(
                StockIntelligenceComponentCorrelation.component_a,
                StockIntelligenceComponentCorrelation.component_b,
            )
        )
    ]


def ablation_payload(session: Session, item: StockIntelligenceAblationRun) -> dict[str, object]:
    metrics = list(
        session.scalars(
            select(StockIntelligenceAblationMetric)
            .where(StockIntelligenceAblationMetric.ablation_run_id == item.id)
            .order_by(StockIntelligenceAblationMetric.metric_name)
        )
    )
    return {
        "id": item.id,
        "experiment_name": item.experiment_name,
        "removed_components": item.removed_components_json,
        "weights": item.weights_json,
        "status": item.status,
        "metrics": [
            {
                "name": metric.metric_name,
                "value": metric.metric_value,
                "valid_period_count": metric.valid_period_count,
                "sample_count": metric.sample_count,
            }
            for metric in metrics
        ],
        "research_only": True,
    }


@router.post("/runs/{validation_run_id}/ablations/build")
def build_ablations(
    validation_run_id: UUID,
    body: ExperimentBuild,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    with session.begin():
        results = StockIntelligenceValidationService(session).run_ablation(
            validation_run_id, body.actor_user_id
        )
    return [ablation_payload(session, result) for result in results]


@router.get("/runs/{validation_run_id}/ablations")
def ablations(
    validation_run_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    _run(session, validation_run_id)
    results = list(
        session.scalars(
            select(StockIntelligenceAblationRun)
            .where(StockIntelligenceAblationRun.validation_run_id == validation_run_id)
            .order_by(StockIntelligenceAblationRun.experiment_name)
        )
    )
    return [ablation_payload(session, result) for result in results]


def sensitivity_payload(item: StockIntelligenceSensitivityRun) -> dict[str, object]:
    return {
        "id": item.id,
        "experiment_name": item.experiment_name,
        "weights": item.weights_json,
        "baseline_rank_correlation": item.baseline_rank_correlation,
        "top_k_overlap": item.top_k_overlap,
        "mean_absolute_rank_change": item.mean_absolute_rank_change,
        "spearman_delta": item.spearman_delta,
        "spread_delta": item.spread_delta,
        "research_only": True,
    }


@router.post("/runs/{validation_run_id}/sensitivity/build")
def build_sensitivity(
    validation_run_id: UUID,
    body: ExperimentBuild,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    with session.begin():
        results = StockIntelligenceValidationService(session).run_sensitivity(
            validation_run_id, body.actor_user_id
        )
    return [sensitivity_payload(result) for result in results]


@router.get("/runs/{validation_run_id}/sensitivity")
def sensitivity(
    validation_run_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    _run(session, validation_run_id)
    return [
        sensitivity_payload(item)
        for item in session.scalars(
            select(StockIntelligenceSensitivityRun)
            .where(StockIntelligenceSensitivityRun.validation_run_id == validation_run_id)
            .order_by(StockIntelligenceSensitivityRun.experiment_name)
        )
    ]


@router.get("/runs/{validation_run_id}/segments")
def segments(
    validation_run_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    _run(session, validation_run_id)
    return [
        {
            "segment_type": item.segment_type,
            "segment_value": item.segment_value,
            "sample_count": item.sample_count,
            "period_count": item.period_count,
            "spearman": item.spearman,
            "top_bottom_spread": item.top_bottom_spread,
            "top_bucket_hit_rate": item.top_bucket_hit_rate,
            "mean_relative_return": item.mean_relative_return,
            "median_relative_return": item.median_relative_return,
            "std_relative_return": item.std_relative_return,
            "positive_rate": item.positive_rate,
            "status": item.status,
        }
        for item in session.scalars(
            select(StockIntelligenceSegmentValidation)
            .where(StockIntelligenceSegmentValidation.validation_run_id == validation_run_id)
            .order_by(
                StockIntelligenceSegmentValidation.segment_type,
                StockIntelligenceSegmentValidation.segment_value,
            )
        )
    ]
