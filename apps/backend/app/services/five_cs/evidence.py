from __future__ import annotations

from uuid import UUID

from app.services.five_cs.schemas import EvidenceDraft


def draft(
    section: str,
    key: str,
    code: str,
    title: str,
    description: str,
    impact: str,
    confidence: float,
    status: str,
    *,
    evidence_type: str = "INTERNAL_ANALYTIC",
    source_type: str | None = None,
    source_id: UUID | None = None,
    lineage: tuple[UUID, int] | None = None,
    raw_value: str | None = None,
    normalized_value: str | None = None,
) -> EvidenceDraft:
    return EvidenceDraft(
        section=section,
        availability_key=key,
        evidence_type=evidence_type,
        observation_code=code,
        title=title,
        description=description,
        impact=impact,
        confidence=confidence,
        status=status,
        source_type=source_type,
        source_id=source_id,
        document_page_id=lineage[0] if lineage else None,
        page_number=lineage[1] if lineage else None,
        raw_value=raw_value,
        normalized_value=normalized_value,
    )


def unavailable(section: str, key: str, code: str, title: str, description: str) -> EvidenceDraft:
    return draft(
        section,
        key,
        code,
        title,
        description,
        "REVIEW",
        0.0,
        "UNAVAILABLE",
        evidence_type="EXTERNAL_PLACEHOLDER",
    )
