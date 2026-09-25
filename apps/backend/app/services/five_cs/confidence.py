from __future__ import annotations

from typing import cast

from app.services.five_cs.schemas import EvidenceDraft


def section_confidence(
    section: str, evidence: list[EvidenceDraft], policy: dict[str, object]
) -> float:
    available = [item for item in evidence if item.status != "UNAVAILABLE"]
    if not available:
        return 0.0
    value = sum(item.confidence for item in available) / len(available)
    critical_keys = cast(dict[str, list[str]], policy["critical_evidence"]).get(section, [])
    critical = [item.confidence for item in available if item.availability_key in critical_keys]
    if critical:
        value = min(value, min(critical))
    if any(item.status == "CONFLICTING" for item in available):
        value *= 0.6
    elif any(item.status in {"NEEDS_REVIEW", "PARTIAL"} for item in available):
        value *= 0.85
    return max(0.0, min(1.0, value))


def overall_confidence(values: list[float], completeness: list[float]) -> float:
    supported = [confidence for confidence, coverage in zip(values, completeness) if coverage > 0]
    return min(supported) if supported else 0.0


def section_status(
    section: str,
    evidence: list[EvidenceDraft],
    completeness: float,
    confidence: float,
    policy: dict[str, object],
) -> str:
    if any(item.status == "CONFLICTING" for item in evidence):
        return "CONFLICTING"
    if not any(item.status != "UNAVAILABLE" for item in evidence):
        return "UNAVAILABLE"
    if any(item.status == "NEEDS_REVIEW" for item in evidence):
        return "NEEDS_REVIEW"
    if section in {"CHARACTER", "CONDITIONS"}:
        return "PARTIAL"
    if section == "COLLATERAL":
        return "PARTIAL"
    thresholds = cast(dict[str, float], policy["confidence"])
    completeness_policy = cast(dict[str, float], policy["completeness"])
    if (
        completeness >= float(completeness_policy["verified_min"])
        and confidence >= thresholds["verified_min"]
    ):
        return "VERIFIED"
    return "PARTIAL" if completeness >= float(completeness_policy["partial_min"]) else "UNAVAILABLE"
