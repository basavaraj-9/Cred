from __future__ import annotations

# ruff: noqa: E501
import math
import statistics
from collections import Counter
from typing import cast


def aggregate_metric(values: list[tuple[float | None, int]]) -> dict[str, float | int] | None:
    valid = [
        (float(value), weight)
        for value, weight in values
        if value is not None and math.isfinite(value)
    ]
    if not valid:
        return None
    numbers = [value for value, _ in valid]
    total_weight = sum(weight for _, weight in valid)
    return {
        "count": len(numbers),
        "mean": statistics.fmean(numbers),
        "median": statistics.median(numbers),
        "std": statistics.pstdev(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "weighted_average": sum(value * weight for value, weight in valid) / total_weight,
    }


def aggregate_model_metrics(reports: list[dict[str, object]]) -> dict[str, object]:
    names = sorted(
        {
            str(name)
            for report in reports
            for name in cast(dict[str, object], report.get("metrics", {}))
        }
    )
    result: dict[str, object] = {}
    for name in names:
        values = []
        for report in reports:
            metrics = cast(dict[str, object], report.get("metrics", {}))
            value = metrics.get(name)
            values.append(
                (
                    float(cast(float, value)) if value is not None else None,
                    int(cast(int, report["support"])),
                )
            )
        aggregate = aggregate_metric(values)
        if aggregate is not None:
            result[name] = aggregate
    return result


def stability_status(aggregate: dict[str, object], minimum_windows: int = 3) -> str:
    pr_auc = cast(dict[str, object] | None, aggregate.get("pr_auc"))
    if not pr_auc or int(cast(int, pr_auc["count"])) < minimum_windows:
        return "INSUFFICIENT_DATA"
    return "STABLE" if float(cast(float, pr_auc["std"])) <= 0.1 else "VARIABLE"


def _status(value: float, moderate: float, high: float) -> str:
    if value >= high:
        return "HIGH"
    if value >= moderate:
        return "MODERATE"
    return "LOW"


def numeric_drift(
    train_values: list[object], evaluation_values: list[object], policy: dict[str, object]
) -> dict[str, object]:
    train = sorted(float(value) for value in train_values if isinstance(value, (int, float)))
    evaluation = sorted(
        float(value) for value in evaluation_values if isinstance(value, (int, float))
    )
    minimum = int(cast(int, policy["minimum_samples"]))
    if len(train) < minimum or len(evaluation) < minimum:
        return {"metric_name": "psi", "metric_value": None, "status": "INSUFFICIENT_DATA"}
    bins = int(cast(int, policy["psi_bins"]))
    edges = [-math.inf]
    for index in range(1, bins):
        position = min(len(train) - 1, int(index * len(train) / bins))
        edges.append(train[position])
    edges.append(math.inf)
    edges = sorted(set(edges))
    epsilon = float(cast(float, policy["psi_epsilon"]))
    psi = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        train_share = sum(lower <= value < upper for value in train) / len(train)
        eval_share = sum(lower <= value < upper for value in evaluation) / len(evaluation)
        train_share = max(train_share, epsilon)
        eval_share = max(eval_share, epsilon)
        psi += (eval_share - train_share) * math.log(eval_share / train_share)
    return {
        "metric_name": "psi",
        "metric_value": psi,
        "status": _status(
            psi,
            float(cast(float, policy["psi_moderate"])),
            float(cast(float, policy["psi_high"])),
        ),
        "train_median": statistics.median(train),
        "evaluation_median": statistics.median(evaluation),
        "train_mean": statistics.fmean(train),
        "evaluation_mean": statistics.fmean(evaluation),
    }


def categorical_drift(
    train_values: list[object], evaluation_values: list[object], policy: dict[str, object]
) -> dict[str, object]:
    train = ["__MISSING__" if value is None else str(value) for value in train_values]
    evaluation = ["__MISSING__" if value is None else str(value) for value in evaluation_values]
    minimum = int(cast(int, policy["minimum_samples"]))
    if len(train) < minimum or len(evaluation) < minimum:
        return {
            "metric_name": "category_frequency_shift",
            "metric_value": None,
            "status": "INSUFFICIENT_DATA",
            "unseen_category_rate": None,
        }
    train_counts, eval_counts = Counter(train), Counter(evaluation)
    categories = set(train_counts) | set(eval_counts)
    shift = 0.5 * sum(
        abs(train_counts[item] / len(train) - eval_counts[item] / len(evaluation))
        for item in categories
    )
    unseen = sum(value not in train_counts for value in evaluation) / len(evaluation)
    return {
        "metric_name": "category_frequency_shift",
        "metric_value": shift,
        "status": _status(
            shift,
            float(cast(float, policy["categorical_moderate"])),
            float(cast(float, policy["categorical_high"])),
        ),
        "unseen_category_rate": unseen,
    }


def feature_drift(
    train_features: list[dict[str, object]],
    evaluation_features: list[dict[str, object]],
    policy: dict[str, object],
) -> list[dict[str, object]]:
    names = sorted(
        {name for row in train_features for name in row}
        | {name for row in evaluation_features for name in row}
    )
    results = []
    for name in names:
        train_values = [row.get(name) for row in train_features]
        evaluation_values = [row.get(name) for row in evaluation_features]
        present = [value for value in train_values if value is not None]
        result = (
            categorical_drift(train_values, evaluation_values, policy)
            if any(isinstance(value, str) for value in present)
            else numeric_drift(train_values, evaluation_values, policy)
        )
        results.append({"feature_name": name, **result})
    return results


def distribution_summary(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)

    def quantile(q: float) -> float:
        return ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1)))]

    return {
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "q10": quantile(0.1),
        "q25": quantile(0.25),
        "q75": quantile(0.75),
        "q90": quantile(0.9),
    }


def prediction_drift(
    previous: list[float] | None, current: list[float], policy: dict[str, object]
) -> dict[str, object]:
    current_summary = distribution_summary(current)
    if previous is None or not previous or not current or current_summary is None:
        return {"metric_value": None, "status": "INSUFFICIENT_DATA", "current": current_summary}
    previous_summary = distribution_summary(previous)
    assert previous_summary is not None
    shift = abs(current_summary["mean"] - previous_summary["mean"])
    return {
        "metric_value": shift,
        "status": _status(
            shift,
            float(cast(float, policy["prediction_moderate"])),
            float(cast(float, policy["prediction_high"])),
        ),
        "previous": previous_summary,
        "current": current_summary,
    }


def calibration_drift(
    previous_brier: float | None, current_brier: float | None, policy: dict[str, object]
) -> dict[str, object]:
    if previous_brier is None or current_brier is None:
        return {"metric_value": None, "status": "INSUFFICIENT_DATA"}
    shift = abs(current_brier - previous_brier)
    return {
        "metric_value": shift,
        "status": _status(
            shift,
            float(cast(float, policy["calibration_moderate"])),
            float(cast(float, policy["calibration_high"])),
        ),
    }


def model_disagreement(
    probabilities: dict[str, float], threshold: float = 0.5
) -> dict[str, object]:
    if not probabilities:
        return {"status": "INSUFFICIENT_DATA"}
    values = list(probabilities.values())
    classes = [int(value >= threshold) for value in values]
    gap = max(values) - min(values)
    std = statistics.pstdev(values)
    differing = len(set(classes))
    status = (
        "HIGH_DISAGREEMENT"
        if gap >= 0.4
        else "MODERATE_DISAGREEMENT"
        if gap >= 0.2
        else "LOW_DISAGREEMENT"
    )
    return {
        "max_probability_gap": gap,
        "probability_std": std,
        "differing_predicted_classes": differing,
        "unanimous": differing == 1,
        "majority_class": Counter(classes).most_common(1)[0][0],
        "status": status,
    }


def rule_risk_index(rule_score: float) -> float:
    if not 0 <= rule_score <= 100:
        raise ValueError("RULE_SCORE_OUT_OF_RANGE")
    return 1 - rule_score / 100


def diagnostic_band(probability: float, policy: dict[str, object]) -> str:
    if not 0 <= probability <= 1:
        raise ValueError("ML_PROBABILITY_OUT_OF_RANGE")
    for band in cast(list[dict[str, object]], policy["bands"]):
        lower, upper = float(cast(float, band["lower"])), float(cast(float, band["upper"]))
        if lower <= probability < upper or probability == upper == 1:
            return str(band["name"])
    raise ValueError("DIAGNOSTIC_BAND_NOT_FOUND")


def rule_ml_agreement(rule_band: str, ml_band: str) -> str:
    rule_rank = {
        "LOW_RISK": 0,
        "MODERATE_LOW_RISK": 1,
        "MODERATE_RISK": 2,
        "ELEVATED_RISK": 3,
        "HIGH_RISK": 4,
        "VERY_HIGH_RISK": 4,
    }
    ml_rank = {"LOW_PD": 0, "MODERATE_LOW_PD": 1, "MODERATE_PD": 2, "ELEVATED_PD": 3, "HIGH_PD": 4}
    if rule_band not in rule_rank:
        return "INSUFFICIENT_DATA"
    difference = ml_rank[ml_band] - rule_rank[rule_band]
    if difference >= 2:
        return "ML_HIGHER_RISK_THAN_RULE"
    if difference <= -2:
        return "RULE_HIGHER_RISK_THAN_ML"
    if max(rule_rank[rule_band], ml_rank[ml_band]) <= 1:
        return "AGREE_LOW"
    if min(rule_rank[rule_band], ml_rank[ml_band]) >= 3:
        return "AGREE_HIGH"
    return "AGREE_MODERATE"


def _ranks(values: list[float]) -> list[float]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    result = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        rank = (start + end - 1) / 2 + 1
        for _, index in ordered[start:end]:
            result[index] = rank
        start = end
    return result


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3 or len(set(left)) < 2 or len(set(right)) < 2:
        return None
    left_mean, right_mean = statistics.fmean(left), statistics.fmean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right)
    )
    return numerator / denominator if denominator else None


def correlations(rule_indices: list[float], probabilities: list[float]) -> dict[str, float | None]:
    if len(rule_indices) != len(probabilities):
        raise ValueError("CORRELATION_INPUT_LENGTH_MISMATCH")
    return {
        "pearson": _pearson(rule_indices, probabilities),
        "spearman": _pearson(_ranks(rule_indices), _ranks(probabilities))
        if len(rule_indices) >= 3
        else None,
    }


def segment_metrics(
    rows: list[dict[str, object]], segment_name: str, minimum_support: int = 5
) -> dict[str, object]:
    groups: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        if segment_name == "domain" and row.get("domain_verification_status") != "VERIFIED":
            continue
        key = str(row.get(segment_name, "UNKNOWN"))
        groups.setdefault(key, []).append(row)
    return {
        key: (
            {"status": "INSUFFICIENT_DATA", "support": len(group)}
            if len(group) < minimum_support
            else {
                "status": "AVAILABLE",
                "support": len(group),
                "positive_rate": statistics.fmean(
                    float(cast(int, row["target_value"])) for row in group
                ),
                "average_probability": statistics.fmean(
                    float(cast(float, row["ml_probability"])) for row in group
                ),
            }
        )
        for key, group in groups.items()
    }


def fusion_readiness(
    *,
    real_outcomes: int,
    valid_windows: int,
    model_production_permitted: bool,
    high_drift: bool,
    comparison_count: int,
    policy: dict[str, object],
) -> dict[str, object]:
    reasons = []
    if real_outcomes < int(cast(int, policy["minimum_real_outcomes"])):
        reasons.append("INSUFFICIENT_REAL_OUTCOMES")
    if valid_windows < int(cast(int, policy["minimum_valid_walk_forward_windows"])):
        reasons.append("INSUFFICIENT_WALK_FORWARD_SUPPORT")
    if bool(policy["require_production_permitted_model"]) and not model_production_permitted:
        reasons.append("MODEL_NOT_PRODUCTION_PERMITTED")
    if bool(policy["block_on_high_drift"]) and high_drift:
        reasons.append("HIGH_DRIFT_DETECTED")
    if bool(policy["require_rule_ml_comparison"]) and comparison_count == 0:
        reasons.append("RULE_ML_COMPARISON_UNAVAILABLE")
    allowed = not reasons
    status = "VALIDATION_READY" if allowed else "PIPELINE_READY"
    return {"status": status, "fusion_allowed": allowed, "blocking_reasons": reasons}
