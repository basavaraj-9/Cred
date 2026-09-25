from __future__ import annotations

from decimal import Decimal
from typing import cast

from app.models.credit_ml_evaluation import CreditMLEvaluationRun
from app.models.ml import MLModel


def experiment_diagnostic(
    *,
    strategy: str,
    rule_risk_index: Decimal | None,
    ml_probability: Decimal | None,
    hybrid_risk_index: Decimal | None,
    model: MLModel | None,
    evaluation: CreditMLEvaluationRun | None,
    experimental_threshold: float,
) -> dict[str, object]:
    """Describe the comparison that is valid for one pipeline experiment.

    Day 13 can supply ML walk-forward metrics and rule/ML rank correlation. A single
    Day 14 experiment is not a labelled historical fusion series, so hybrid outcome
    metrics and a strategy winner are deliberately unavailable.
    """
    summary = cast(dict[str, object], evaluation.summary_json) if evaluation else {}
    aggregate = cast(dict[str, object], summary.get("aggregate_metrics", {}))
    rule_ml = cast(dict[str, object], summary.get("rule_ml_comparison", {}))
    selected_metrics = aggregate.get(model.model_name) if model else None
    return {
        "status": "PIPELINE_DIAGNOSTIC_ONLY",
        "comparison": {
            "RULE_ONLY": {
                "risk_index": float(rule_risk_index) if rule_risk_index is not None else None,
                "is_probability": False,
            },
            "ML_ONLY": {
                "probability_of_default": float(ml_probability)
                if ml_probability is not None
                else None,
                "production_probability": False,
            },
            strategy: {
                "experimental_hybrid_risk_index": float(hybrid_risk_index)
                if hybrid_risk_index is not None
                else None,
                "is_calibrated_probability": False,
            },
        },
        "available_strategy_comparators": [
            "RULE_ONLY",
            "ML_ONLY",
            "WEIGHTED_BLEND",
            "CONSENSUS_GATED",
        ],
        "experimental_threshold": experimental_threshold,
        "rule_ml_ranking_correlation": rule_ml.get("correlations"),
        "ml_only_walk_forward_metrics": selected_metrics,
        "hybrid_outcome_metrics": {
            "status": "UNAVAILABLE",
            "reason": "NO_LABELLED_HISTORICAL_FUSION_SERIES",
        },
        "hybrid_brier_score": {
            "status": "NOT_CALCULATED",
            "reason": "EXPERIMENTAL_HYBRID_INDEX_IS_NOT_A_CALIBRATED_PD",
        },
        "strategy_winner": None,
        "winner_reason": "REAL_HISTORICAL_VALIDATION_REQUIRED",
    }
