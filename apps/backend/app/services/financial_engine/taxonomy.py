import json
import re
from functools import lru_cache
from pathlib import Path

TAXONOMY_VERSION = "financial_line_items_v1"
TAXONOMY_PATH = Path(__file__).parent / "taxonomy" / f"{TAXONOMY_VERSION}.json"
STATEMENT_TYPES = {"INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW_STATEMENT"}
MEASUREMENT_TYPES = {"MONETARY", "PER_SHARE", "PERCENTAGE"}


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def validate_taxonomy(payload: dict) -> None:
    if payload.get("version") != TAXONOMY_VERSION or not isinstance(payload.get("items"), list):
        raise ValueError("Invalid financial taxonomy version or items")
    names: set[str] = set()
    synonyms: dict[tuple[str, str], str] = {}
    for item in payload["items"]:
        if not {"name", "statement_type", "measurement_type", "synonyms"} <= item.keys():
            raise ValueError("Financial taxonomy item lacks a required field")
        name = item["name"]
        if name in names or item["statement_type"] not in STATEMENT_TYPES:
            raise ValueError("Duplicate name or invalid statement type")
        if item["measurement_type"] not in MEASUREMENT_TYPES or not item["synonyms"]:
            raise ValueError("Invalid measurement type or empty synonyms")
        names.add(name)
        for synonym in [name.replace("_", " "), *item["synonyms"]]:
            key = (item["statement_type"], normalize_label(synonym))
            if not key[1] or (key in synonyms and synonyms[key] != name):
                raise ValueError(f"Ambiguous financial synonym: {synonym}")
            synonyms[key] = name


@lru_cache
def taxonomy() -> dict:
    payload = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    validate_taxonomy(payload)
    return payload


@lru_cache
def synonym_index() -> dict[tuple[str, str], tuple[str, str]]:
    index = {}
    for item in taxonomy()["items"]:
        for synonym in [item["name"].replace("_", " "), *item["synonyms"]]:
            index[(item["statement_type"], normalize_label(synonym))] = (
                item["name"],
                item["measurement_type"],
            )
    return index


def map_label(statement_type: str, raw_label: str) -> tuple[str, str] | None:
    return synonym_index().get((statement_type, normalize_label(raw_label)))
