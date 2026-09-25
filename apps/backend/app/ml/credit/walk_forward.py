from __future__ import annotations

# ruff: noqa: E501
from dataclasses import dataclass
from datetime import date
from typing import cast


@dataclass(frozen=True)
class WalkForwardWindow:
    number: int
    mode: str
    train_rows: list[dict[str, object]]
    evaluation_rows: list[dict[str, object]]
    status: str
    skip_reason: str | None

    @property
    def train_dates(self) -> list[date]:
        return [_date(row) for row in self.train_rows]

    @property
    def evaluation_dates(self) -> list[date]:
        return [_date(row) for row in self.evaluation_rows]


def _date(row: dict[str, object]) -> date:
    value = row["observation_date"]
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _target_count(rows: list[dict[str, object]], target: int) -> int:
    return sum(int(cast(int, row["target_value"])) == target for row in rows)


def _skip_reason(
    train: list[dict[str, object]], evaluation: list[dict[str, object]], policy: dict[str, object]
) -> str | None:
    if not train or not evaluation or max(map(_date, train)) >= min(map(_date, evaluation)):
        return "TEMPORAL_LEAKAGE"
    if len(train) < int(cast(int, policy["minimum_training_examples"])):
        return "INSUFFICIENT_TRAINING_SUPPORT"
    if len(evaluation) < int(cast(int, policy["minimum_evaluation_examples"])):
        return "INSUFFICIENT_EVALUATION_SUPPORT"
    if not _target_count(train, 0) or not _target_count(train, 1):
        return "SINGLE_CLASS_TRAIN"
    if _target_count(train, 1) < int(
        cast(int, policy["minimum_positives_training"])
    ) or _target_count(train, 0) < int(cast(int, policy["minimum_negatives_training"])):
        return "INSUFFICIENT_TRAINING_SUPPORT"
    if _target_count(evaluation, 1) < int(
        cast(int, policy["minimum_positives_evaluation"])
    ) or _target_count(evaluation, 0) < int(cast(int, policy["minimum_negatives_evaluation"])):
        return "INSUFFICIENT_EVALUATION_SUPPORT"
    return None


def generate_walk_forward_windows(
    records: list[dict[str, object]], policy: dict[str, object], mode: str
) -> list[WalkForwardWindow]:
    supported = cast(list[str], policy["supported_modes"])
    if mode not in supported:
        raise ValueError("UNSUPPORTED_WALK_FORWARD_MODE")
    ordered = sorted(records, key=lambda row: (_date(row), str(row.get("company_id", ""))))
    periods = sorted({_date(row) for row in ordered})
    train_periods = int(cast(int, policy["training_window_length"]))
    evaluation_periods = int(cast(int, policy["evaluation_window_length"]))
    step = int(cast(int, policy["step_size"]))
    windows: list[WalkForwardWindow] = []
    number = 1
    for evaluation_index in range(train_periods, len(periods), step):
        evaluation_dates = set(periods[evaluation_index : evaluation_index + evaluation_periods])
        if len(evaluation_dates) < evaluation_periods:
            break
        if mode == "ROLLING_WINDOW":
            training_dates = set(periods[evaluation_index - train_periods : evaluation_index])
        else:
            training_dates = set(periods[:evaluation_index])
        evaluation = [row for row in ordered if _date(row) in evaluation_dates]
        evaluation_companies = {str(row.get("company_id")) for row in evaluation}
        train = [
            row
            for row in ordered
            if _date(row) in training_dates
            and (
                policy.get("company_isolation_policy") != "STRICT_WINDOW_ISOLATION"
                or str(row.get("company_id")) not in evaluation_companies
            )
        ]
        reason = _skip_reason(train, evaluation, policy)
        windows.append(
            WalkForwardWindow(
                number=number,
                mode=mode,
                train_rows=train,
                evaluation_rows=evaluation,
                status="SKIPPED" if reason else "VALID",
                skip_reason=reason,
            )
        )
        number += 1
    return windows
