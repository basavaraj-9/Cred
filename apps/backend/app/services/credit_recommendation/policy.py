from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import cast

POLICY_VERSION = "credit_recommendation_policy_v1"
ENGINE_VERSION = "credit_recommendation_engine_v1"
SUMMARY_VERSION = "credit_recommendation_summary_v1"


@lru_cache
def policy() -> dict[str, object]:
    value = cast(
        dict[str, object],
        json.loads((Path(__file__).parent / "credit_recommendation_policy_v1.json").read_text()),
    )
    if value.get("version") != POLICY_VERSION or value.get("engine_version") != ENGINE_VERSION:
        raise ValueError("CREDIT_RECOMMENDATION_POLICY_INVALID")
    return value


def policy_number(key: str) -> float:
    value = policy()[key]
    if not isinstance(value, (int, float)):
        raise ValueError("CREDIT_RECOMMENDATION_POLICY_INVALID")
    return float(value)


def recommendation_status(
    *,
    inputs_ready: bool,
    conflict: bool,
    critical_count: int,
    sufficient: bool,
    review_count: int,
    missing_count: int,
) -> str:
    if not inputs_ready:
        return "NOT_READY"
    if conflict:
        return "DATA_CONFLICT_REVIEW"
    if critical_count:
        return "CRITICAL_RISK_REVIEW"
    if not sufficient:
        return "INSUFFICIENT_EVIDENCE"
    if review_count or missing_count:
        return "CONDITIONAL_REVIEW_REQUIRED"
    return "READY_FOR_DECISION_REVIEW"
