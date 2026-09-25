from decimal import ROUND_HALF_UP, Decimal

from app.models.enums import CreditAssessmentStatus, CreditComponent
from app.services.credit_engine.business_stability import score_business_stability
from app.services.credit_engine.data_quality import score_data_quality
from app.services.credit_engine.financial_strength import score_financial_strength
from app.services.credit_engine.industry_context import score_industry_context
from app.services.credit_engine.policy import decimal_setting, risk_band
from app.services.credit_engine.repayment_capacity import score_repayment_capacity
from app.services.credit_engine.schemas import AssessmentResult, CreditFeatures

SCORE_ENGINE_VERSION = "credit_score_engine_v1"


def score_credit(features: CreditFeatures) -> AssessmentResult:
    components = [
        score_financial_strength(features),
        score_repayment_capacity(features),
        score_business_stability(features),
        score_data_quality(features),
        score_industry_context(features),
    ]
    eligible = [
        item
        for item in components
        if item.status
        not in {
            CreditAssessmentStatus.INSUFFICIENT_DATA,
            CreditAssessmentStatus.UNAVAILABLE,
            CreditAssessmentStatus.FAILED,
        }
    ]
    coverage = sum((item.weight for item in eligible), Decimal(0)).quantize(Decimal("0.0001"))
    confidence = Decimal(0)
    if eligible:
        weighted_confidence = (
            sum((item.confidence * item.weight for item in eligible), Decimal(0)) / coverage
        )
        data_quality = next(
            item for item in components if item.component == CreditComponent.DATA_QUALITY
        )
        quality_factor = Decimal("0.5") + data_quality.score / Decimal(200)
        critical = [
            item.confidence
            for item in eligible
            if item.component
            in {
                CreditComponent.FINANCIAL_STRENGTH,
                CreditComponent.REPAYMENT_CAPACITY,
                CreditComponent.BUSINESS_STABILITY,
            }
        ]
        confidence = min(
            weighted_confidence * coverage * quality_factor,
            min(critical) if critical else weighted_confidence,
        ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    if coverage < decimal_setting("minimum_coverage", "overall"):
        return AssessmentResult(
            None, None, coverage, confidence, CreditAssessmentStatus.INSUFFICIENT_DATA, components
        )
    score = (sum((item.score * item.weight for item in eligible), Decimal(0)) / coverage).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if features.critical_conflict or any(
        item.status == CreditAssessmentStatus.CONFLICTING for item in eligible
    ):
        status = CreditAssessmentStatus.CONFLICTING
    elif any(
        item.status == CreditAssessmentStatus.NEEDS_REVIEW for item in eligible
    ) or confidence < Decimal("0.75"):
        status = CreditAssessmentStatus.NEEDS_REVIEW
    else:
        status = CreditAssessmentStatus.VERIFIED
    return AssessmentResult(score, risk_band(score), coverage, confidence, status, components)
