from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models.enums import CreditComponent, CreditRiskBand

POLICY_PATH = Path(__file__).parent / "taxonomy" / "credit_policy_v1.json"


@lru_cache(maxsize=1)
def credit_policy() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if payload.get("version") != "credit_policy_v1":
        raise ValueError("Unexpected credit policy version")
    weights = {name: Decimal(str(value)) for name, value in payload["component_weights"].items()}
    if set(weights) != {component.value for component in CreditComponent}:
        raise ValueError("Credit policy contains unknown or missing components")
    if sum(weights.values()) != Decimal(1):
        raise ValueError("Credit component weights must sum to one")
    bands = payload["risk_bands"]
    minimums = [Decimal(str(item["minimum"])) for item in bands]
    if minimums != sorted(minimums, reverse=True) or minimums[-1] != 0:
        raise ValueError("Risk bands must be descending and terminate at zero")
    if len({item["band"] for item in bands}) != len(CreditRiskBand):
        raise ValueError("Risk bands must be unique and complete")
    rules = payload["rules"]
    if len(rules) != len(set(rules)):
        raise ValueError("Credit reason codes must be unique")
    if any(rule["component"] not in weights for rule in rules.values()):
        raise ValueError("Credit rule references an unknown component")
    thresholds = payload["thresholds"]
    ordered_checks = (
        ("debt_to_equity", "strong_max", "moderate_positive_max", "moderate_max"),
        ("debt_to_assets", "strong_max", "moderate_max"),
        ("interest_coverage", "weak_min", "moderate_min", "strong_min"),
        ("debt_to_ebitda", "strong_max", "moderate_max", "weak_max"),
        ("current_ratio", "moderate_min", "strong_min"),
        ("quick_ratio", "moderate_min", "strong_min"),
        ("operating_cash_flow_to_debt", "moderate_min", "strong_min"),
    )
    for metric, *keys in ordered_checks:
        values = [Decimal(str(thresholds[metric][key])) for key in keys]
        if values != sorted(values) or len(values) != len(set(values)):
            raise ValueError(f"Credit policy threshold ordering is invalid for {metric}")
    return payload


CREDIT_POLICY_VERSION = str(credit_policy()["version"])


def decimal_setting(*path: str) -> Decimal:
    value: Any = credit_policy()
    for part in path:
        value = value[part]
    return Decimal(str(value))


def risk_band(score: Decimal) -> CreditRiskBand:
    for item in credit_policy()["risk_bands"]:
        if score >= Decimal(str(item["minimum"])):
            return CreditRiskBand(item["band"])
    raise ValueError("Credit score did not match a configured risk band")
