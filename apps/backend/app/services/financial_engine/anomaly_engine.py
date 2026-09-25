from __future__ import annotations

# ruff: noqa: E501
from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import AnomalySeverity
from app.models.financial_trend import FinancialTrend
from app.services.financial_engine.anomaly_rules import anomaly_rules


@dataclass(frozen=True)
class AnomalyCandidate:
    anomaly_type: str
    category: str
    severity: AnomalySeverity
    title: str
    description: str
    trends: tuple[FinancialTrend, ...]
    persistence_count: int = 1


def _d(value: object | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _last_yoy(trend: FinancialTrend) -> Decimal | None:
    if not trend.series:
        return None
    return _d(trend.series[-1].get("percentage_change"))


def _last_value(trend: FinancialTrend) -> Decimal | None:
    return _d(trend.series[-1].get("value")) if trend.series else None


def detect_anomalies(trends: list[FinancialTrend]) -> list[AnomalyCandidate]:
    percent_keys = {
        "revenue_decline_percent",
        "profit_decline_percent",
        "rapid_debt_growth_percent",
        "debt_revenue_growth_gap_percent",
        "working_capital_growth_gap_percent",
        "cross_metric_growth_gap_percent",
        "ratio_deterioration_percent",
        "asset_growth_percent",
        "weak_revenue_growth_percent",
    }
    thresholds = {
        key: Decimal(str(value)) / (Decimal(100) if key in percent_keys else Decimal(1))
        for key, value in anomaly_rules()["thresholds"].items()
    }
    by_name = {trend.metric_name: trend for trend in trends}
    found: list[AnomalyCandidate] = []

    def add(
        kind: str,
        category: str,
        severity: AnomalySeverity,
        title: str,
        description: str,
        *support: FinancialTrend,
        persistence: int = 1,
    ) -> None:
        found.append(
            AnomalyCandidate(
                kind, category, severity, title, description, tuple(support), persistence
            )
        )

    revenue = by_name.get("revenue") or by_name.get("revenue_from_operations")
    if revenue:
        declines = [
            point
            for point in revenue.series[1:]
            if (_d(point.get("percentage_change")) or Decimal(0))
            <= -thresholds["revenue_decline_percent"]
        ]
        if declines:
            change = _d(declines[-1]["percentage_change"]) or Decimal(0)
            add(
                "REVENUE_DECLINE",
                "PROFITABILITY",
                AnomalySeverity.MEDIUM,
                "Revenue Decline",
                f"Revenue declined {abs(change) * 100:.1f}% in the latest material decline period.",
                revenue,
            )
        consecutive = 0
        for point in revenue.series[1:]:
            current_change = _d(point.get("percentage_change"))
            consecutive = (
                consecutive + 1 if current_change is not None and current_change < 0 else 0
            )
        if consecutive >= 2:
            add(
                "PERSISTENT_REVENUE_DECLINE",
                "PROFITABILITY",
                AnomalySeverity.HIGH,
                "Persistent Revenue Decline",
                f"Revenue declined across {consecutive} consecutive comparable intervals.",
                revenue,
                persistence=consecutive,
            )

    pat = by_name.get("profit_after_tax")
    if pat:
        values = [_d(point.get("value")) for point in pat.series]
        transitions = [
            str(point.get("state_transition"))
            for point in pat.series
            if point.get("state_transition")
        ]
        if "PROFIT_TO_LOSS" in transitions:
            add(
                "PROFIT_TO_LOSS",
                "PROFITABILITY",
                AnomalySeverity.HIGH,
                "Profit to Loss Transition",
                "Profit after tax moved from positive to negative.",
                pat,
            )
        if "LOSS_TO_PROFIT" in transitions:
            add(
                "LOSS_TO_PROFIT",
                "PROFITABILITY",
                AnomalySeverity.INFO,
                "Loss to Profit Transition",
                "Profit after tax moved from negative to non-negative.",
                pat,
            )
        positive_declines = []
        for previous, point in zip(pat.series, pat.series[1:], strict=False):
            previous_value = _d(previous.get("value"))
            current_value = _d(point.get("value"))
            current_change = _d(point.get("percentage_change"))
            if (
                previous_value is not None
                and previous_value > 0
                and current_value is not None
                and current_value > 0
                and current_change is not None
                and current_change <= -thresholds["profit_decline_percent"]
            ):
                positive_declines.append(point)
        if positive_declines:
            add(
                "PROFIT_DECLINE",
                "PROFITABILITY",
                AnomalySeverity.MEDIUM,
                "Profit Decline",
                "Profit after tax declined materially while remaining positive.",
                pat,
            )
        negative_run = 0
        for value in values:
            negative_run = negative_run + 1 if value is not None and value < 0 else 0
        if negative_run >= 2:
            add(
                "PERSISTENT_NET_LOSS",
                "PROFITABILITY",
                AnomalySeverity.HIGH if negative_run >= 3 else AnomalySeverity.MEDIUM,
                "Persistent Net Loss",
                f"Profit after tax was negative for {negative_run} consecutive periods.",
                pat,
                persistence=negative_run,
            )

    for metric, kind, title in (
        ("ebitda_margin", "EBITDA_MARGIN_COMPRESSION", "EBITDA Margin Compression"),
        ("net_profit_margin", "NET_MARGIN_COMPRESSION", "Net Margin Compression"),
    ):
        trend = by_name.get(metric)
        if (
            trend
            and trend.percentage_point_change is not None
            and trend.percentage_point_change <= -thresholds["margin_compression_percentage_points"]
        ):
            add(
                kind,
                "MARGIN",
                AnomalySeverity.MEDIUM,
                title,
                f"{title.removesuffix(' Compression')} declined {abs(trend.percentage_point_change):.1f} percentage points across the analyzed period.",
                trend,
            )

    leverage = by_name.get("debt_to_equity") or by_name.get("debt_to_assets")
    if (
        leverage
        and leverage.trend_direction == "INCREASING"
        and (_last_yoy(leverage) or Decimal(0)) >= thresholds["ratio_deterioration_percent"]
    ):
        add(
            "RISING_LEVERAGE",
            "LEVERAGE",
            AnomalySeverity.MEDIUM,
            "Rising Leverage",
            f"{leverage.metric_name.replace('_', ' ').title()} increased materially across comparable periods.",
            leverage,
            persistence=max(1, leverage.period_count - 1),
        )

    debt = by_name.get("total_debt")
    if debt:
        debt_growth = _last_yoy(debt)
        if debt_growth is not None and debt_growth >= thresholds["rapid_debt_growth_percent"]:
            add(
                "RAPID_DEBT_INCREASE",
                "LEVERAGE",
                AnomalySeverity.MEDIUM,
                "Rapid Debt Increase",
                f"Total debt increased {debt_growth * 100:.1f}% in the latest comparable interval.",
                debt,
            )
        revenue_growth = _last_yoy(revenue) if revenue else None
        if (
            debt_growth is not None
            and revenue_growth is not None
            and revenue is not None
            and debt_growth - revenue_growth >= thresholds["debt_revenue_growth_gap_percent"]
        ):
            add(
                "DEBT_GROWTH_OUTPACING_REVENUE",
                "LEVERAGE",
                AnomalySeverity.MEDIUM,
                "Debt Growth Outpacing Revenue",
                f"Debt growth exceeded revenue growth by {(debt_growth - revenue_growth) * 100:.1f} percentage points.",
                debt,
                revenue,
            )

    coverage = by_name.get("interest_coverage")
    if coverage:
        if (
            coverage.trend_direction == "DECREASING"
            and (_last_yoy(coverage) or Decimal(0)) <= -thresholds["ratio_deterioration_percent"]
        ):
            add(
                "DECLINING_INTEREST_COVERAGE",
                "COVERAGE",
                AnomalySeverity.MEDIUM,
                "Declining Interest Coverage",
                "Interest coverage declined materially across comparable periods.",
                coverage,
            )
        current = _last_value(coverage)
        if current is not None and current < Decimal(
            str(anomaly_rules()["thresholds"]["interest_coverage_alert"])
        ):
            add(
                "LOW_INTEREST_COVERAGE_ALERT",
                "COVERAGE",
                AnomalySeverity.HIGH,
                "Low Interest Coverage Alert",
                f"Interest coverage of {current:.2f}x is below the configured operational alert level.",
                coverage,
            )

    current_ratio, quick_ratio = by_name.get("current_ratio"), by_name.get("quick_ratio")
    falling_liquidity = [
        trend
        for trend in (current_ratio, quick_ratio)
        if trend and trend.trend_direction == "DECREASING"
    ]
    if falling_liquidity:
        add(
            "LIQUIDITY_DETERIORATION",
            "LIQUIDITY",
            AnomalySeverity.MEDIUM,
            "Liquidity Deterioration",
            "Available liquidity ratios declined across comparable periods.",
            *falling_liquidity,
        )
    if (
        current_ratio
        and (current := _last_value(current_ratio)) is not None
        and current < Decimal(str(anomaly_rules()["thresholds"]["current_ratio_alert"]))
    ):
        add(
            "CURRENT_RATIO_ALERT",
            "LIQUIDITY",
            AnomalySeverity.MEDIUM,
            "Current Ratio Alert",
            f"Current ratio of {current:.2f}x is below the configured operational alert level.",
            current_ratio,
        )

    ocf = by_name.get("cash_flow_from_operations")
    if ocf:
        negative_count = 0
        for point in ocf.series:
            value = _d(point.get("value"))
            negative_count = negative_count + 1 if value is not None and value < 0 else 0
        if negative_count:
            add(
                "NEGATIVE_OPERATING_CASH_FLOW",
                "CASH_FLOW",
                AnomalySeverity.MEDIUM,
                "Negative Operating Cash Flow",
                "Operating cash flow was negative in the latest negative period.",
                ocf,
            )
        if negative_count >= 2:
            add(
                "PERSISTENT_NEGATIVE_OPERATING_CASH_FLOW",
                "CASH_FLOW",
                AnomalySeverity.HIGH,
                "Persistent Negative Operating Cash Flow",
                f"Operating cash flow was negative for {negative_count} consecutive periods.",
                ocf,
                persistence=negative_count,
            )

    if pat and ocf:
        pat_value, ocf_value = _last_value(pat), _last_value(ocf)
        pat_growth, ocf_growth = _last_yoy(pat), _last_yoy(ocf)
        divergence = (
            pat_value is not None and pat_value > 0 and ocf_value is not None and ocf_value <= 0
        )
        divergence = divergence or (
            pat_growth is not None
            and pat_growth > 0
            and ocf_growth is not None
            and pat_growth - ocf_growth >= thresholds["cross_metric_growth_gap_percent"]
            and ocf_growth < 0
        )
        if divergence:
            add(
                "PROFIT_CASH_FLOW_DIVERGENCE",
                "CASH_FLOW",
                AnomalySeverity.HIGH,
                "Profit and Cash Flow Divergence",
                "Profit after tax and operating cash flow moved in materially divergent directions.",
                pat,
                ocf,
            )

    for metric, kind, title in (
        ("trade_receivables", "RECEIVABLES_OUTPACING_REVENUE", "Receivables Outpacing Revenue"),
        ("inventory", "INVENTORY_OUTPACING_REVENUE", "Inventory Outpacing Revenue"),
    ):
        trend = by_name.get(metric)
        metric_growth, revenue_growth = (
            _last_yoy(trend) if trend else None,
            _last_yoy(revenue) if revenue else None,
        )
        if (
            trend is not None
            and metric_growth is not None
            and revenue_growth is not None
            and revenue is not None
            and metric_growth - revenue_growth >= thresholds["working_capital_growth_gap_percent"]
        ):
            label = metric.replace("_", " ").title()
            add(
                kind,
                "WORKING_CAPITAL",
                AnomalySeverity.MEDIUM,
                title,
                f"{label} grew materially faster than revenue and may warrant working-capital review.",
                trend,
                revenue,
            )

    assets = by_name.get("total_assets")
    if assets and revenue:
        asset_growth, revenue_growth = _last_yoy(assets), _last_yoy(revenue)
        if (
            asset_growth is not None
            and revenue_growth is not None
            and asset_growth >= thresholds["asset_growth_percent"]
            and revenue_growth <= thresholds["weak_revenue_growth_percent"]
        ):
            add(
                "ASSET_GROWTH_WITH_WEAK_REVENUE",
                "EFFICIENCY",
                AnomalySeverity.LOW,
                "Asset Growth with Weak Revenue",
                "Total assets grew materially while revenue was flat or declining.",
                assets,
                revenue,
            )

    for metric, kind, title in (
        ("return_on_equity", "DECLINING_ROE", "Declining Return on Equity"),
        ("return_on_assets", "DECLINING_ROA", "Declining Return on Assets"),
        ("debt_to_ebitda", "DEBT_TO_EBITDA_DETERIORATION", "Debt to EBITDA Deterioration"),
    ):
        trend = by_name.get(metric)
        if trend and trend.trend_direction == "DECREASING" and metric != "debt_to_ebitda":
            add(
                kind,
                "PROFITABILITY",
                AnomalySeverity.MEDIUM,
                title,
                f"{title.removeprefix('Declining ')} declined materially across comparable periods.",
                trend,
            )
        if trend and metric == "debt_to_ebitda" and trend.trend_direction == "INCREASING":
            add(
                kind,
                "LEVERAGE",
                AnomalySeverity.MEDIUM,
                title,
                "Debt to EBITDA increased materially across comparable periods.",
                trend,
            )
    return found
