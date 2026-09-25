from decimal import Decimal

from app.models.enums import CreditComponent
from app.services.credit_engine.overlap import suppress_overlaps
from app.services.credit_engine.rules import finish_component, rule
from app.services.credit_engine.schemas import (
    ComponentResult,
    CreditFeatures,
    RuleResult,
    TrendFeature,
)


def score_business_stability(features: CreditFeatures) -> ComponentResult:
    rules: list[RuleResult] = []
    used: list[TrendFeature] = []

    def eligible(name: str) -> TrendFeature | None:
        item = features.trends.get(name)
        if item and item.status not in {"UNAVAILABLE", "INSUFFICIENT_DATA", "NOT_MEANINGFUL"}:
            used.append(item)
            return item
        return None

    revenue = eligible("revenue") or eligible("revenue_from_operations")
    if revenue:
        code = {
            "INCREASING": "REVENUE_GROWTH_STABLE",
            "STABLE": "REVENUE_STABLE",
            "VOLATILE": "REVENUE_VOLATILE",
            "MIXED": "REVENUE_VOLATILE",
        }.get(revenue.direction)
        if code:
            rules.append(
                rule(
                    code,
                    f"Revenue trend is {revenue.direction.lower()} across comparable periods.",
                    revenue,
                )
            )
    profit = eligible("profit_after_tax")
    if profit and profit.direction == "INCREASING":
        rules.append(
            rule(
                "PROFIT_GROWTH_STABLE",
                "Profit after tax increased across comparable periods.",
                profit,
            )
        )
    eligible("ebitda")

    anomalies = suppress_overlaps(features.anomalies)
    revenue_alert = anomalies.get("PERSISTENT_REVENUE_DECLINE") or anomalies.get("REVENUE_DECLINE")
    if revenue_alert:
        rules.append(
            rule(
                revenue_alert.name,
                "Revenue decline triggered the applicable persistence rule.",
                revenue_alert,
            )
        )
    for name, code, message in (
        ("PROFIT_TO_LOSS", "PROFIT_TO_LOSS", "Profit moved from profit to loss."),
        ("LOSS_TO_PROFIT", "LOSS_TO_PROFIT", "Profit recovered from loss to profit."),
        (
            "PERSISTENT_NET_LOSS",
            "PERSISTENT_NET_LOSS",
            "Net losses persisted across comparable periods.",
        ),
    ):
        if alert := anomalies.get(name):
            rules.append(rule(code, message, alert))
    compression = anomalies.get("EBITDA_MARGIN_COMPRESSION") or anomalies.get(
        "NET_MARGIN_COMPRESSION"
    )
    if compression:
        rules.append(
            rule(
                "STABILITY_MARGIN_COMPRESSION",
                "A verified margin compression alert reduces business stability.",
                compression,
            )
        )
    return finish_component(
        CreditComponent.BUSINESS_STABILITY,
        rules,
        min(Decimal(1), Decimal(len(used)) / Decimal(3)),
        [item.confidence for item in used],
        conflict=any(item.status == "CONFLICTING" for item in used),
    )
