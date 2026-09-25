from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import cast

SELECTION_POLICY_VERSION = "credit_model_selection_policy_v1"


@lru_cache
def selection_policy() -> dict[str, object]:
    path = Path(__file__).with_name("taxonomy") / f"{SELECTION_POLICY_VERSION}.json"
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def select_model(validation: dict[str, dict[str, object]]) -> tuple[str, str]:
    policy = selection_policy()
    tie_order = cast(list[str], policy["tie_break_order"])

    def score(name: str) -> tuple[float, float, float, int]:
        report = validation[name]
        metrics = report.get("metrics", {})
        assert isinstance(metrics, dict)
        pr_auc = float(metrics.get("pr_auc", -1.0))
        roc_auc = float(metrics.get("roc_auc", -1.0))
        brier = float(metrics.get("brier_score", 2.0))
        return pr_auc, roc_auc, -brier, -tie_order.index(name)

    available = [name for name in tie_order if name in validation]
    if not available:
        raise ValueError("No successfully trained credit model candidates")
    selected = max(available, key=score)
    metrics = validation[selected].get("metrics", {})
    reason = (
        "validation metrics under credit_model_selection_policy_v1"
        if isinstance(metrics, dict) and "pr_auc" in metrics
        else "deterministic fallback order because primary metrics were unavailable"
    )
    return selected, reason
