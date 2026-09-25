from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.models.enums import (
    CreditAssessmentStatus,
    CreditComponent,
    CreditReasonType,
    CreditRiskBand,
    FinancialScope,
)


@dataclass(frozen=True)
class MetricFeature:
    name: str
    value: Decimal | None
    status: str
    confidence: Decimal
    source_id: UUID
    source_role: str


@dataclass(frozen=True)
class TrendFeature:
    name: str
    direction: str
    status: str
    confidence: Decimal
    missing_periods: int
    source_id: UUID
    source_role: str
    source_signature: str = ""


@dataclass(frozen=True)
class AnomalyFeature:
    name: str
    severity: str
    status: str
    confidence: Decimal
    source_id: UUID
    source_role: str
    source_signature: str = ""


@dataclass(frozen=True)
class InputRef:
    role: str
    source_type: str
    source_id: UUID


@dataclass
class CreditFeatures:
    scope: FinancialScope
    ratios: dict[str, MetricFeature] = field(default_factory=dict)
    values: dict[str, MetricFeature] = field(default_factory=dict)
    trends: dict[str, TrendFeature] = field(default_factory=dict)
    anomalies: dict[str, AnomalyFeature] = field(default_factory=dict)
    completeness: Decimal = Decimal(0)
    validation_errors: int = 0
    conflicting_inputs: int = 0
    verified_ratio_share: Decimal = Decimal(0)
    missing_period_count: int = 0
    profile_status: str | None = None
    profile_confidence: Decimal | None = None
    domain_status: str | None = None
    domain_confidence: Decimal | None = None
    input_refs: list[InputRef] = field(default_factory=list)
    critical_conflict: bool = False


@dataclass(frozen=True)
class RuleResult:
    component: CreditComponent
    code: str
    input_metric: str
    input_value: Decimal | None
    input_status: str
    impact: Decimal
    max_impact: Decimal
    reason_type: CreditReasonType
    message: str
    confidence: Decimal
    status: CreditAssessmentStatus
    source_role: str | None


@dataclass
class ComponentResult:
    component: CreditComponent
    score: Decimal
    weight: Decimal
    coverage: Decimal
    confidence: Decimal
    status: CreditAssessmentStatus
    rules: list[RuleResult] = field(default_factory=list)


@dataclass
class AssessmentResult:
    score: Decimal | None
    risk_band: CreditRiskBand | None
    component_coverage: Decimal
    confidence: Decimal
    status: CreditAssessmentStatus
    components: list[ComponentResult]
