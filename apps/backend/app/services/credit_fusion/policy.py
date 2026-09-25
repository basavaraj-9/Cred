from __future__ import annotations

# ruff: noqa: E501
import json
from functools import lru_cache
from pathlib import Path
from typing import cast

FUSION_POLICY_VERSION = "credit_fusion_policy_v1"
FUSION_BAND_VERSION = "credit_fusion_risk_bands_v1"
FUSION_ENGINE_VERSION = "credit_fusion_engine_v1"


@lru_cache
def load_policy(version: str = FUSION_POLICY_VERSION) -> dict[str, object]:
    path = Path(__file__).with_name(f"{version}.json")
    data = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    validate_policy(data)
    return data


@lru_cache
def load_bands(version: str = FUSION_BAND_VERSION) -> dict[str, object]:
    path = Path(__file__).with_name(f"{version}.json")
    data = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    bands = cast(list[dict[str, object]], data["bands"])
    if (
        not bands
        or float(cast(float, bands[0]["lower"])) != 0
        or float(cast(float, bands[-1]["upper"])) != 1
    ):
        raise ValueError("FUSION_BAND_RANGES_INVALID")
    for previous, current in zip(bands, bands[1:]):
        if float(cast(float, previous["upper"])) != float(cast(float, current["lower"])):
            raise ValueError("FUSION_BAND_RANGES_INVALID")
    return data


def validate_policy(value: dict[str, object]) -> None:
    weighted = cast(dict[str, object], value["weighted_blend"])
    rule_weight = float(cast(float, weighted["rule_weight"]))
    ml_weight = float(cast(float, weighted["ml_weight"]))
    if not 0 <= rule_weight <= 1 or not 0 <= ml_weight <= 1:
        raise ValueError("FUSION_WEIGHT_OUT_OF_RANGE")
    if abs(rule_weight + ml_weight - 1) > 1e-12:
        raise ValueError("FUSION_WEIGHTS_MUST_SUM_TO_ONE")
    agreement = cast(dict[str, object], value["agreement"])
    low = float(cast(float, agreement["low_gap_max"]))
    review = float(cast(float, agreement["review_gap_max"]))
    if not 0 <= low < review <= 1:
        raise ValueError("FUSION_GAP_THRESHOLDS_INVALID")
    cap = float(
        cast(float, cast(dict[str, object], value["confidence"])["pipeline_validation_cap"])
    )
    if not 0 <= cap <= 1:
        raise ValueError("FUSION_CONFIDENCE_CAP_INVALID")


def experimental_band(risk_index: float) -> str:
    if not 0 <= risk_index <= 1:
        raise ValueError("FUSION_RISK_INDEX_OUT_OF_RANGE")
    for band in cast(list[dict[str, object]], load_bands()["bands"]):
        lower = float(cast(float, band["lower"]))
        upper = float(cast(float, band["upper"]))
        if lower <= risk_index < upper or risk_index == upper == 1:
            return str(band["name"])
    raise ValueError("FUSION_BAND_NOT_FOUND")
