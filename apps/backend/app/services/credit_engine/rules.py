from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.models.enums import CreditAssessmentStatus, CreditComponent, CreditReasonType
from app.services.credit_engine.policy import credit_policy, decimal_setting
from app.services.credit_engine.schemas import (
    AnomalyFeature,
    ComponentResult,
    MetricFeature,
    RuleResult,
    TrendFeature,
)

Feature = MetricFeature | TrendFeature | AnomalyFeature


def clamp_score(value: Decimal) -> Decimal:
    return min(Decimal(100), max(Decimal(0), value)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def rule(
    code: str,
    message: str,
    source: Feature | None = None,
    *,
    metric: str | None = None,
    value: Decimal | None = None,
    status: str = "VERIFIED",
    confidence: Decimal = Decimal(1),
    source_role: str | None = None,
) -> RuleResult:
    definition = credit_policy()["rules"][code]
    impact = Decimal(str(definition["impact"]))
    component = CreditComponent(definition["component"])
    if source is not None:
        metric = source.name
        status = source.status
        confidence = source.confidence
        source_role = source.source_role
        value = source.value if isinstance(source, MetricFeature) else value
    result_status = (
        CreditAssessmentStatus.CONFLICTING
        if status in {"CONFLICTING", "CURRENCY_MISMATCH"}
        else CreditAssessmentStatus.NEEDS_REVIEW
        if status in {"NEEDS_REVIEW", "UNAVAILABLE", "NOT_MEANINGFUL", "INSUFFICIENT_DATA"}
        else CreditAssessmentStatus.VERIFIED
    )
    reason_type = (
        CreditReasonType.REVIEW
        if result_status != CreditAssessmentStatus.VERIFIED
        else CreditReasonType.POSITIVE
        if impact > 0
        else CreditReasonType.NEGATIVE
        if impact < 0
        else CreditReasonType.NEUTRAL
    )
    return RuleResult(
        component,
        code,
        metric or code.lower(),
        value,
        status,
        impact,
        abs(impact),
        reason_type,
        message,
        confidence,
        result_status,
        source_role,
    )


def finish_component(
    component: CreditComponent,
    rules: list[RuleResult],
    coverage: Decimal,
    confidences: list[Decimal],
    *,
    conflict: bool = False,
) -> ComponentResult:
    score = clamp_score(
        decimal_setting("base_score") + sum((item.impact for item in rules), Decimal(0))
    )
    minimum = decimal_setting("minimum_coverage", component.value)
    if coverage < minimum:
        status = CreditAssessmentStatus.INSUFFICIENT_DATA
    elif conflict or any(item.status == CreditAssessmentStatus.CONFLICTING for item in rules):
        status = CreditAssessmentStatus.CONFLICTING
    elif any(item.status == CreditAssessmentStatus.NEEDS_REVIEW for item in rules):
        status = CreditAssessmentStatus.NEEDS_REVIEW
    else:
        status = CreditAssessmentStatus.VERIFIED
    confidence = (min(confidences) if confidences else Decimal(0)) * coverage
    return ComponentResult(
        component,
        score,
        decimal_setting("component_weights", component.value),
        coverage.quantize(Decimal("0.0001")),
        min(Decimal(1), max(Decimal(0), confidence)).quantize(Decimal("0.0001")),
        status,
        rules,
    )
