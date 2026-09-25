from __future__ import annotations

# ruff: noqa: E501
from typing import cast


def fusion_confidence(
    *,
    rule_confidence: float,
    coverage: float,
    calibration_available: bool,
    gap_level: str,
    drift_level: str,
    model_disagreement: str,
    rule_status: str,
    policy: dict[str, object],
) -> tuple[float, list[dict[str, object]]]:
    confidence = 0.35 * rule_confidence + 0.25 * coverage
    confidence += 0.15 * 0.6  # Pipeline-validated ML readiness.
    confidence += 0.1 * float(calibration_available)
    confidence += 0.05 * (1 if drift_level == "LOW" else 0.6 if drift_level == "MODERATE" else 0.3)
    confidence += 0.1 * (1 if gap_level == "LOW" else 0.5 if gap_level == "MODERATE" else 0)
    config = cast(dict[str, object], policy["confidence"])
    penalties: list[dict[str, object]] = []
    for applies, code, key in (
        (True, "SYNTHETIC_ONLY_DATA", "synthetic_penalty"),
        (True, "INSUFFICIENT_WALK_FORWARD_SUPPORT", "insufficient_walk_forward_penalty"),
        (drift_level == "MODERATE", "MODERATE_FEATURE_DRIFT", "moderate_drift_penalty"),
        (
            model_disagreement == "MODERATE_DISAGREEMENT",
            "MODERATE_MODEL_DISAGREEMENT",
            "moderate_disagreement_penalty",
        ),
        (rule_status == "NEEDS_REVIEW", "RULE_REQUIRES_REVIEW", "review_rule_penalty"),
    ):
        if applies:
            amount = float(cast(float, config[key]))
            confidence -= amount
            penalties.append({"reason_code": code, "penalty": amount})
    cap = float(cast(float, config["pipeline_validation_cap"]))
    return max(0.0, min(confidence, cap)), penalties
