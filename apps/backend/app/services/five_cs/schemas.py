from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class EvidenceDraft:
    section: str
    availability_key: str
    evidence_type: str
    observation_code: str
    title: str
    description: str
    impact: str
    confidence: float
    status: str
    source_type: str | None = None
    source_id: UUID | None = None
    document_page_id: UUID | None = None
    page_number: int | None = None
    raw_value: str | None = None
    normalized_value: str | None = None


@dataclass(frozen=True)
class SectionResult:
    section: str
    status: str
    confidence: float
    completeness: float
    summary: str
    evidence: tuple[EvidenceDraft, ...]
