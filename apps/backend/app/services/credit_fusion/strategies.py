from __future__ import annotations

from decimal import Decimal
from typing import cast

from app.services.credit_fusion.policy import experimental_band


def agreement_level(gap: Decimal, policy: dict[str, object]) -> str:
    agreement = cast(dict[str, object], policy["agreement"])
    if gap <= Decimal(str(agreement["low_gap_max"])):
        return "LOW"
    if gap <= Decimal(str(agreement["review_gap_max"])):
        return "MODERATE"
    return "HIGH"


def weighted_blend(
    rule_risk: Decimal, ml_probability: Decimal, policy: dict[str, object]
) -> dict[str, object]:
    weighted = cast(dict[str, object], policy["weighted_blend"])
    rule_weight = Decimal(str(weighted["rule_weight"]))
    ml_weight = Decimal(str(weighted["ml_weight"]))
    hybrid = rule_risk * rule_weight + ml_probability * ml_weight
    if hybrid < 0 or hybrid > 1:
        if hybrid < Decimal("-1e-12") or hybrid > Decimal("1.000000000001"):
            raise ValueError("FUSION_RESULT_OUT_OF_RANGE")
        hybrid = min(Decimal("1"), max(Decimal("0"), hybrid))
    return {
        "status": "EXPERIMENTAL_RESULT",
        "hybrid_risk_index": hybrid,
        "strength_score": (Decimal("1") - hybrid) * Decimal("100"),
        "band": experimental_band(float(hybrid)),
        "rule_weight": rule_weight,
        "ml_weight": ml_weight,
        "rule_contribution": rule_risk * rule_weight,
        "ml_contribution": ml_probability * ml_weight,
    }


def consensus_gated(
    rule_risk: Decimal, ml_probability: Decimal, policy: dict[str, object]
) -> dict[str, object]:
    gap = abs(ml_probability - rule_risk)
    level = agreement_level(gap, policy)
    if level == "HIGH":
        return {"status": "BLOCKED_BY_DISAGREEMENT", "hybrid_risk_index": None}
    if level == "MODERATE":
        return {"status": "REVIEW_REQUIRED", "hybrid_risk_index": None}
    return weighted_blend(rule_risk, ml_probability, policy)
