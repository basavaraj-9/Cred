from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Change:
    absolute: Decimal
    percent: Decimal | None
    state_transition: str | None
    reason: str | None = None


def calculate_change(previous: Decimal, current: Decimal) -> Change:
    absolute = current - previous
    if previous < 0:
        if current >= 0:
            return Change(absolute, None, "LOSS_TO_PROFIT")
        transition = (
            "LOSS_NARROWED"
            if current > previous
            else "LOSS_WIDENED"
            if current < previous
            else None
        )
        return Change(absolute, None, transition)
    if previous > 0 and current < 0:
        return Change(absolute, None, "PROFIT_TO_LOSS")
    if previous == 0:
        return Change(absolute, None, None, "ZERO_BASE")
    return Change(absolute, (current - previous) / abs(previous), None)


def percentage_point_change(previous: Decimal, current: Decimal) -> Decimal:
    return (current - previous) * Decimal(100)
