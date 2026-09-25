from uuid import UUID

# ruff: noqa: E501
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.document import Document
from app.models.enums import FinancialScope
from app.models.financial import FinancialLineItem
from app.models.financial_analysis import (
    FinancialRatio,
    FinancialRatioInput,
    FinancialValidationIssue,
    NormalizedFinancialValue,
)
from app.services.financial_engine.analysis_service import (
    latest_analysis_run,
    run_financial_analysis,
)

router = APIRouter(tags=["financial analysis"])


@router.post("/documents/{document_id}/financial-analysis")
def analyze(
    document_id: UUID, request: Request, session: Session = Depends(get_db)
) -> dict[str, object]:
    return run_financial_analysis(
        session,
        document_id,
        request.app.state.settings.accounting_reconciliation_tolerance_percent,
        request.app.state.settings.debt_reconciliation_tolerance_percent,
        request.app.state.settings.cash_reconciliation_tolerance_percent,
    )


@router.get("/documents/{document_id}/financial-validation")
def validation(document_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    if session.get(Document, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    run = latest_analysis_run(session, document_id)
    if run is None:
        raise AppError("FINANCIAL_ANALYSIS_NOT_FOUND", "Run financial analysis first", 404)
    issues = session.scalars(
        select(FinancialValidationIssue)
        .where(FinancialValidationIssue.run_id == run.id)
        .order_by(FinancialValidationIssue.fiscal_year.desc(), FinancialValidationIssue.issue_type)
    ).all()
    values = session.scalars(
        select(NormalizedFinancialValue)
        .where(NormalizedFinancialValue.run_id == run.id)
        .order_by(
            NormalizedFinancialValue.statement_scope,
            NormalizedFinancialValue.fiscal_year.desc(),
            NormalizedFinancialValue.canonical_name,
        )
    ).all()

    def normalized_payload(value: NormalizedFinancialValue) -> dict[str, object]:
        source = (
            session.get(FinancialLineItem, value.financial_line_item_id)
            if value.financial_line_item_id
            else None
        )
        return {
            "id": value.id,
            "canonical_name": value.canonical_name,
            "statement_scope": value.statement_scope,
            "fiscal_year": value.fiscal_year,
            "raw_numeric_value": value.raw_numeric_value,
            "normalized_value": value.normalized_value,
            "currency": value.normalized_currency,
            "canonical_unit": value.canonical_unit,
            "status": value.normalization_status,
            "confidence_score": value.normalization_confidence,
            "origin": value.value_origin,
            "formula": value.formula,
            "input_value_ids": value.input_value_ids,
            "financial_line_item_id": value.financial_line_item_id,
            "source": (
                {
                    "page_number": source.page_number,
                    "raw_label": source.raw_label,
                    "raw_value": source.raw_value,
                    "raw_unit": source.raw_unit,
                    "evidence_text": source.evidence_text,
                }
                if source
                else None
            ),
        }

    return {
        "document_id": document_id,
        "status": run.status,
        "completeness_score": run.completeness_score,
        "validator_version": run.validator_version,
        "normalized_values": [normalized_payload(value) for value in values],
        "issues": [
            {
                "id": issue.id,
                "statement_scope": issue.statement_scope,
                "fiscal_year": issue.fiscal_year,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "message": issue.message,
                "status": issue.status,
                "expected_value": issue.expected_value,
                "actual_value": issue.actual_value,
                "difference": issue.difference,
                "tolerance": issue.tolerance,
                "related_value_ids": issue.related_value_ids,
            }
            for issue in issues
        ],
    }


@router.get("/documents/{document_id}/financial-ratios")
def ratios(
    document_id: UUID,
    scope: FinancialScope | None = Query(default=None),
    fiscal_year: str | None = Query(default=None, max_length=20),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    run = latest_analysis_run(session, document_id)
    if run is None:
        if session.get(Document, document_id) is None:
            raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
        raise AppError("FINANCIAL_ANALYSIS_NOT_FOUND", "Run financial analysis first", 404)
    statement = select(FinancialRatio).where(FinancialRatio.run_id == run.id)
    if scope:
        statement = statement.where(FinancialRatio.statement_scope == scope)
    if fiscal_year:
        statement = statement.where(FinancialRatio.fiscal_year == fiscal_year)
    rows = session.scalars(
        statement.order_by(
            FinancialRatio.fiscal_year.desc(),
            FinancialRatio.ratio_category,
            FinancialRatio.ratio_name,
        )
    ).all()
    return [_ratio(row) for row in rows]


def _ratio(row: FinancialRatio) -> dict[str, object]:
    return {
        "id": row.id,
        "statement_scope": row.statement_scope,
        "fiscal_year": row.fiscal_year,
        "ratio_name": row.ratio_name,
        "ratio_category": row.ratio_category,
        "ratio_value": row.ratio_value,
        "ratio_unit": row.ratio_unit,
        "status": row.status,
        "confidence_score": row.confidence_score,
        "calculation_basis": row.calculation_basis,
        "formula": row.formula,
        "ratio_taxonomy_version": row.ratio_taxonomy_version,
        "calculator_version": row.calculator_version,
    }


@router.get("/financial-ratios/{ratio_id}")
def ratio_detail(ratio_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    ratio = session.get(FinancialRatio, ratio_id)
    if ratio is None:
        raise AppError("FINANCIAL_RATIO_NOT_FOUND", "Financial ratio not found", 404)
    links = session.execute(
        select(FinancialRatioInput, NormalizedFinancialValue)
        .join(
            NormalizedFinancialValue,
            FinancialRatioInput.normalized_financial_value_id == NormalizedFinancialValue.id,
        )
        .where(FinancialRatioInput.financial_ratio_id == ratio_id)
        .order_by(FinancialRatioInput.input_role)
    ).all()
    inputs = []
    for link, value in links:
        source = (
            session.get(FinancialLineItem, value.financial_line_item_id)
            if value.financial_line_item_id
            else None
        )
        derived_sources = []
        for value_id in value.input_value_ids or []:
            derived_value = session.get(NormalizedFinancialValue, UUID(value_id))
            if derived_value and derived_value.financial_line_item_id:
                derived_source = session.get(
                    FinancialLineItem, derived_value.financial_line_item_id
                )
                if derived_source:
                    derived_sources.append(
                        {
                            "canonical_name": derived_value.canonical_name,
                            "page_number": derived_source.page_number,
                            "raw_label": derived_source.raw_label,
                            "raw_value": derived_source.raw_value,
                            "evidence_text": derived_source.evidence_text,
                        }
                    )
        inputs.append(
            {
                "input_role": link.input_role,
                "normalized_value_id": value.id,
                "canonical_name": value.canonical_name,
                "normalized_value": value.normalized_value,
                "currency": value.normalized_currency,
                "origin": value.value_origin,
                "confidence_score": value.normalization_confidence,
                "formula": value.formula,
                "source": (
                    {
                        "financial_line_item_id": source.id,
                        "page_number": source.page_number,
                        "raw_label": source.raw_label,
                        "raw_value": source.raw_value,
                        "evidence_text": source.evidence_text,
                    }
                    if source
                    else None
                ),
                "derived_sources": derived_sources,
            }
        )
    return {**_ratio(ratio), "inputs": inputs}
