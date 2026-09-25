from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TypedDict


class AnomalyRules(TypedDict):
    version: str
    thresholds: dict[str, float]


RULES_PATH = Path(__file__).parent / "taxonomy" / "financial_anomaly_rules_v1.json"


@lru_cache(maxsize=1)
def anomaly_rules() -> AnomalyRules:
    payload: AnomalyRules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    if payload["version"] != "financial_anomaly_rules_v1":
        raise ValueError("Unexpected financial anomaly rules version")
    return payload


ANOMALY_RULE_VERSION = anomaly_rules()["version"]
