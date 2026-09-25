from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.credit import CreditAssessment, CreditAssessmentInput, CreditRuleResult
from app.models.document import Document
from app.models.enums import CreditReasonType, FinancialScope
from app.models.extracted_field import ExtractedField
from app.models.financial import FinancialLineItem
from app.models.financial_analysis import FinancialRatioInput, NormalizedFinancialValue
from app.models.financial_trend import FinancialAnomalyInput, FinancialTrendInput
from app.services.credit_engine.service import (
    assessment_payload,
    latest_credit_assessments,
    run_credit_analysis,
)

router = APIRouter(tags=["credit risk"])


def _assessment(session: Session, assessment_id: UUID) -> CreditAssessment:
    row = session.get(CreditAssessment, assessment_id)
    if row is None:
        raise AppError("CREDIT_ASSESSMENT_NOT_FOUND", "Credit assessment not found", 404)
    return row


@router.post("/documents/{document_id}/credit-risk/analyze")
def analyze_credit_risk(
    document_id: UUID,
    scope: FinancialScope | None = Query(default=None),
    session: Session = Depends(get_db),
) -> dict[str, object] | list[dict[str, object]]:
    rows = run_credit_analysis(session, document_id, scope)
    return rows[0] if scope or len(rows) == 1 else rows


@router.get("/documents/{document_id}/credit-risk")
def get_document_credit_risk(
    document_id: UUID,
    scope: FinancialScope | None = Query(default=None),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if session.get(Document, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    rows = latest_credit_assessments(session, document_id)
    if scope:
        rows = [row for row in rows if row.statement_scope == scope]
    return [assessment_payload(session, row) for row in rows]


@router.get("/credit-assessments/{assessment_id}")
def get_credit_assessment(
    assessment_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    return assessment_payload(session, _assessment(session, assessment_id))


@router.get("/credit-assessments/{assessment_id}/reasons")
def get_credit_reasons(
    assessment_id: UUID,
    reason_type: CreditReasonType | None = Query(default=None),
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, object]]]:
    _assessment(session, assessment_id)
    query = select(CreditRuleResult).where(CreditRuleResult.credit_assessment_id == assessment_id)
    if reason_type:
        query = query.where(CreditRuleResult.reason_type == reason_type)
    rows = session.scalars(
        query.order_by(CreditRuleResult.component, CreditRuleResult.rule_code)
    ).all()
    payload: list[dict[str, object]] = [
        {
            "id": row.id,
            "component": row.component,
            "rule_code": row.rule_code,
            "rule_version": row.rule_version,
            "input_metric": row.input_metric,
            "input_value": row.input_value,
            "input_status": row.input_status,
            "score_impact": row.score_impact,
            "max_score_impact": row.max_score_impact,
            "reason_type": row.reason_type,
            "message": row.message,
            "confidence_score": row.confidence_score,
            "status": row.status,
            "assessment_input_id": row.credit_assessment_input_id,
            "evidence_url": (
                f"/api/v1/credit-assessments/{assessment_id}/evidence"
                if row.credit_assessment_input_id
                else None
            ),
        }
        for row in rows
    ]
    groups: dict[str, list[dict[str, object]]] = {
        "positive": [],
        "negative": [],
        "review": [],
        "neutral": [],
    }
    for item in payload:
        groups[str(item["reason_type"]).lower()].append(item)
    return groups


def _value_evidence(session: Session, value_id: UUID) -> list[dict[str, object]]:
    value = session.get(NormalizedFinancialValue, value_id)
    if value is None:
        return []
    source_ids = [UUID(item) for item in value.input_value_ids or []] or [value.id]
    evidence: list[dict[str, object]] = []
    for source in session.scalars(
        select(NormalizedFinancialValue).where(NormalizedFinancialValue.id.in_(source_ids))
    ).all():
        line = (
            session.get(FinancialLineItem, source.financial_line_item_id)
            if source.financial_line_item_id
            else None
        )
        evidence.append(
            {
                "source_type": "normalized_financial_value",
                "source_id": source.id,
                "metric": source.canonical_name,
                "fiscal_year": source.fiscal_year,
                "value": source.normalized_value,
                "page_number": line.page_number if line else None,
                "evidence_text": line.evidence_text if line else None,
                "raw_label": line.raw_label if line else None,
                "raw_value": line.raw_value if line else None,
            }
        )
    return evidence


def _lineage(session: Session, link: CreditAssessmentInput) -> list[dict[str, object]]:
    if link.normalized_financial_value_id:
        return _value_evidence(session, link.normalized_financial_value_id)
    if link.financial_ratio_id:
        ratio_links = session.scalars(
            select(FinancialRatioInput).where(
                FinancialRatioInput.financial_ratio_id == link.financial_ratio_id
            )
        ).all()
        return [
            item
            for ratio_link in ratio_links
            for item in _value_evidence(session, ratio_link.normalized_financial_value_id)
        ]
    if link.financial_trend_id:
        trend_links = session.scalars(
            select(FinancialTrendInput).where(
                FinancialTrendInput.financial_trend_id == link.financial_trend_id
            )
        ).all()
        result: list[dict[str, object]] = []
        for trend_link in trend_links:
            if trend_link.normalized_financial_value_id:
                result.extend(_value_evidence(session, trend_link.normalized_financial_value_id))
            elif trend_link.financial_ratio_id:
                ratio_links = session.scalars(
                    select(FinancialRatioInput).where(
                        FinancialRatioInput.financial_ratio_id == trend_link.financial_ratio_id
                    )
                ).all()
                result.extend(
                    item
                    for ratio_link in ratio_links
                    for item in _value_evidence(session, ratio_link.normalized_financial_value_id)
                )
        return result
    if link.financial_anomaly_id:
        anomaly_links = session.scalars(
            select(FinancialAnomalyInput).where(
                FinancialAnomalyInput.financial_anomaly_id == link.financial_anomaly_id
            )
        ).all()
        result = []
        for anomaly_link in anomaly_links:
            proxy = CreditAssessmentInput(
                financial_trend_id=anomaly_link.financial_trend_id,
                normalized_financial_value_id=anomaly_link.normalized_financial_value_id,
                financial_ratio_id=anomaly_link.financial_ratio_id,
                credit_assessment_id=link.credit_assessment_id,
                input_role="evidence",
            )
            result.extend(_lineage(session, proxy))
        return result
    profile_id = link.company_profile_id
    if profile_id:
        return [
            {
                "source_type": "company_profile",
                "source_id": field.id,
                "metric": field.field_name,
                "value": field.normalized_value,
                "page_number": field.page_number,
                "evidence_text": field.evidence_text,
            }
            for field in session.scalars(
                select(ExtractedField).where(ExtractedField.company_profile_id == profile_id)
            ).all()
        ]
    if link.domain_classification_id:
        from app.models.domain_classification import DomainClassificationEvidence

        evidence_links = session.scalars(
            select(DomainClassificationEvidence).where(
                DomainClassificationEvidence.domain_classification_id
                == link.domain_classification_id
            )
        ).all()
        return [
            {
                "source_type": "domain_classification",
                "source_id": field.id,
                "metric": field.field_name,
                "value": field.normalized_value,
                "page_number": field.page_number,
                "evidence_text": field.evidence_text,
            }
            for item in evidence_links
            if (field := session.get(ExtractedField, item.extracted_field_id))
        ]
    return []


@router.get("/credit-assessments/{assessment_id}/evidence")
def get_credit_evidence(
    assessment_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _assessment(session, assessment_id)
    links = session.scalars(
        select(CreditAssessmentInput)
        .where(CreditAssessmentInput.credit_assessment_id == assessment_id)
        .order_by(CreditAssessmentInput.input_role)
    ).all()
    return [
        {
            "assessment_input_id": link.id,
            "input_role": link.input_role,
            "evidence": _lineage(session, link),
        }
        for link in links
    ]
