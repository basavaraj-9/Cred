import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

AUTHORITY_POLICY_VERSION = "credit_review_authority_policy_v1"
COMMITTEE_SUMMARY_VERSION = "credit_committee_summary_v1"


@lru_cache
def authority_policy() -> dict[str, Any]:
    path = Path(__file__).with_name(f"{AUTHORITY_POLICY_VERSION}.json")
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
