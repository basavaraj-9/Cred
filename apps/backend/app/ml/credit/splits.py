import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.ml.credit.schemas import SplitAssignment, SplitCandidate
from app.models.enums import CreditDatasetSplit

POLICY_PATH = Path(__file__).parent / "taxonomy" / "credit_split_policy_v1.json"


@lru_cache(maxsize=1)
def split_policy() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if payload.get("version") != "credit_split_policy_v1":
        raise ValueError("Unexpected credit split policy version")
    fractions = [
        float(payload[name]) for name in ("train_fraction", "validation_fraction", "test_fraction")
    ]
    if abs(sum(fractions) - 1) > 1e-9 or any(value <= 0 for value in fractions):
        raise ValueError("Credit split fractions must be positive and sum to one")
    return payload


SPLIT_POLICY_VERSION = str(split_policy()["version"])


def company_grouped_chronological_split(candidates: list[SplitCandidate]) -> list[SplitAssignment]:
    if not candidates:
        return []
    groups: dict[object, list[SplitCandidate]] = defaultdict(list)
    for item in candidates:
        groups[item.company_id].append(item)
    ordered = sorted(
        groups.values(),
        key=lambda rows: (min(item.observation_date for item in rows), str(rows[0].company_id)),
    )
    count = len(ordered)
    train_end = max(1, round(count * float(split_policy()["train_fraction"])))
    validation_count = (
        max(1, round(count * float(split_policy()["validation_fraction"]))) if count >= 3 else 0
    )
    validation_end = min(count, train_end + validation_count)
    if validation_end == count and count >= 3:
        validation_end -= 1
    result: list[SplitAssignment] = []
    for index, rows in enumerate(ordered):
        split = (
            CreditDatasetSplit.TRAIN
            if index < train_end
            else CreditDatasetSplit.VALIDATION
            if index < validation_end
            else CreditDatasetSplit.TEST
        )
        result.extend(SplitAssignment(item.observation_id, split) for item in rows)
    return result
