import json

# ruff: noqa: E501
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

RATIO_TAXONOMY_VERSION = "financial_ratios_v1"
RATIO_PATH = Path(__file__).parent / "taxonomy" / f"{RATIO_TAXONOMY_VERSION}.json"


class RatioDefinition(TypedDict):
    name: str
    display_name: str
    category: str
    formula: str
    required_inputs: list[str]
    unit: str
    description: str


@lru_cache
def ratio_definitions() -> list[RatioDefinition]:
    payload = json.loads(RATIO_PATH.read_text(encoding="utf-8"))
    if payload.get("version") != RATIO_TAXONOMY_VERSION or not payload.get("ratios"):
        raise ValueError("Invalid ratio taxonomy")
    names: set[str] = set()
    required = {
        "name",
        "display_name",
        "category",
        "formula",
        "required_inputs",
        "unit",
        "description",
    }
    for ratio in payload["ratios"]:
        if not required <= ratio.keys() or ratio["name"] in names or not ratio["required_inputs"]:
            raise ValueError("Invalid or duplicate ratio definition")
        names.add(ratio["name"])
    return payload["ratios"]
