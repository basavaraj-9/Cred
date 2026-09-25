from __future__ import annotations

from typing import cast

from app.services.five_cs.schemas import EvidenceDraft


def section_completeness(
    section: str, evidence: list[EvidenceDraft], policy: dict[str, object]
) -> float:
    required = cast(dict[str, list[str]], policy["required_evidence"])[section]
    available = {
        item.availability_key
        for item in evidence
        if item.status not in {"UNAVAILABLE", "CONFLICTING"}
    }
    return len(set(required) & available) / len(required)


def overall_completeness(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
