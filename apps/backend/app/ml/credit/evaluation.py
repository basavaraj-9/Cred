from __future__ import annotations

import math
from typing import Any

from sklearn.metrics import (  # type: ignore[import-untyped]
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _ece(y_true: list[int], probability: list[float], bins: int = 5) -> float:
    edges = [index / bins for index in range(bins + 1)]
    result = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        indices = [
            index
            for index, value in enumerate(probability)
            if lower <= value < upper or (upper == 1 and value == 1)
        ]
        if not indices:
            continue
        confidence = sum(probability[index] for index in indices) / len(indices)
        observed = sum(y_true[index] for index in indices) / len(indices)
        result += len(indices) / len(y_true) * abs(confidence - observed)
    return float(result)


def evaluate_binary(
    model: Any, x: list[list[object]], y: list[int], threshold: float = 0.5
) -> dict[str, object]:
    if not y:
        return {"support": 0, "metrics": {}, "unavailable": {"all": "Empty split"}}
    probabilities = [float(value) for value in model.predict_proba(x)[:, 1]]
    predicted = [int(value >= threshold) for value in probabilities]
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    metrics: dict[str, float] = {
        "accuracy": float(accuracy_score(y, predicted)),
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "f1": float(f1_score(y, predicted, zero_division=0)),
        "brier_score": float(brier_score_loss(y, probabilities)),
        "log_loss": float(log_loss(y, probabilities, labels=[0, 1])),
        "specificity": float(tn / (tn + fp)) if tn + fp else 0.0,
        "negative_predictive_value": float(tn / (tn + fn)) if tn + fn else 0.0,
        "expected_calibration_error": _ece(y, probabilities),
        "positive_rate": float(sum(y) / len(y)),
        "predicted_positive_rate": float(sum(predicted) / len(predicted)),
        "average_probability": float(sum(probabilities) / len(probabilities)),
        "observed_default_rate": float(sum(y) / len(y)),
    }
    unavailable: dict[str, str] = {}
    if len(set(y)) < 2:
        unavailable["roc_auc"] = "Split contains only one target class"
        unavailable["pr_auc"] = "Split contains only one target class"
        unavailable["balanced_accuracy"] = "Split contains only one target class"
    else:
        metrics["balanced_accuracy"] = float(balanced_accuracy_score(y, predicted))
        metrics["roc_auc"] = float(roc_auc_score(y, probabilities))
        metrics["pr_auc"] = float(average_precision_score(y, probabilities))
    for name, value in list(metrics.items()):
        if not math.isfinite(value):
            unavailable[name] = "Metric was not finite"
            del metrics[name]
    calibration_curve = [
        {"probability": probability, "target": target}
        for probability, target in zip(probabilities, y)
    ]
    return {
        "support": len(y),
        "positive_count": sum(y),
        "negative_count": len(y) - sum(y),
        "threshold": threshold,
        "metrics": metrics,
        "unavailable": unavailable,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "calibration_points": calibration_curve,
        "probabilities": probabilities,
    }
