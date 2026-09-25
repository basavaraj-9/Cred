from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.models.enums import CreditDatasetSplit, CreditLabelQuality, CreditLabelStatus


@dataclass(frozen=True)
class LabelResult:
    target: int | None
    status: CreditLabelStatus
    quality: CreditLabelQuality
    outcome_id: UUID | None


@dataclass(frozen=True)
class SplitCandidate:
    observation_id: UUID
    company_id: UUID
    observation_date: date
    target: int


@dataclass(frozen=True)
class SplitAssignment:
    observation_id: UUID
    split: CreditDatasetSplit
