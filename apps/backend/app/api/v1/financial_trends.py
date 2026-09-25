from __future__ import annotations

# ruff: noqa: E501
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.document import Document
from app.models.enums import AnomalySeverity, AnomalyStatus, FinancialScope
from app.models.financial import FinancialLineItem
from app.models.financial_analysis import (
    FinancialRatio,
    FinancialRatioInput,
    NormalizedFinancialValue,
)
from app.models.financial_trend import (
    FinancialAnomaly,
    FinancialAnomalyInput,
    FinancialTrend,
    FinancialTrendInput,
)
from app.services.financial_engine.trend_series import period_year
from app.services.financial_engine.trend_service import (
    latest_trend_run,
    run_financial_trend_analysis,
)

router = APIRouter(tags=["financial trends"])


def _trend_payload(row: FinancialTrend) -> dict[str, object]:
    return {
        "id": row.id,
        "statement_scope": row.statement_scope,
        "metric_name": row.metric_name,
        "metric_source_type": row.metric_source_type,
        "currency": row.currency,
        "start_fiscal_year": row.start_fiscal_year,
        "end_fiscal_year": row.end_fiscal_year,
        "period_count": row.period_count,
        "start_value": row.start_value,
        "end_value": row.end_value,
        "absolute_change": row.absolute_change,
        "percentage_change": row.percentage_change,
        "cagr": row.cagr,
        "percentage_point_change": row.percentage_point_change,
        "change_type": row.change_type,
        "state_transition": row.state_transition,
        "trend_direction": row.trend_direction,
        "trend_strength": row.trend_strength,
        "status": row.status,
        "confidence_score": row.confidence_score,
        "series": row.series,
        "missing_periods": row.missing_periods,
        "calculator_version": row.calculator_version,
    }


def _anomaly_payload(row: FinancialAnomaly) -> dict[str, object]:
    return {
        "id": row.id,
        "statement_scope": row.statement_scope,
        "anomaly_type": row.anomaly_type,
        "category": row.category,
        "severity": row.severity,
        "title": row.title,
        "description": row.description,
        "start_fiscal_year": row.start_fiscal_year,
        "end_fiscal_year": row.end_fiscal_year,
        "confidence_score": row.confidence_score,
        "status": row.status,
        "persistence_count": row.persistence_count,
        "rule_version": row.rule_version,
    }


def _value_evidence(session: Session, value: NormalizedFinancialValue) -> list[dict[str, object]]:
    values = [value]
    if value.input_value_ids:
        values = list(
            session.scalars(
                select(NormalizedFinancialValue).where(
                    NormalizedFinancialValue.id.in_([UUID(item) for item in value.input_value_ids])
                )
            ).all()
        )
    evidence: list[dict[str, object]] = []
    for source_value in values:
        line = (
            session.get(FinancialLineItem, source_value.financial_line_item_id)
            if source_value.financial_line_item_id
            else None
        )
        evidence.append(
            {
                "normalized_value_id": source_value.id,
                "canonical_name": source_value.canonical_name,
                "fiscal_year": source_value.fiscal_year,
                "value": source_value.normalized_value,
                "currency": source_value.normalized_currency,
                "confidence_score": source_value.normalization_confidence,
                "page_number": line.page_number if line else None,
                "raw_label": line.raw_label if line else None,
                "raw_value": line.raw_value if line else None,
                "evidence_text": line.evidence_text if line else None,
            }
        )
    return evidence


def _trend_detail(session: Session, trend: FinancialTrend) -> dict[str, object]:
    links = session.scalars(
        select(FinancialTrendInput)
        .where(FinancialTrendInput.financial_trend_id == trend.id)
        .order_by(FinancialTrendInput.fiscal_year)
    ).all()
    inputs: list[dict[str, object]] = []
    for link in links:
        if link.normalized_financial_value_id:
            value = session.get(NormalizedFinancialValue, link.normalized_financial_value_id)
            if value:
                inputs.append(
                    {
                        "input_role": link.input_role,
                        "fiscal_year": link.fiscal_year,
                        "source_type": "NORMALIZED_VALUE",
                        "source_id": value.id,
                        "metric_name": value.canonical_name,
                        "evidence": _value_evidence(session, value),
                    }
                )
        elif link.financial_ratio_id:
            ratio = session.get(FinancialRatio, link.financial_ratio_id)
            if ratio:
                ratio_links = session.scalars(
                    select(FinancialRatioInput).where(
                        FinancialRatioInput.financial_ratio_id == ratio.id
                    )
                ).all()
                evidence = [
                    source
                    for ratio_link in ratio_links
                    if (
                        value := session.get(
                            NormalizedFinancialValue,
                            ratio_link.normalized_financial_value_id,
                        )
                    )
                    for source in _value_evidence(session, value)
                ]
                inputs.append(
                    {
                        "input_role": link.input_role,
                        "fiscal_year": link.fiscal_year,
                        "source_type": "RATIO",
                        "source_id": ratio.id,
                        "metric_name": ratio.ratio_name,
                        "evidence": evidence,
                    }
                )
    return {
        **_trend_payload(trend),
        "inputs": inputs,
        "formula": "YoY=(current-previous)/abs(previous); CAGR=(ending/beginning)^(1/years)-1",
    }


@router.post("/documents/{document_id}/financial-trends/analyze")
def analyze_financial_trends(
    document_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    return run_financial_trend_analysis(session, document_id)


@router.get("/documents/{document_id}/financial-trends")
def get_financial_trends(
    document_id: UUID,
    scope: FinancialScope | None = Query(default=None),
    metric: str | None = Query(default=None, max_length=100),
    start_year: str | None = Query(default=None, max_length=20),
    end_year: str | None = Query(default=None, max_length=20),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if session.get(Document, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    run = latest_trend_run(session, document_id)
    if run is None:
        raise AppError("FINANCIAL_TRENDS_NOT_FOUND", "Run financial trend analysis first", 404)
    query = select(FinancialTrend).where(FinancialTrend.run_id == run.id)
    if scope:
        query = query.where(FinancialTrend.statement_scope == scope)
    if metric:
        query = query.where(FinancialTrend.metric_name == metric)
    rows = list(
        session.scalars(
            query.order_by(FinancialTrend.statement_scope, FinancialTrend.metric_name)
        ).all()
    )
    if start_year:
        rows = [row for row in rows if period_year(row.end_fiscal_year) >= period_year(start_year)]
    if end_year:
        rows = [row for row in rows if period_year(row.start_fiscal_year) <= period_year(end_year)]
    return [_trend_payload(row) for row in rows]


@router.get("/financial-trends/{trend_id}")
def get_financial_trend(trend_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    trend = session.get(FinancialTrend, trend_id)
    if trend is None:
        raise AppError("FINANCIAL_TREND_NOT_FOUND", "Financial trend not found", 404)
    return _trend_detail(session, trend)


@router.get("/documents/{document_id}/financial-anomalies")
def get_financial_anomalies(
    document_id: UUID,
    scope: FinancialScope | None = Query(default=None),
    severity: AnomalySeverity | None = Query(default=None),
    category: str | None = Query(default=None, max_length=50),
    status: AnomalyStatus | None = Query(default=None),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if session.get(Document, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    run = latest_trend_run(session, document_id)
    if run is None:
        raise AppError("FINANCIAL_TRENDS_NOT_FOUND", "Run financial trend analysis first", 404)
    query = select(FinancialAnomaly).where(FinancialAnomaly.run_id == run.id)
    if scope:
        query = query.where(FinancialAnomaly.statement_scope == scope)
    if severity:
        query = query.where(FinancialAnomaly.severity == severity)
    if category:
        query = query.where(FinancialAnomaly.category == category)
    if status:
        query = query.where(FinancialAnomaly.status == status)
    return [
        _anomaly_payload(row)
        for row in session.scalars(
            query.order_by(FinancialAnomaly.severity.desc(), FinancialAnomaly.anomaly_type)
        ).all()
    ]


@router.get("/financial-anomalies/{anomaly_id}")
def get_financial_anomaly(
    anomaly_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    anomaly = session.get(FinancialAnomaly, anomaly_id)
    if anomaly is None:
        raise AppError("FINANCIAL_ANOMALY_NOT_FOUND", "Financial anomaly not found", 404)
    links = session.scalars(
        select(FinancialAnomalyInput).where(
            FinancialAnomalyInput.financial_anomaly_id == anomaly.id
        )
    ).all()
    inputs: list[dict[str, object]] = []
    for link in links:
        if link.financial_trend_id and (
            trend := session.get(FinancialTrend, link.financial_trend_id)
        ):
            inputs.append(
                {
                    "input_role": link.input_role,
                    "source_type": "TREND",
                    "source": _trend_detail(session, trend),
                }
            )
        elif link.normalized_financial_value_id and (
            value := session.get(NormalizedFinancialValue, link.normalized_financial_value_id)
        ):
            inputs.append(
                {
                    "input_role": link.input_role,
                    "source_type": "NORMALIZED_VALUE",
                    "source": _value_evidence(session, value),
                }
            )
        elif link.financial_ratio_id and (
            ratio := session.get(FinancialRatio, link.financial_ratio_id)
        ):
            inputs.append(
                {
                    "input_role": link.input_role,
                    "source_type": "RATIO",
                    "source": {
                        "id": ratio.id,
                        "ratio_name": ratio.ratio_name,
                        "fiscal_year": ratio.fiscal_year,
                        "ratio_value": ratio.ratio_value,
                    },
                }
            )
    return {**_anomaly_payload(anomaly), "inputs": inputs}
