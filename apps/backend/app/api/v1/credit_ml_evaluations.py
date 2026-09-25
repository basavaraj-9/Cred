from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.credit_ml_evaluation import (
    CreditMLDriftResult,
    CreditMLEvaluationRun,
    CreditMLEvaluationWindow,
    CreditMLWindowModelResult,
    CreditRuleMLComparison,
)

router = APIRouter(tags=["credit ML evaluations"])


def _run_or_404(session: Session, evaluation_id: UUID) -> CreditMLEvaluationRun:
    run = session.get(CreditMLEvaluationRun, evaluation_id)
    if run is None:
        raise AppError("CREDIT_ML_EVALUATION_NOT_FOUND", "Credit ML evaluation not found", 404)
    return run


def _summary(run: CreditMLEvaluationRun) -> dict[str, object]:
    return {
        "evaluation_id": run.id,
        "dataset_id": run.dataset_id,
        "evaluation_version": run.evaluation_version,
        "mode": run.mode,
        "window_mode": run.window_mode,
        "status": run.status,
        "valid_window_count": run.valid_window_count,
        "skipped_window_count": run.skipped_window_count,
        "fusion_readiness": run.fusion_readiness,
        "fusion_allowed": run.fusion_allowed,
        "production_use_permitted": False,
        "created_at": run.created_at,
    }


@router.get("/ml/credit/evaluations")
def list_credit_ml_evaluations(session: Session = Depends(get_db)) -> list[dict[str, object]]:
    runs = session.scalars(
        select(CreditMLEvaluationRun).order_by(CreditMLEvaluationRun.created_at.desc())
    ).all()
    return [_summary(run) for run in runs]


@router.get("/ml/credit/evaluations/{evaluation_id}")
def get_credit_ml_evaluation(
    evaluation_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    run = _run_or_404(session, evaluation_id)
    return {
        **_summary(run),
        "input_hash": run.input_hash,
        "walk_forward_policy_version": run.walk_forward_policy_version,
        "drift_policy_version": run.drift_policy_version,
        "diagnostic_band_version": run.diagnostic_band_version,
        "fusion_readiness_policy_version": run.fusion_readiness_policy_version,
        "summary": run.summary_json,
    }


@router.get("/ml/credit/evaluations/{evaluation_id}/windows")
def get_evaluation_windows(
    evaluation_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _run_or_404(session, evaluation_id)
    windows = session.scalars(
        select(CreditMLEvaluationWindow)
        .where(CreditMLEvaluationWindow.evaluation_run_id == evaluation_id)
        .order_by(CreditMLEvaluationWindow.window_number)
    ).all()
    output = []
    for window in windows:
        models = session.scalars(
            select(CreditMLWindowModelResult).where(
                CreditMLWindowModelResult.evaluation_window_id == window.id
            )
        ).all()
        output.append(
            {
                "window_id": window.id,
                "window_number": window.window_number,
                "mode": window.mode,
                "train_start": window.train_start,
                "train_end": window.train_end,
                "evaluation_start": window.evaluation_start,
                "evaluation_end": window.evaluation_end,
                "train_count": window.train_count,
                "evaluation_count": window.evaluation_count,
                "status": window.status,
                "skip_reason": window.skip_reason,
                "models": [
                    {
                        "model_family": result.model_family,
                        "model_version": result.model_version,
                        "calibration_method": result.calibration_method,
                        "status": result.status,
                        "metrics": result.metric_summary_json,
                    }
                    for result in models
                ],
            }
        )
    return output


@router.get("/ml/credit/evaluations/{evaluation_id}/drift")
def get_evaluation_drift(
    evaluation_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _run_or_404(session, evaluation_id)
    rows = session.execute(
        select(CreditMLDriftResult, CreditMLEvaluationWindow.window_number)
        .join(
            CreditMLEvaluationWindow,
            CreditMLEvaluationWindow.id == CreditMLDriftResult.evaluation_window_id,
        )
        .where(CreditMLEvaluationWindow.evaluation_run_id == evaluation_id)
        .order_by(CreditMLEvaluationWindow.window_number, CreditMLDriftResult.feature_name)
    ).all()
    return [
        {
            "window_number": window_number,
            "feature_name": row.feature_name,
            "drift_type": row.drift_type,
            "metric_name": row.metric_name,
            "metric_value": row.metric_value,
            "status": row.status,
            "threshold_version": row.threshold_version,
            "metadata": row.metadata_json,
        }
        for row, window_number in rows
    ]


@router.get("/ml/credit/evaluations/{evaluation_id}/rule-comparison")
def get_rule_ml_comparison(
    evaluation_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    run = _run_or_404(session, evaluation_id)
    rows = session.scalars(
        select(CreditRuleMLComparison)
        .where(CreditRuleMLComparison.evaluation_run_id == evaluation_id)
        .order_by(CreditRuleMLComparison.created_at)
    ).all()
    return {
        "evaluation_id": evaluation_id,
        "summary": run.summary_json.get("rule_ml_comparison", {}),
        "rule_score_is_probability": False,
        "comparisons": [
            {
                "observation_id": row.observation_id,
                "ml_model_family": row.ml_model_family,
                "ml_probability": row.ml_probability,
                "rule_score": row.rule_score,
                "rule_risk_index": row.rule_risk_index,
                "rule_risk_band": row.rule_risk_band,
                "ml_diagnostic_band": row.ml_diagnostic_band,
                "agreement_status": row.agreement_status,
                "probability_gap": row.probability_gap,
            }
            for row in rows
        ],
    }
