from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.document import Document
from app.models.financial import FinancialLineItem, FinancialStatement
from app.services.financial_engine.service import extract_financial_statements, latest_run

router = APIRouter(tags=["financial statements"])


@router.post("/documents/{document_id}/financial-statements/extract")
def extract_document_financials(document_id: UUID, session: Session = Depends(get_db)) -> dict:
    return extract_financial_statements(session, document_id)


@router.get("/documents/{document_id}/financial-statements")
def list_statements(document_id: UUID, session: Session = Depends(get_db)) -> list[dict]:
    if session.get(Document, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    run = latest_run(session, document_id)
    if run is None:
        return []
    rows = session.scalars(
        select(FinancialStatement)
        .where(FinancialStatement.run_id == run.id)
        .order_by(FinancialStatement.start_page_number, FinancialStatement.fiscal_year.desc())
    ).all()
    return [
        {
            "id": row.id,
            "statement_type": row.statement_type,
            "statement_scope": row.statement_scope,
            "fiscal_year": row.fiscal_year,
            "period_end": row.period_end,
            "currency": row.currency,
            "normalized_unit": row.normalized_unit,
            "status": row.status,
            "confidence_score": row.confidence_score,
            "start_page_number": row.start_page_number,
            "end_page_number": row.end_page_number,
        }
        for row in rows
    ]


def _item(row: FinancialLineItem) -> dict:
    return {
        "id": row.id,
        "financial_statement_id": row.financial_statement_id,
        "canonical_name": row.canonical_name,
        "raw_label": row.raw_label,
        "measurement_type": row.measurement_type,
        "raw_value": row.raw_value,
        "numeric_value": row.numeric_value,
        "raw_column_header": row.raw_column_header,
        "fiscal_year": row.fiscal_year,
        "period_end": row.period_end,
        "currency": row.currency,
        "normalized_unit": row.normalized_unit,
        "unit_multiplier": row.unit_multiplier,
        "status": row.status,
        "confidence_score": row.confidence_score,
        "page_number": row.page_number,
        "document_page_id": row.document_page_id,
        "evidence_text": row.evidence_text,
        "source_priority": row.source_priority,
    }


@router.get("/financial-statements/{statement_id}/line-items")
def list_line_items(statement_id: UUID, session: Session = Depends(get_db)) -> list[dict]:
    if session.get(FinancialStatement, statement_id) is None:
        raise AppError("FINANCIAL_STATEMENT_NOT_FOUND", "Financial statement not found", 404)
    rows = session.scalars(
        select(FinancialLineItem)
        .where(FinancialLineItem.financial_statement_id == statement_id)
        .order_by(FinancialLineItem.page_number, FinancialLineItem.id)
    ).all()
    return [_item(row) for row in rows]


@router.get("/financial-line-items/{line_item_id}")
def get_line_item(line_item_id: UUID, session: Session = Depends(get_db)) -> dict:
    item = session.get(FinancialLineItem, line_item_id)
    if item is None:
        raise AppError("FINANCIAL_LINE_ITEM_NOT_FOUND", "Financial line item not found", 404)
    statement = session.get(FinancialStatement, item.financial_statement_id)
    assert statement is not None
    return {
        **_item(item),
        "document_id": item.document_id,
        "statement_type": statement.statement_type,
        "statement_scope": statement.statement_scope,
        "extractor_version": item.extractor_version,
        "taxonomy_version": item.taxonomy_version,
    }
