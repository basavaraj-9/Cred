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


def score_financial_strength(features: CreditFeatures) -> ComponentResult:
    rules: list[RuleResult] = []
    used: list[MetricFeature] = []
    thresholds = credit_policy()["thresholds"]

    def eligible(name: str) -> MetricFeature | None:
        item = features.ratios.get(name)
        if (
            item
            and item.value is not None
            and item.status not in {"UNAVAILABLE", "NOT_MEANINGFUL", "CONFLICTING"}
        ):
            used.append(item)
            return item
        return None

    if item := eligible("current_ratio"):
        assert item.value is not None
        limit = thresholds["current_ratio"]
        code = (
            "STRONG_CURRENT_RATIO"
            if item.value >= Decimal(str(limit["strong_min"]))
            else "MODERATE_CURRENT_RATIO"
            if item.value >= Decimal(str(limit["moderate_min"]))
            else "LOW_CURRENT_RATIO"
        )
        rules.append(
            rule(code, f"Current ratio is {item.value:.2f}x under the development policy.", item)
        )
    if item := eligible("quick_ratio"):
        assert item.value is not None
        limit = thresholds["quick_ratio"]
        code = (
            "STRONG_QUICK_RATIO"
            if item.value >= Decimal(str(limit["strong_min"]))
            else "MODERATE_QUICK_RATIO"
            if item.value >= Decimal(str(limit["moderate_min"]))
            else "LOW_QUICK_RATIO"
        )
        rules.append(
            rule(code, f"Quick ratio is {item.value:.2f}x under the development policy.", item)
        )
    if item := eligible("debt_to_equity"):
        assert item.value is not None
        limit = thresholds["debt_to_equity"]
        code = (
            "LOW_LEVERAGE"
            if item.value <= Decimal(str(limit["strong_max"]))
            else "MODERATE_LEVERAGE"
            if item.value <= Decimal(str(limit["moderate_positive_max"]))
            else "HIGH_LEVERAGE"
            if item.value > Decimal(str(limit["moderate_max"]))
            else "NEUTRAL_LEVERAGE"
        )
        rules.append(
            rule(code, f"Debt to equity is {item.value:.2f}x under the development policy.", item)
        )
    if item := eligible("debt_to_assets"):
        assert item.value is not None
        limit = thresholds["debt_to_assets"]
        if item.value <= Decimal(str(limit["strong_max"])):
            rules.append(
                rule("LOW_DEBT_ASSET_SHARE", f"Debt to assets is {item.value:.2f}x.", item)
            )
        elif item.value > Decimal(str(limit["moderate_max"])):
            rules.append(
                rule("HIGH_DEBT_ASSET_SHARE", f"Debt to assets is {item.value:.2f}x.", item)
            )
    for name, positive, negative, label in (
        ("ebitda_margin", "POSITIVE_EBITDA_MARGIN", "NEGATIVE_EBITDA_MARGIN", "EBITDA margin"),
        ("net_profit_margin", "POSITIVE_NET_MARGIN", "NEGATIVE_NET_MARGIN", "Net profit margin"),
        ("return_on_assets", "POSITIVE_ROA", "NEGATIVE_ROA", "Return on assets"),
        ("return_on_equity", "POSITIVE_ROE", "NEGATIVE_ROE", "Return on equity"),
    ):
        if item := eligible(name):
            assert item.value is not None
            rules.append(
                rule(
                    positive if item.value > 0 else negative,
                    f"{label} is {'positive' if item.value > 0 else 'negative'}.",
                    item,
                )
            )
    equity = features.values.get("total_equity")
    equity_value = equity.value if equity else None
    if equity and equity_value is not None and equity_value < 0:
        rules.append(
            rule(
                "NEGATIVE_EQUITY",
                "Total equity is negative; return-on-equity signals are not treated as strength.",
                equity,
            )
        )
    anomalies = suppress_overlaps(features.anomalies)
    compression = anomalies.get("EBITDA_MARGIN_COMPRESSION") or anomalies.get(
        "NET_MARGIN_COMPRESSION"
    )
    if compression:
        rules.append(
            rule(
                "MARGIN_COMPRESSION",
                "A verified margin-compression alert reduces financial strength.",
                compression,
            )
        )
    if rising := anomalies.get("RISING_LEVERAGE"):
        rules.append(
            rule(
                "RISING_LEVERAGE",
                "Leverage increased materially across comparable periods.",
                rising,
            )
        )
    return finish_component(
        CreditComponent.FINANCIAL_STRENGTH,
        rules,
        Decimal(len(used)) / Decimal(8),
        [item.confidence for item in used],
        conflict=features.critical_conflict,
    )
