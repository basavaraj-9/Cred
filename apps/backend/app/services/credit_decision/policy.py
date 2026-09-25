from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import cast

POLICY_VERSION = "credit_decision_policy_v1"
LIMIT_POLICY_VERSION = "credit_limit_policy_v1"
ENGINE_VERSION = "credit_decision_support_engine_v1"
SUMMARY_VERSION = "credit_decision_summary_v1"


@lru_cache
def decision_policy() -> dict[str, object]:
    value = cast(
        dict[str, object],
        json.loads((Path(__file__).parent / "credit_decision_policy_v1.json").read_text()),
    )
    if value.get("version") != POLICY_VERSION or value.get("engine_version") != ENGINE_VERSION:
        raise ValueError("CREDIT_DECISION_POLICY_INVALID")
    return value


@lru_cache
def limit_policy() -> dict[str, object]:
    value = cast(
        dict[str, object],
        json.loads((Path(__file__).parent / "credit_limit_policy_v1.json").read_text()),
    )
    if value.get("version") != LIMIT_POLICY_VERSION:
        raise ValueError("CREDIT_LIMIT_POLICY_INVALID")
    return value


def number(policy: dict[str, object], key: str) -> float:
    value = policy[key]
    if not isinstance(value, (int, float)):
        raise ValueError("POLICY_NUMBER_INVALID")
    return float(value)


def system_recommendation(
    *, insufficient: bool, exceptions: int, adverse: bool, manual: bool, conditional: bool
) -> str:
    if insufficient:
        return "INSUFFICIENT_EVIDENCE"
    if exceptions:
        return "POLICY_EXCEPTION_REVIEW"
    if adverse:
        return "ADVERSE_REVIEW"
    if manual:
        return "MANUAL_REVIEW_REQUIRED"
    if conditional:
        return "CONDITIONAL_REVIEW"
    return "FAVORABLE_REVIEW"
