from __future__ import annotations

# ruff: noqa: E501
from decimal import Decimal
from uuid import UUID

from app.models.credit import CreditSubscore
from app.models.financial_analysis import FinancialRatio, NormalizedFinancialValue
from app.models.financial_trend import FinancialTrend
from app.services.five_cs.evidence import draft, unavailable
from app.services.five_cs.schemas import EvidenceDraft


def build_capital(
    ratios: dict[str, FinancialRatio],
    values: dict[str, NormalizedFinancialValue],
    trends: dict[str, FinancialTrend],
    subscore: CreditSubscore | None,
    lineage: dict[UUID, tuple[UUID, int]],
    thresholds: dict[str, float],
) -> list[EvidenceDraft]:
    rows: list[EvidenceDraft] = []
    if subscore:
        rows.append(
            draft(
                "CAPITAL",
                "financial_strength_subscore",
                "CAPITAL_FINANCIAL_STRENGTH_SUBSCORE",
                "Day 10 financial-strength assessment",
                "The persisted Day 10 financial-strength component is linked as supporting context.",
                "NEUTRAL",
                float(subscore.confidence_score),
                subscore.status.value,
                source_type="CREDIT_SUBSCORE",
                source_id=subscore.id,
                normalized_value=str(subscore.normalized_score),
            )
        )
    equity = values.get("total_equity")
    if equity and equity.normalized_value is not None:
        positive = equity.normalized_value > 0
        rows.append(
            draft(
                "CAPITAL",
                "total_equity",
                "CAPITAL_POSITIVE_EQUITY" if positive else "CAPITAL_NEGATIVE_EQUITY",
                "Total equity",
                "Persisted total equity is positive."
                if positive
                else "Persisted total equity is negative and requires review.",
                "POSITIVE" if positive else "NEGATIVE",
                equity.normalization_confidence,
                "VERIFIED" if equity.normalization_status.value == "NORMALIZED" else "NEEDS_REVIEW",
                source_type="FINANCIAL_VALUE",
                source_id=equity.id,
                lineage=lineage.get(equity.id),
                raw_value=str(equity.normalized_value),
                normalized_value=str(equity.normalized_value),
            )
        )
    else:
        rows.append(
            unavailable(
                "CAPITAL",
                "total_equity",
                "CAPITAL_EQUITY_UNAVAILABLE",
                "Total equity unavailable",
                "Verified total-equity evidence is unavailable.",
            )
        )
    for name, key, low_limit, high_limit in (
        ("debt_to_equity", "debt_to_equity", "debt_to_equity_low_max", "debt_to_equity_high_min"),
        ("debt_to_assets", "debt_to_assets", "debt_to_assets_low_max", None),
    ):
        item = ratios.get(name)
        if not item or item.ratio_value is None:
            rows.append(
                unavailable(
                    "CAPITAL",
                    key,
                    f"CAPITAL_{name.upper()}_UNAVAILABLE",
                    name.replace("_", " ").title(),
                    "Persisted leverage ratio is unavailable.",
                )
            )
            continue
        value = Decimal(item.ratio_value)
        positive = value <= Decimal(str(thresholds[low_limit]))
        negative = bool(high_limit and value >= Decimal(str(thresholds[high_limit])))
        rows.append(
            draft(
                "CAPITAL",
                key,
                "CAPITAL_LOW_LEVERAGE"
                if positive
                else "CAPITAL_HIGH_LEVERAGE"
                if negative
                else "CAPITAL_LEVERAGE_AVAILABLE",
                name.replace("_", " ").title(),
                f"Persisted {name.replace('_', ' ')} is {value}x.",
                "POSITIVE" if positive else "NEGATIVE" if negative else "NEUTRAL",
                item.confidence_score,
                item.status.value,
                source_type="FINANCIAL_RATIO",
                source_id=item.id,
                lineage=lineage.get(item.id),
                normalized_value=f"{value}x",
            )
        )
    trend = trends.get("total_equity")
    if trend:
        increasing = trend.trend_direction.value == "INCREASING"
        rows.append(
            draft(
                "CAPITAL",
                "equity_trend",
                "CAPITAL_EQUITY_GROWTH"
                if increasing
                else "CAPITAL_EQUITY_DECLINE"
                if trend.trend_direction.value == "DECREASING"
                else "CAPITAL_EQUITY_TREND_AVAILABLE",
                "Equity trend",
                f"Persisted equity trend is {trend.trend_direction.value.lower()}.",
                "POSITIVE"
                if increasing
                else "NEGATIVE"
                if trend.trend_direction.value == "DECREASING"
                else "NEUTRAL",
                trend.confidence_score,
                trend.status.value,
                source_type="FINANCIAL_TREND",
                source_id=trend.id,
                lineage=lineage.get(trend.id),
                normalized_value=trend.trend_direction.value,
            )
        )
    else:
        rows.append(
            unavailable(
                "CAPITAL",
                "equity_trend",
                "CAPITAL_EQUITY_TREND_UNAVAILABLE",
                "Equity trend unavailable",
                "A persisted multi-period equity trend is unavailable.",
            )
        )
    net_worth = values.get("net_worth")
    rows.append(
        draft(
            "CAPITAL",
            "net_worth",
            "CAPITAL_NET_WORTH_AVAILABLE",
            "Net worth",
            "Persisted net-worth evidence is available.",
            "NEUTRAL",
            net_worth.normalization_confidence,
            "VERIFIED",
            source_type="FINANCIAL_VALUE",
            source_id=net_worth.id,
            lineage=lineage.get(net_worth.id),
            normalized_value=str(net_worth.normalized_value),
        )
        if net_worth and net_worth.normalized_value is not None
        else unavailable(
            "CAPITAL",
            "net_worth",
            "CAPITAL_NET_WORTH_UNAVAILABLE",
            "Net worth unavailable",
            "Net worth was not derived from equity or share capital.",
        )
    )
    return rows
