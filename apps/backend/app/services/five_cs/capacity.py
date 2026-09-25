from __future__ import annotations

# ruff: noqa: E501
from decimal import Decimal
from uuid import UUID

from app.models.credit import CreditSubscore
from app.models.financial_analysis import FinancialRatio, NormalizedFinancialValue
from app.models.financial_trend import FinancialAnomaly, FinancialTrend
from app.services.five_cs.evidence import draft, unavailable
from app.services.five_cs.schemas import EvidenceDraft


def build_capacity(
    ratios: dict[str, FinancialRatio],
    values: dict[str, NormalizedFinancialValue],
    trends: dict[str, FinancialTrend],
    anomalies: dict[str, FinancialAnomaly],
    subscore: CreditSubscore | None,
    lineage: dict[UUID, tuple[UUID, int]],
    thresholds: dict[str, float],
) -> list[EvidenceDraft]:
    rows: list[EvidenceDraft] = []
    if subscore:
        rows.append(
            draft(
                "CAPACITY",
                "repayment_subscore",
                "CAPACITY_REPAYMENT_SUBSCORE",
                "Day 10 repayment-capacity assessment",
                "The persisted Day 10 repayment-capacity component is linked as supporting context.",
                "NEUTRAL",
                float(subscore.confidence_score),
                subscore.status.value,
                source_type="CREDIT_SUBSCORE",
                source_id=subscore.id,
                normalized_value=str(subscore.normalized_score),
            )
        )
    else:
        rows.append(
            unavailable(
                "CAPACITY",
                "repayment_subscore",
                "CAPACITY_CRITICAL_INPUT_REVIEW",
                "Repayment-capacity component unavailable",
                "The required Day 10 repayment-capacity component is unavailable.",
            )
        )

    def ratio(name: str, key: str, low_code: str, high_code: str, low_good: bool) -> None:
        item = ratios.get(name)
        if (
            not item
            or item.ratio_value is None
            or item.status.value not in {"VERIFIED", "NEEDS_REVIEW"}
        ):
            rows.append(
                unavailable(
                    "CAPACITY",
                    key,
                    f"CAPACITY_{name.upper()}_UNAVAILABLE",
                    name.replace("_", " ").title(),
                    "Persisted ratio evidence is unavailable.",
                )
            )
            return
        value = Decimal(item.ratio_value)
        if name == "interest_coverage":
            positive = value >= Decimal(str(thresholds["interest_coverage_strong_min"]))
            negative = value <= Decimal(str(thresholds["interest_coverage_low_max"]))
        elif name == "debt_to_ebitda":
            positive = value <= Decimal(str(thresholds["debt_to_ebitda_low_max"]))
            negative = value >= Decimal(str(thresholds["debt_to_ebitda_high_min"]))
        else:
            positive = value > Decimal(str(thresholds["ocf_to_debt_positive_min"]))
            negative = value < 0
        code = (
            low_code
            if positive
            else high_code
            if negative
            else f"CAPACITY_{name.upper()}_AVAILABLE"
        )
        impact = "POSITIVE" if positive else "NEGATIVE" if negative else "NEUTRAL"
        rows.append(
            draft(
                "CAPACITY",
                key,
                code,
                name.replace("_", " ").title(),
                f"Persisted {name.replace('_', ' ')} is {value}x.",
                impact,
                item.confidence_score,
                item.status.value,
                source_type="FINANCIAL_RATIO",
                source_id=item.id,
                lineage=lineage.get(item.id),
                raw_value=str(value),
                normalized_value=f"{value}x",
            )
        )

    ratio(
        "interest_coverage",
        "interest_coverage",
        "CAPACITY_STRONG_INTEREST_COVERAGE",
        "CAPACITY_LOW_INTEREST_COVERAGE",
        False,
    )
    ratio(
        "debt_to_ebitda",
        "debt_to_ebitda",
        "CAPACITY_LOW_DEBT_TO_EBITDA",
        "CAPACITY_HIGH_DEBT_TO_EBITDA",
        True,
    )
    ratio(
        "operating_cash_flow_to_debt",
        "ocf_to_debt",
        "CAPACITY_POSITIVE_OCF_TO_DEBT",
        "CAPACITY_NEGATIVE_OCF_TO_DEBT",
        False,
    )
    cash = values.get("cash_flow_from_operations")
    if (
        cash
        and cash.normalized_value is not None
        and cash.normalization_status.value in {"NORMALIZED", "NEEDS_REVIEW"}
    ):
        positive = cash.normalized_value > 0
        rows.append(
            draft(
                "CAPACITY",
                "cash_flow",
                "CAPACITY_POSITIVE_OPERATING_CASH_FLOW"
                if positive
                else "CAPACITY_NEGATIVE_OPERATING_CASH_FLOW",
                "Operating cash flow",
                "Persisted operating cash flow is positive."
                if positive
                else "Persisted operating cash flow is negative.",
                "POSITIVE" if positive else "NEGATIVE",
                cash.normalization_confidence,
                "VERIFIED" if cash.normalization_status.value == "NORMALIZED" else "NEEDS_REVIEW",
                source_type="FINANCIAL_VALUE",
                source_id=cash.id,
                lineage=lineage.get(cash.id),
                raw_value=str(cash.normalized_value),
                normalized_value=str(cash.normalized_value),
            )
        )
    else:
        rows.append(
            unavailable(
                "CAPACITY",
                "cash_flow",
                "CAPACITY_CASH_FLOW_UNAVAILABLE",
                "Operating cash flow unavailable",
                "Persisted operating cash-flow evidence is unavailable.",
            )
        )
    for code, observation in (
        ("PERSISTENT_NEGATIVE_OPERATING_CASH_FLOW", "CAPACITY_PERSISTENT_NEGATIVE_OCF"),
        ("PROFIT_CASH_FLOW_DIVERGENCE", "CAPACITY_PROFIT_CASHFLOW_DIVERGENCE"),
        ("DECLINING_INTEREST_COVERAGE", "CAPACITY_DECLINING_INTEREST_COVERAGE"),
        ("DEBT_GROWTH_OUTPACES_REVENUE", "CAPACITY_DEBT_GROWTH_HIGH"),
    ):
        if item := anomalies.get(code):
            rows.append(
                draft(
                    "CAPACITY",
                    code.lower(),
                    observation,
                    item.title,
                    item.description,
                    "NEGATIVE",
                    item.confidence_score,
                    item.status.value,
                    source_type="FINANCIAL_ANOMALY",
                    source_id=item.id,
                    lineage=lineage.get(item.id),
                )
            )
    if trend := trends.get("interest_coverage"):
        if trend.trend_direction.value == "DECREASING":
            rows.append(
                draft(
                    "CAPACITY",
                    "interest_coverage_trend",
                    "CAPACITY_DECLINING_INTEREST_COVERAGE",
                    "Declining interest coverage",
                    "Persisted interest-coverage trend is decreasing.",
                    "REVIEW",
                    trend.confidence_score,
                    trend.status.value,
                    source_type="FINANCIAL_TREND",
                    source_id=trend.id,
                    lineage=lineage.get(trend.id),
                    normalized_value=trend.trend_direction.value,
                )
            )
    return rows
