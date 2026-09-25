from decimal import Decimal

from app.models.enums import CreditComponent
from app.services.credit_engine.policy import credit_policy
from app.services.credit_engine.rules import finish_component, rule
from app.services.credit_engine.schemas import ComponentResult, CreditFeatures, RuleResult


def score_data_quality(features: CreditFeatures) -> ComponentResult:
    rules: list[RuleResult] = []
    limits = credit_policy()["thresholds"]
    if features.completeness >= Decimal(str(limits["completeness"]["high_min"])):
        code = "HIGH_DATA_COMPLETENESS"
    elif features.completeness <= Decimal(str(limits["completeness"]["low_max"])):
        code = "LOW_DATA_COMPLETENESS"
    else:
        code = "MODERATE_DATA_COMPLETENESS"
    rules.append(
        rule(
            code,
            f"Core financial data completeness is {features.completeness:.0%}.",
            metric="completeness",
            value=features.completeness,
        )
    )
    rules.append(
        rule(
            "NO_VALIDATION_ERRORS" if features.validation_errors == 0 else "VALIDATION_ERRORS",
            f"Financial validation produced {features.validation_errors} error(s).",
            metric="validation_errors",
            value=Decimal(features.validation_errors),
        )
    )
    rules.append(
        rule(
            "NO_CONFLICTING_INPUTS"
            if features.conflicting_inputs == 0
            else "CONFLICTING_FINANCIAL_INPUTS",
            f"The financial inputs contain {features.conflicting_inputs} conflict(s).",
            metric="conflicting_inputs",
            value=Decimal(features.conflicting_inputs),
            status="CONFLICTING" if features.conflicting_inputs else "VERIFIED",
        )
    )
    if features.verified_ratio_share >= Decimal(str(limits["verified_ratio_share"]["high_min"])):
        rules.append(
            rule(
                "HIGH_VERIFIED_RATIO_SHARE",
                f"Verified ratio share is {features.verified_ratio_share:.0%}.",
                metric="verified_ratio_share",
                value=features.verified_ratio_share,
            )
        )
    elif features.verified_ratio_share <= Decimal(str(limits["verified_ratio_share"]["low_max"])):
        rules.append(
            rule(
                "LOW_VERIFIED_RATIO_SHARE",
                f"Verified ratio share is {features.verified_ratio_share:.0%}.",
                metric="verified_ratio_share",
                value=features.verified_ratio_share,
                status="NEEDS_REVIEW",
            )
        )
    rules.append(
        rule(
            "COMPLETE_FINANCIAL_PERIODS"
            if features.missing_period_count == 0
            else "MISSING_FINANCIAL_PERIODS",
            f"Trend inputs contain {features.missing_period_count} missing period(s).",
            metric="missing_periods",
            value=Decimal(features.missing_period_count),
            status="VERIFIED" if features.missing_period_count == 0 else "NEEDS_REVIEW",
        )
    )
    if features.profile_status:
        verified = features.profile_status == "VERIFIED"
        rules.append(
            rule(
                "PROFILE_EVIDENCE_VERIFIED" if verified else "PROFILE_EVIDENCE_REVIEW",
                f"Company profile evidence status is {features.profile_status}.",
                metric="profile_status",
                status="VERIFIED" if verified else "NEEDS_REVIEW",
                confidence=features.profile_confidence or Decimal(0),
                source_role="company_profile",
            )
        )
    confidence = [features.completeness]
    if features.profile_confidence is not None:
        confidence.append(features.profile_confidence)
    return finish_component(
        CreditComponent.DATA_QUALITY,
        rules,
        Decimal(1),
        confidence,
        conflict=features.critical_conflict,
    )
