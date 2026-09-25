from decimal import Decimal


def rule_score_to_risk_index(score: Decimal | float) -> Decimal:
    value = Decimal(str(score))
    if value < 0 or value > 100:
        raise ValueError("RULE_SCORE_OUT_OF_RANGE")
    return Decimal("1") - value / Decimal("100")
