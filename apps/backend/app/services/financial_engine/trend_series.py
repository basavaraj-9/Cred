from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class SeriesPoint:
    fiscal_year: str
    period_year: int
    value: Decimal
    confidence: float
    status: str
    source: Any
    currency: str | None = None
    derived: bool = False
    calculation_basis: str | None = None


def period_year(value: str) -> int:
    match = re.fullmatch(r"FY\s*(\d{4})", value.strip(), re.IGNORECASE)
    if match:
        return int(match.group(1))
    try:
        return date.fromisoformat(value.strip()).year
    except ValueError as exc:
        raise ValueError(f"Unsupported fiscal period: {value}") from exc


def chronological(points: list[SeriesPoint]) -> list[SeriesPoint]:
    return sorted(points, key=lambda point: (point.period_year, point.fiscal_year))


def missing_years(points: list[SeriesPoint]) -> list[str]:
    ordered = chronological(points)
    if len(ordered) < 2:
        return []
    present = {point.period_year for point in ordered}
    return [
        f"FY{year}"
        for year in range(ordered[0].period_year, ordered[-1].period_year + 1)
        if year not in present
    ]
