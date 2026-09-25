from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.external_research.schemas import ProviderResult, QueryDraft


class ResearchProvider(ABC):
    name: str
    version: str

    @abstractmethod
    def search(self, query: QueryDraft, legal_name: str) -> list[ProviderResult]:
        """Return normalized provider results without mutating source records."""
