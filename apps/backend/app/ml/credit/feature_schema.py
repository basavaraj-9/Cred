import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parent / "taxonomy" / "credit_ml_features_v1.json"


@lru_cache(maxsize=1)
def feature_schema() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if payload.get("version") != "credit_ml_features_v1":
        raise ValueError("Unexpected credit feature schema version")
    if payload["default_feature_group"] not in payload["feature_groups"]:
        raise ValueError("Default credit feature group is unknown")
    return payload


FEATURE_SCHEMA_VERSION = str(feature_schema()["version"])
FEATURE_BUILDER_VERSION = "credit_ml_feature_builder_v1"


def validate_features(features: dict[str, object], feature_group: str) -> None:
    schema = feature_schema()
    if feature_group not in schema["feature_groups"]:
        raise ValueError(f"Unknown credit feature group: {feature_group}")
    forbidden = set(schema["forbidden_features"])
    leaked = forbidden.intersection(features)
    if leaked:
        raise ValueError(f"Forbidden predictive features: {sorted(leaked)}")
    for name, value in features.items():
        if value is None:
            continue
        if name.startswith(schema["binary_prefix"]) and value not in {0, 1}:
            raise ValueError(f"Binary feature {name} must be 0 or 1")
        if name == "financial_completeness" and (
            not isinstance(value, (int, float)) or not (0 <= float(value) <= 1)
        ):
            raise ValueError("financial_completeness must be between zero and one")
        if name.endswith(schema["confidence_suffix"]) and (
            not isinstance(value, (int, float)) or not (0 <= float(value) <= 1)
        ):
            raise ValueError(f"Confidence feature {name} is outside zero to one")
        if not isinstance(value, (int, float, str, bool)):
            raise ValueError(f"Feature {name} has an unsupported type")
