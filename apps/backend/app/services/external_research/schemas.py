from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class QueryDraft:
    scope: str
    text: str


@dataclass(frozen=True)
class ProviderResult:
    scope: str
    title: str
    publisher: str
    source_type: str
    url: str
    text: str
    entity_name: str
    event_code: str
    impact: str
    publication_date: date | None = None
    event_date: date | None = None
    attributes: dict[str, object] = field(default_factory=dict)
    mime_type: str = "text/html"
    failure_code: str | None = None
