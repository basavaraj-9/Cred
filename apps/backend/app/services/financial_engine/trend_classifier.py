from __future__ import annotations

from decimal import Decimal

from app.models.enums import TrendDirection, TrendStrength


def classify(
    values: list[Decimal], state_change: bool = False
) -> tuple[TrendDirection, TrendStrength | None]:
    if len(values) < 2:
        return TrendDirection.INSUFFICIENT_DATA, None
    if state_change:
        return TrendDirection.STATE_CHANGE, None
    deltas = [current - previous for previous, current in zip(values, values[1:], strict=False)]
    scale = max(max(abs(value) for value in values), Decimal("0.000001"))
    stable_limit = scale * Decimal("0.01")
    if all(abs(delta) <= stable_limit for delta in deltas):
        return TrendDirection.STABLE, TrendStrength.WEAK
    positive = sum(delta > stable_limit for delta in deltas)
    negative = sum(delta < -stable_limit for delta in deltas)
    if positive == len(deltas):
        direction = TrendDirection.INCREASING
    elif negative == len(deltas):
        direction = TrendDirection.DECREASING
    elif len(values) >= 3 and positive and negative:
        direction = (
            TrendDirection.VOLATILE
            if max(values) - min(values) > scale * Decimal("0.20")
            else TrendDirection.MIXED
        )
    else:
        direction = TrendDirection.MIXED
    magnitude = abs(values[-1] - values[0]) / scale
    if len(values) < 3:
        strength = TrendStrength.MODERATE if magnitude >= Decimal("0.10") else TrendStrength.WEAK
    elif magnitude >= Decimal("0.25") and direction in {
        TrendDirection.INCREASING,
        TrendDirection.DECREASING,
    }:
        strength = TrendStrength.STRONG
    elif magnitude >= Decimal("0.10"):
        strength = TrendStrength.MODERATE
    else:
        strength = TrendStrength.WEAK
    return direction, strength
