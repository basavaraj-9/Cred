from __future__ import annotations

from datetime import UTC, date, datetime

ENGINE_VERSION = "external_research_engine_v1"
QUERY_BUILDER_VERSION = "research_query_builder_v1"
EVIDENCE_EXTRACTOR_VERSION = "research_evidence_extractor_v1"
FINDING_VERSION = "research_finding_v1"
SOURCE_POLICY_VERSION = "research_source_quality_v1"
FRESHNESS_POLICY_VERSION = "research_freshness_policy_v1"
VALID_SCOPES = ("COMPANY", "PROMOTER", "LEGAL", "RATINGS", "INDUSTRY", "SECTOR")

SOURCE_QUALITY: dict[str, tuple[int, float]] = {
    "OFFICIAL": (1, 0.98),
    "REGULATOR": (1, 0.98),
    "GOVERNMENT": (1, 0.96),
    "RATING_AGENCY": (1, 0.96),
    "INDUSTRY_BODY": (2, 0.84),
    "REPUTABLE_NEWS": (2, 0.78),
    "OTHER": (3, 0.55),
}


def source_quality(source_type: str) -> tuple[int, float]:
    return SOURCE_QUALITY.get(source_type, SOURCE_QUALITY["OTHER"])


def freshness(publication_date: date | None, category: str, today: date | None = None) -> str:
    if publication_date is None:
        return "UNKNOWN"
    age = ((today or datetime.now(UTC).date()) - publication_date).days
    if category == "LEGAL" and age > 730:
        return "HISTORICAL"
    limit = 365 if category in {"RATINGS", "INDUSTRY", "SECTOR"} else 730
    return "CURRENT" if age <= limit else "STALE"
