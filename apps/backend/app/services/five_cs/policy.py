from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import cast

POLICY_VERSION = "five_cs_policy_v1"
ENGINE_VERSION = "five_cs_engine_v1"
SUMMARY_VERSION = "five_cs_summary_v1"
COLLATERAL_EXTRACTOR_VERSION = "collateral_evidence_extractor_v1"
SECTIONS = ("CHARACTER", "CAPACITY", "CAPITAL", "COLLATERAL", "CONDITIONS")


@lru_cache
def five_cs_policy() -> dict[str, object]:
    value = cast(
        dict[str, object],
        json.loads((Path(__file__).parent / "five_cs_policy_v1.json").read_text()),
    )
    validate_policy(value)
    return value


def validate_policy(value: dict[str, object]) -> None:
    if value.get("version") != POLICY_VERSION or value.get("engine_version") != ENGINE_VERSION:
        raise ValueError("FIVE_CS_POLICY_VERSION_INVALID")
    if tuple(cast(list[str], value.get("sections", []))) != SECTIONS:
        raise ValueError("FIVE_CS_SECTIONS_INVALID")
    confidence = cast(dict[str, float], value["confidence"])
    completeness = cast(dict[str, object], value["completeness"])
    for threshold in (
        *confidence.values(),
        cast(float, completeness["verified_min"]),
        cast(float, completeness["partial_min"]),
    ):
        if not 0 <= float(threshold) <= 1:
            raise ValueError("FIVE_CS_THRESHOLD_OUT_OF_RANGE")
    required = cast(dict[str, list[str]], value["required_evidence"])
    if set(required) != set(SECTIONS) or any(not items for items in required.values()):
        raise ValueError("FIVE_CS_COMPLETENESS_RULES_INVALID")


def validate_section(section: str) -> str:
    value = section.upper()
    if value not in SECTIONS:
        raise ValueError("FIVE_CS_SECTION_UNKNOWN")
    return value
