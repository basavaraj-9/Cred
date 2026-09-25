from __future__ import annotations

# ruff: noqa: E501
import hashlib
import logging
from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.document import Document
from app.models.enums import (
    AnalysisStage,
    AnomalyStatus,
    ChangeType,
    NormalizationStatus,
    RatioStatus,
    TrendMetricSourceType,
    TrendStatus,
    ValueOrigin,
)
from app.models.financial_analysis import (
    FinancialAnalysisRun,
    FinancialRatio,
    NormalizedFinancialValue,
)
from app.models.financial_trend import (
    FinancialAnomaly,
    FinancialAnomalyInput,
    FinancialTrend,
    FinancialTrendInput,
    FinancialTrendRun,
)
from app.services.financial_engine.anomaly_engine import detect_anomalies
from app.services.financial_engine.anomaly_rules import ANOMALY_RULE_VERSION
from app.services.financial_engine.cagr import calculate_cagr
from app.services.financial_engine.growth import calculate_change, percentage_point_change
from app.services.financial_engine.trend_classifier import classify
from app.services.financial_engine.trend_series import (
    SeriesPoint,
    chronological,
    missing_years,
    period_year,
)

TREND_CALCULATOR_VERSION = "financial_trend_calculator_v1"
NORMALIZED_METRICS = {
    "revenue",
    "revenue_from_operations",
    "ebitda",
    "ebit",
    "profit_after_tax",
    "cash_flow_from_operations",
    "total_assets",
    "total_equity",
    "total_debt",
    "trade_receivables",
    "inventory",
    "current_assets",
    "current_liabilities",
}
RATIO_METRICS = {
    "current_ratio",
    "quick_ratio",
    "debt_to_equity",
    "debt_to_assets",
    "interest_coverage",
    "debt_to_ebitda",
    "ebitda_margin",
    "ebit_margin",
    "net_profit_margin",
    "return_on_assets",
    "return_on_equity",
    "operating_cash_flow_to_debt",
    "asset_turnover",
}
MARGIN_METRICS = {
    "ebitda_margin",
    "ebit_margin",
    "net_profit_margin",
    "return_on_assets",
    "return_on_equity",
}
logger = logging.getLogger(__name__)


def _quantize(value: Decimal | None) -> Decimal | None:
    return (
        value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if value is not None else None
    )


def _latest_day8_run(session: Session, document_id: UUID) -> FinancialAnalysisRun:
    run = session.scalar(
        select(FinancialAnalysisRun)
        .where(FinancialAnalysisRun.document_id == document_id)
        .order_by(FinancialAnalysisRun.created_at.desc())
    )
    if run is None:
        raise AppError(
            "FINANCIAL_ANALYSIS_REQUIRED", "Run Day 8 financial analysis before trend analysis", 409
        )
    return run


def _load_inputs(
    session: Session, run: FinancialAnalysisRun
) -> tuple[list[NormalizedFinancialValue], list[FinancialRatio]]:
    values = list(
        session.scalars(
            select(NormalizedFinancialValue).where(
                NormalizedFinancialValue.run_id == run.id,
                NormalizedFinancialValue.canonical_name.in_(NORMALIZED_METRICS),
            )
        ).all()
    )
    ratios = list(
        session.scalars(
            select(FinancialRatio).where(
                FinancialRatio.run_id == run.id, FinancialRatio.ratio_name.in_(RATIO_METRICS)
            )
        ).all()
    )
    return values, ratios


def _input_hash(
    run: FinancialAnalysisRun, values: list[NormalizedFinancialValue], ratios: list[FinancialRatio]
) -> str:
    digest = hashlib.sha256(
        f"{run.id}|{TREND_CALCULATOR_VERSION}|{ANOMALY_RULE_VERSION}\n".encode()
    )
    records = [
        f"V|{row.id}|{row.normalized_value}|{row.normalization_status}|{row.normalization_confidence}|{row.normalized_currency}|{row.value_origin}|{row.fiscal_year}"
        for row in values
    ]
    records += [
        f"R|{row.id}|{row.ratio_value}|{row.status}|{row.confidence_score}|{row.calculation_basis}|{row.formula_version}|{row.fiscal_year}"
        for row in ratios
    ]
    for record in sorted(records):
        digest.update(f"{record}\n".encode())
    return digest.hexdigest()


def _series_groups(
    values: list[NormalizedFinancialValue], ratios: list[FinancialRatio]
) -> dict[tuple[Any, TrendMetricSourceType, str, str], list[SeriesPoint]]:
    groups: dict[tuple[Any, TrendMetricSourceType, str, str], list[SeriesPoint]] = defaultdict(list)
    for value_row in values:
        if value_row.normalized_value is None or value_row.normalization_status not in {
            NormalizationStatus.NORMALIZED,
            NormalizationStatus.NEEDS_REVIEW,
            NormalizationStatus.CONFLICTING,
        }:
            continue
        try:
            year = period_year(value_row.fiscal_year)
        except ValueError:
            continue
        currency = value_row.normalized_currency or "N/A"
        groups[
            (
                value_row.statement_scope,
                TrendMetricSourceType.NORMALIZED_VALUE,
                value_row.canonical_name,
                currency,
            )
        ].append(
            SeriesPoint(
                value_row.fiscal_year,
                year,
                value_row.normalized_value,
                value_row.normalization_confidence,
                value_row.normalization_status.value,
                value_row,
                currency,
                value_row.value_origin == ValueOrigin.DERIVED,
            )
        )
    for ratio_row in ratios:
        if ratio_row.ratio_value is None or ratio_row.status not in {
            RatioStatus.VERIFIED,
            RatioStatus.NEEDS_REVIEW,
            RatioStatus.CONFLICTING,
        }:
            continue
        try:
            year = period_year(ratio_row.fiscal_year)
        except ValueError:
            continue
        groups[
            (ratio_row.statement_scope, TrendMetricSourceType.RATIO, ratio_row.ratio_name, "N/A")
        ].append(
            SeriesPoint(
                ratio_row.fiscal_year,
                year,
                ratio_row.ratio_value,
                ratio_row.confidence_score,
                ratio_row.status.value,
                ratio_row,
                calculation_basis=ratio_row.calculation_basis,
            )
        )
    return groups


def _build_trend(
    session: Session,
    run: FinancialTrendRun,
    document: Document,
    key: tuple[Any, TrendMetricSourceType, str, str],
    raw_points: list[SeriesPoint],
) -> FinancialTrend:
    scope, source_type, metric_name, currency = key
    points = chronological(raw_points)
    first, last = points[0], points[-1]
    margin = metric_name in MARGIN_METRICS
    payload: list[dict[str, object]] = []
    transition: str | None = None
    for index, point in enumerate(points):
        item: dict[str, object] = {
            "fiscal_year": point.fiscal_year,
            "period_year": point.period_year,
            "value": str(point.value),
            "confidence_score": point.confidence,
            "status": point.status,
        }
        if index:
            previous = points[index - 1]
            change = calculate_change(previous.value, point.value)
            item["absolute_change"] = str(change.absolute)
            item["state_transition"] = change.state_transition
            if point.period_year - previous.period_year == 1:
                item["percentage_change"] = (
                    str(_quantize(change.percent))
                    if change.percent is not None and not margin
                    else None
                )
                item["percentage_point_change"] = (
                    str(_quantize(percentage_point_change(previous.value, point.value)))
                    if margin
                    else None
                )
                item["reason"] = change.reason
            else:
                item.update(
                    {
                        "percentage_change": None,
                        "percentage_point_change": None,
                        "reason": "NON_CONSECUTIVE_PERIODS",
                    }
                )
            transition = change.state_transition or transition
        payload.append(item)
    endpoint = calculate_change(first.value, last.value) if len(points) > 1 else None
    years = last.period_year - first.period_year
    missing = missing_years(points)
    cagr = calculate_cagr(first.value, last.value, years) if len(points) > 1 else None
    direction, strength = classify([point.value for point in points], bool(transition))
    statuses = {point.status for point in points}
    if len(points) == 1:
        status = TrendStatus.INSUFFICIENT_DATA
    elif "CONFLICTING" in statuses:
        status = TrendStatus.CONFLICTING
    elif "NEEDS_REVIEW" in statuses:
        status = TrendStatus.NEEDS_REVIEW
    elif endpoint and endpoint.reason == "ZERO_BASE" and not margin:
        status = TrendStatus.NOT_MEANINGFUL
    else:
        status = TrendStatus.VERIFIED
    confidence = min(point.confidence for point in points)
    confidence -= min(0.20, 0.05 * len(missing))
    if any(point.derived for point in points):
        confidence -= 0.03
    if any(point.calculation_basis == "ENDING_BALANCE" for point in points):
        confidence -= 0.05
    trend = FinancialTrend(
        run_id=run.id,
        analysis_job_id=document.analysis_job_id,
        company_id=document.company_id,
        document_id=document.id,
        statement_scope=scope,
        metric_name=metric_name,
        metric_source_type=source_type,
        currency=currency,
        start_fiscal_year=first.fiscal_year,
        end_fiscal_year=last.fiscal_year,
        period_count=len(points),
        start_value=first.value,
        end_value=last.value,
        absolute_change=endpoint.absolute if endpoint else None,
        percentage_change=None if margin or not endpoint else _quantize(endpoint.percent),
        cagr=_quantize(cagr),
        percentage_point_change=_quantize(percentage_point_change(first.value, last.value))
        if margin and endpoint
        else None,
        change_type=ChangeType.PERCENTAGE_POINT
        if margin
        else ChangeType.STATE_TRANSITION
        if transition
        else ChangeType.MULTIPLE_CHANGE
        if source_type == TrendMetricSourceType.RATIO
        else ChangeType.PERCENT,
        state_transition=transition,
        trend_direction=direction,
        trend_strength=strength,
        status=status,
        confidence_score=max(0, round(confidence, 4)),
        series=payload,
        missing_periods=missing or None,
        calculator_version=TREND_CALCULATOR_VERSION,
    )
    session.add(trend)
    session.flush()
    for index, point in enumerate(points):
        session.add(
            FinancialTrendInput(
                financial_trend_id=trend.id,
                normalized_financial_value_id=point.source.id
                if source_type == TrendMetricSourceType.NORMALIZED_VALUE
                else None,
                financial_ratio_id=point.source.id
                if source_type == TrendMetricSourceType.RATIO
                else None,
                input_role="START"
                if index == 0
                else "END"
                if index == len(points) - 1
                else "INTERMEDIATE",
                fiscal_year=point.fiscal_year,
            )
        )
    return trend


def _summary(session: Session, run: FinancialTrendRun) -> dict[str, object]:
    scopes = list(
        session.scalars(
            select(FinancialTrend.statement_scope).where(FinancialTrend.run_id == run.id).distinct()
        ).all()
    )
    years = sorted(
        {
            year
            for series in session.scalars(
                select(FinancialTrend.series).where(FinancialTrend.run_id == run.id)
            ).all()
            for year in [str(point["fiscal_year"]) for point in series]
        },
        key=period_year,
    )
    verified = (
        session.scalar(
            select(func.count())
            .select_from(FinancialAnomaly)
            .where(
                FinancialAnomaly.run_id == run.id, FinancialAnomaly.status == AnomalyStatus.VERIFIED
            )
        )
        or 0
    )
    return {
        "document_id": run.document_id,
        "run_id": run.id,
        "status": run.status,
        "trend_count": run.trend_count,
        "anomaly_count": run.anomaly_count,
        "verified_anomalies": verified,
        "review_anomalies": run.anomaly_count - verified,
        "scopes": scopes,
        "years": years,
        "trend_calculator_version": run.trend_calculator_version,
        "anomaly_rule_version": run.anomaly_rule_version,
    }


def _run(session: Session, document_id: UUID) -> dict[str, object]:
    with session.begin():
        document = session.get(Document, document_id)
        if document is None:
            raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
        day8 = _latest_day8_run(session, document_id)
        values, ratios = _load_inputs(session, day8)
        fingerprint = _input_hash(day8, values, ratios)
        existing = session.scalar(
            select(FinancialTrendRun).where(
                FinancialTrendRun.document_id == document_id,
                FinancialTrendRun.input_hash == fingerprint,
                FinancialTrendRun.trend_calculator_version == TREND_CALCULATOR_VERSION,
                FinancialTrendRun.anomaly_rule_version == ANOMALY_RULE_VERSION,
            )
        )
        if existing:
            return _summary(session, existing)
        now = datetime.now(UTC)
        run = FinancialTrendRun(
            analysis_job_id=document.analysis_job_id,
            company_id=document.company_id,
            document_id=document.id,
            financial_analysis_run_id=day8.id,
            input_hash=fingerprint,
            trend_calculator_version=TREND_CALCULATOR_VERSION,
            anomaly_rule_version=ANOMALY_RULE_VERSION,
            status="PROCESSING",
            started_at=now,
        )
        session.add(run)
        session.flush()
        write_audit_log(
            session,
            entity_type="document",
            entity_id=document.id,
            action="FINANCIAL_TREND_ANALYSIS_STARTED",
            event_type="FINANCIAL_TREND_ANALYSIS_STARTED",
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            metadata_json={
                "run_id": str(run.id),
                "trend_calculator_version": TREND_CALCULATOR_VERSION,
                "anomaly_rule_version": ANOMALY_RULE_VERSION,
            },
        )
        document.analysis_job.current_stage = AnalysisStage.FINANCIAL_TREND_ANALYSIS
        trends = [
            _build_trend(session, run, document, key, points)
            for key, points in _series_groups(values, ratios).items()
        ]
        run.trend_count = len(trends)
        write_audit_log(
            session,
            entity_type="document",
            entity_id=document.id,
            action="FINANCIAL_TRENDS_CALCULATED",
            event_type="FINANCIAL_TRENDS_CALCULATED",
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            metadata_json={"run_id": str(run.id), "trend_count": len(trends)},
        )
        for scope in {trend.statement_scope for trend in trends}:
            scoped = [
                trend
                for trend in trends
                if trend.statement_scope == scope
                and trend.currency
                in {
                    "N/A",
                    next(
                        (
                            item.currency
                            for item in trends
                            if item.statement_scope == scope
                            and item.metric_name in {"revenue", "revenue_from_operations"}
                        ),
                        "N/A",
                    ),
                }
            ]
            for candidate in detect_anomalies(scoped):
                status = (
                    AnomalyStatus.VERIFIED
                    if all(trend.status == TrendStatus.VERIFIED for trend in candidate.trends)
                    else AnomalyStatus.NEEDS_REVIEW
                )
                anomaly = FinancialAnomaly(
                    run_id=run.id,
                    analysis_job_id=document.analysis_job_id,
                    company_id=document.company_id,
                    document_id=document.id,
                    statement_scope=scope,
                    anomaly_type=candidate.anomaly_type,
                    category=candidate.category,
                    severity=candidate.severity,
                    title=candidate.title,
                    description=candidate.description,
                    start_fiscal_year=min(
                        (trend.start_fiscal_year for trend in candidate.trends), key=period_year
                    ),
                    end_fiscal_year=max(
                        (trend.end_fiscal_year for trend in candidate.trends), key=period_year
                    ),
                    confidence_score=min(trend.confidence_score for trend in candidate.trends),
                    status=status,
                    persistence_count=candidate.persistence_count,
                    rule_version=ANOMALY_RULE_VERSION,
                )
                session.add(anomaly)
                session.flush()
                for trend in candidate.trends:
                    session.add(
                        FinancialAnomalyInput(
                            financial_anomaly_id=anomaly.id,
                            financial_trend_id=trend.id,
                            input_role=trend.metric_name,
                        )
                    )
                write_audit_log(
                    session,
                    entity_type="document",
                    entity_id=document.id,
                    action="FINANCIAL_ANOMALY_DETECTED",
                    event_type="FINANCIAL_ANOMALY_DETECTED",
                    company_id=document.company_id,
                    analysis_job_id=document.analysis_job_id,
                    metadata_json={
                        "run_id": str(run.id),
                        "anomaly_type": anomaly.anomaly_type,
                        "severity": anomaly.severity.value,
                    },
                )
        run.anomaly_count = (
            session.scalar(
                select(func.count())
                .select_from(FinancialAnomaly)
                .where(FinancialAnomaly.run_id == run.id)
            )
            or 0
        )
        run.status = "COMPLETED"
        run.completed_at = datetime.now(UTC)
        write_audit_log(
            session,
            entity_type="document",
            entity_id=document.id,
            action="FINANCIAL_TREND_ANALYSIS_COMPLETED",
            event_type="FINANCIAL_TREND_ANALYSIS_COMPLETED",
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            metadata_json={
                "run_id": str(run.id),
                "trend_count": run.trend_count,
                "anomaly_count": run.anomaly_count,
            },
        )
        logger.info(
            "Financial trend analysis completed: document=%s trends=%s anomalies=%s",
            document_id,
            run.trend_count,
            run.anomaly_count,
        )
        return _summary(session, run)


def run_financial_trend_analysis(session: Session, document_id: UUID) -> dict[str, object]:
    try:
        return _run(session, document_id)
    except AppError:
        raise
    except Exception as exc:
        logger.exception(
            "Financial trend analysis failed: document=%s error=%s", document_id, type(exc).__name__
        )
        session.rollback()
        try:
            with session.begin():
                document = session.get(Document, document_id)
                if document:
                    write_audit_log(
                        session,
                        entity_type="document",
                        entity_id=document.id,
                        action="FINANCIAL_TREND_ANALYSIS_FAILED",
                        event_type="FINANCIAL_TREND_ANALYSIS_FAILED",
                        company_id=document.company_id,
                        analysis_job_id=document.analysis_job_id,
                        metadata_json={"error_type": type(exc).__name__},
                    )
        except Exception:
            session.rollback()
        raise


def latest_trend_run(session: Session, document_id: UUID) -> FinancialTrendRun | None:
    return session.scalar(
        select(FinancialTrendRun)
        .where(FinancialTrendRun.document_id == document_id)
        .order_by(FinancialTrendRun.created_at.desc())
    )
