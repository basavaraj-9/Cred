import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models.enums import CreditOutcomeType

POLICY_PATH = Path(__file__).parent / "taxonomy" / "credit_label_policy_v1.json"


@lru_cache(maxsize=1)
def label_policy() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if payload.get("version") != "credit_label_policy_v1":
        raise ValueError("Unexpected credit label policy version")
    all_names = {item.value for item in CreditOutcomeType}
    mapped = (
        set(payload["default_events"])
        | set(payload["non_default_evidence"])
        | set(payload["review_events"])
    )
    if mapped != all_names:
        raise ValueError("Every credit outcome type must have exactly one label-policy mapping")
    if sum(
        map(
            len,
            (payload["default_events"], payload["non_default_evidence"], payload["review_events"]),
        )
    ) != len(mapped):
        raise ValueError("Credit outcome mappings overlap")
    if int(payload["default_prediction_horizon_days"]) <= 0:
        raise ValueError("Prediction horizon must be positive")
    return payload


LABEL_POLICY_VERSION = str(label_policy()["version"])
