from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from decimal import Decimal


def finite_decimal(value: float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return Decimal(str(number))


def mean(values: list[Decimal]) -> Decimal | None:
    return finite_decimal(statistics.fmean(float(value) for value in values)) if values else None


def median(values: list[Decimal]) -> Decimal | None:
    return finite_decimal(statistics.median(float(value) for value in values)) if values else None


def population_std(values: list[Decimal]) -> Decimal | None:
    return finite_decimal(statistics.pstdev(float(value) for value in values)) if values else None


def ranks(values: list[Decimal]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    result = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average_rank = (index + 1 + end) / 2.0
        for position in range(index, end):
            result[ordered[position][0]] = average_rank
        index = end
    return result


def pearson(left: list[float], right: list[float]) -> Decimal | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True))
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left) * sum((y - right_mean) ** 2 for y in right)
    )
    if denominator == 0:
        return None
    return finite_decimal(numerator / denominator)


def spearman(left: list[Decimal], right: list[Decimal]) -> Decimal | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    return pearson(ranks(left), ranks(right))


@dataclass(frozen=True)
class Bucket:
    name: str
    order: int
    indexes: tuple[int, ...]


def quantile_buckets(scores: list[Decimal], method: str) -> list[Bucket]:
    count = 5 if method == "QUINTILE" else 3
    prefix = "Q" if count == 5 else "T"
    ordered = sorted(range(len(scores)), key=lambda index: (scores[index], index))
    assignments: list[list[int]] = [[] for _ in range(count)]
    for position, original_index in enumerate(ordered):
        assignments[min(count - 1, position * count // len(ordered))].append(original_index)
    return [
        Bucket(f"{prefix}{index + 1}", index + 1, tuple(indexes))
        for index, indexes in enumerate(assignments)
        if indexes
    ]


def monotonicity(values: list[Decimal]) -> tuple[Decimal | None, str]:
    if len(values) < 2:
        return None, "INSUFFICIENT_DATA"
    score = Decimal(
        sum(right >= left for left, right in zip(values, values[1:], strict=False))
    ) / Decimal(len(values) - 1)
    if score >= Decimal("0.75"):
        status = "STRONG"
    elif score >= Decimal("0.50"):
        status = "MODERATE"
    else:
        status = "WEAK"
    return score, status
