from decimal import Decimal

from app.models.enums import CreditAssessmentStatus, CreditComponent
from app.services.credit_engine.policy import decimal_setting
from app.services.credit_engine.rules import rule
from app.services.credit_engine.schemas import ComponentResult, CreditFeatures


def score_industry_context(features: CreditFeatures) -> ComponentResult:
    weight = decimal_setting("component_weights", CreditComponent.INDUSTRY_CONTEXT.value)
    if features.domain_status != "VERIFIED":
        return ComponentResult(
            CreditComponent.INDUSTRY_CONTEXT,
            decimal_setting("base_score"),
            weight,
            Decimal(0),
            Decimal(0),
            CreditAssessmentStatus.UNAVAILABLE,
            [],
        )
    confidence = features.domain_confidence or Decimal(0)
    result = rule(
        "VERIFIED_DOMAIN_CONTEXT",
        "Verified domain evidence is available; no sector risk assumption was applied.",
        metric="domain_classification",
        status="VERIFIED",
        confidence=confidence,
        source_role="domain_classification",
    )
    return ComponentResult(
        CreditComponent.INDUSTRY_CONTEXT,
        decimal_setting("base_score") + result.impact,
        weight,
        Decimal(1),
        confidence,
        CreditAssessmentStatus.VERIFIED,
        [result],
    )
