from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PsiResult:
    value: float | None
    status: str
    bin_count: int


def population_stability_index(
    reference: list[float],
    current: list[float],
    *,
    requested_bins: int = 10,
    epsilon: float = 0.000001,
    minimum_samples: int = 10,
) -> PsiResult:
    if len(reference) < minimum_samples or len(current) < minimum_samples:
        return PsiResult(None, "INSUFFICIENT_DATA", 0)
    ordered = sorted(reference)
    if ordered[0] == ordered[-1]:
        return PsiResult(None, "INSUFFICIENT_VARIATION", 0)
    bin_count = min(requested_bins, len(reference) // 2, len(current) // 2)
    if bin_count < 2:
        return PsiResult(None, "INSUFFICIENT_DATA", 0)
    boundaries: list[float] = []
    for index in range(1, bin_count):
        position = index * (len(ordered) - 1) / bin_count
        low = math.floor(position)
        high = math.ceil(position)
        fraction = position - low
        boundary = ordered[low] * (1 - fraction) + ordered[high] * fraction
        if not boundaries or boundary > boundaries[-1]:
            boundaries.append(boundary)
    if not boundaries:
        return PsiResult(None, "INSUFFICIENT_VARIATION", 0)

    def proportions(values: list[float]) -> list[float]:
        counts = [0] * (len(boundaries) + 1)
        for value in values:
            target = 0
            while target < len(boundaries) and value > boundaries[target]:
                target += 1
            counts[target] += 1
        return [max(count / len(values), epsilon) for count in counts]

    reference_rates = proportions(reference)
    current_rates = proportions(current)
    value = sum(
        (current_rate - reference_rate) * math.log(current_rate / reference_rate)
        for reference_rate, current_rate in zip(reference_rates, current_rates, strict=True)
    )
    if not math.isfinite(value):
        return PsiResult(None, "INSUFFICIENT_DATA", len(reference_rates))
    return PsiResult(max(0.0, value), "AVAILABLE", len(reference_rates))
