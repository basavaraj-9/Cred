from decimal import Decimal

from app.models.enums import CreditComponent
from app.services.credit_engine.overlap import suppress_overlaps
from app.services.credit_engine.policy import credit_policy
from app.services.credit_engine.rules import finish_component, rule
from app.services.credit_engine.schemas import (
    ComponentResult,
    CreditFeatures,
    MetricFeature,
    RuleResult,
)


def score_repayment_capacity(features: CreditFeatures) -> ComponentResult:
    rules: list[RuleResult] = []
    used: list[MetricFeature] = []
    thresholds = credit_policy()["thresholds"]

    def eligible(name: str, values: bool = False) -> MetricFeature | None:
        item = (features.values if values else features.ratios).get(name)
        if (
            item
            and item.value is not None
            and item.status
            not in {"UNAVAILABLE", "NOT_MEANINGFUL", "CONFLICTING", "CURRENCY_MISMATCH"}
        ):
            used.append(item)
            return item
        return None

    if item := eligible("interest_coverage"):
        assert item.value is not None
        limit = thresholds["interest_coverage"]
        code = (
            "STRONG_INTEREST_COVERAGE"
            if item.value >= Decimal(str(limit["strong_min"]))
            else "MODERATE_INTEREST_COVERAGE"
            if item.value >= Decimal(str(limit["moderate_min"]))
            else "LOW_INTEREST_COVERAGE"
            if item.value >= Decimal(str(limit["weak_min"]))
            else "VERY_LOW_INTEREST_COVERAGE"
        )
        rules.append(
            rule(
                code, f"Interest coverage is {item.value:.2f}x under the development policy.", item
            )
        )
    if item := eligible("debt_to_ebitda"):
        assert item.value is not None
        limit = thresholds["debt_to_ebitda"]
        code = (
            "LOW_DEBT_TO_EBITDA"
            if item.value < Decimal(str(limit["strong_max"]))
            else "MODERATE_DEBT_TO_EBITDA"
            if item.value <= Decimal(str(limit["moderate_max"]))
            else "WEAK_DEBT_TO_EBITDA"
            if item.value <= Decimal(str(limit["weak_max"]))
            else "HIGH_DEBT_TO_EBITDA"
        )
        rules.append(
            rule(code, f"Debt to EBITDA is {item.value:.2f}x under the development policy.", item)
        )
    if item := eligible("operating_cash_flow_to_debt"):
        assert item.value is not None
        limit = thresholds["operating_cash_flow_to_debt"]
        if item.value >= Decimal(str(limit["strong_min"])):
            rules.append(
                rule(
                    "STRONG_OCF_TO_DEBT", f"Operating cash flow to debt is {item.value:.2f}x.", item
                )
            )
        elif item.value > 0:
            rules.append(
                rule(
                    "POSITIVE_OCF_TO_DEBT",
                    f"Operating cash flow to debt is positive at {item.value:.2f}x.",
                    item,
                )
            )
    ocf = eligible("cash_flow_from_operations", values=True)
    anomalies = suppress_overlaps(features.anomalies)
    ocf_value = ocf.value if ocf else None
    if ocf and ocf_value is not None and ocf_value > 0:
        rules.append(
            rule("POSITIVE_OPERATING_CASH_FLOW", "Latest operating cash flow is positive.", ocf)
        )
    negative = anomalies.get("PERSISTENT_NEGATIVE_OPERATING_CASH_FLOW") or anomalies.get(
        "NEGATIVE_OPERATING_CASH_FLOW"
    )
    if negative:
        rules.append(
            rule(
                negative.name,
                "Operating cash flow is negative across the applicable alert period.",
                negative,
            )
        )
    if divergence := anomalies.get("PROFIT_CASH_FLOW_DIVERGENCE"):
        rules.append(
            rule(
                "PROFIT_CASHFLOW_DIVERGENCE",
                "Profit and operating cash flow moved in materially divergent directions.",
                divergence,
            )
        )
    coverage_alert = anomalies.get("LOW_INTEREST_COVERAGE_ALERT") or anomalies.get(
        "DECLINING_INTEREST_COVERAGE"
    )
    if coverage_alert:
        rules.append(
            rule(
                coverage_alert.name,
                "Interest coverage triggered the applicable level or deterioration alert.",
                coverage_alert,
            )
        )
    if deterioration := anomalies.get("DEBT_TO_EBITDA_DETERIORATION"):
        rules.append(
            rule(
                "DEBT_TO_EBITDA_DETERIORATION",
                "Debt to EBITDA deteriorated across comparable periods.",
                deterioration,
            )
        )
    return finish_component(
        CreditComponent.REPAYMENT_CAPACITY,
        rules,
        Decimal(len(used)) / Decimal(4),
        [item.confidence for item in used],
        conflict=features.critical_conflict,
    )
