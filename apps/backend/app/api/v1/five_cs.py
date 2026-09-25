from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.database.session import get_db
from app.models.document import Document
from app.models.enums import FinancialScope
from app.models.five_cs import FiveCsAssessment, FiveCsEvidence, FiveCsReviewItem, FiveCsSection
from app.services.five_cs.policy import POLICY_VERSION, validate_section
from app.services.five_cs.refresh import FiveCsResearchRefreshService
from app.services.five_cs.service import (
    FiveCsAssessmentService,
    assessment_payload,
    latest_document_assessments,
)

router = APIRouter(tags=["5 Cs of Credit"])


class ResearchRefreshRequest(BaseModel):
    research_run_id: UUID


def _record_failure(
    session: Session, document_id: UUID, scope: FinancialScope | None, code: str
) -> None:
    try:
        session.rollback()
        document = session.get(Document, document_id)
        write_audit_log(
            session,
            entity_type="five_cs_analysis_attempt",
            entity_id=document_id,
            action="FIVE_CS_ANALYSIS_FAILED",
            event_type="FIVE_CS_ANALYSIS_FAILED",
            company_id=document.company_id if document else None,
            analysis_job_id=document.analysis_job_id if document else None,
            metadata_json={
                "scope": scope.value if scope else None,
                "error_code": code,
                "policy_version": POLICY_VERSION,
            },
        )
        session.commit()
    except Exception:
        session.rollback()


def _record_refresh_failure(session: Session, assessment_id: UUID, code: str) -> None:
    try:
        session.rollback()
        assessment = session.get(FiveCsAssessment, assessment_id)
        write_audit_log(
            session,
            entity_type="five_cs_refresh_attempt",
            entity_id=assessment_id,
            action="FIVE_CS_RESEARCH_REFRESH_FAILED",
            event_type="FIVE_CS_RESEARCH_REFRESH_FAILED",
            company_id=assessment.company_id if assessment else None,
            analysis_job_id=assessment.analysis_job_id if assessment else None,
            metadata_json={"error_code": code},
        )
        session.commit()
    except Exception:
        session.rollback()


def _assessment(session: Session, assessment_id: UUID) -> FiveCsAssessment:
    row = session.get(FiveCsAssessment, assessment_id)
    if row is None:
        raise AppError("FIVE_CS_ASSESSMENT_NOT_FOUND", "5 Cs assessment not found", 404)
    return row


def _source_url(row: FiveCsEvidence, document_id: UUID) -> str | None:
    if row.document_page_id and row.page_number:
        return f"/api/v1/documents/{document_id}/pages/{row.page_number}"
    if not row.source_reference_id:
        return None
    templates = {
        "FINANCIAL_RATIO": "/api/v1/financial-ratios/{}",
        "FINANCIAL_TREND": "/api/v1/financial-trends/{}",
        "FINANCIAL_ANOMALY": "/api/v1/financial-anomalies/{}",
        "CREDIT_ASSESSMENT": "/api/v1/credit-assessments/{}",
        "DOMAIN_CLASSIFICATION": "/api/v1/domain-classifications/{}/evidence",
        "RESEARCH_FINDING": "/api/v1/research-findings/{}",
        "FINANCIAL_VALUE": f"/api/v1/documents/{document_id}/financial-validation",
        "COMPANY_PROFILE": f"/api/v1/documents/{document_id}/company-profile",
    }
    template = templates.get(row.source_type or "")
    return template.format(row.source_reference_id) if template and "{}" in template else template


@router.post("/documents/{document_id}/five-cs/analyze")
def analyze_five_cs(
    document_id: UUID,
    scope: FinancialScope | None = Query(default=None),
    session: Session = Depends(get_db),
) -> dict[str, object] | list[dict[str, object]]:
    try:
        with session.begin():
            rows = FiveCsAssessmentService(session).analyze(document_id, scope)
        return rows[0] if scope or len(rows) == 1 else rows
    except ValueError as exc:
        code = str(exc)
        _record_failure(session, document_id, scope, code)
        status = 404 if code == "DOCUMENT_NOT_FOUND" else 422
        raise AppError(code, code.replace("_", " ").title(), status) from exc
    except Exception as exc:
        _record_failure(session, document_id, scope, type(exc).__name__)
        raise


@router.get("/documents/{document_id}/five-cs")
def get_document_five_cs(
    document_id: UUID,
    scope: FinancialScope | None = Query(default=None),
    latest: bool = Query(default=True),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if session.get(Document, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    rows = (
        latest_document_assessments(session, document_id)
        if latest
        else list(
            session.scalars(
                select(FiveCsAssessment)
                .where(FiveCsAssessment.document_id == document_id)
                .order_by(FiveCsAssessment.created_at.desc(), FiveCsAssessment.id.desc())
            )
        )
    )
    if scope:
        rows = [row for row in rows if row.statement_scope == scope]
    return [assessment_payload(session, row) for row in rows]


@router.post("/five-cs/{assessment_id}/refresh-with-research")
def refresh_five_cs_with_research(
    assessment_id: UUID,
    body: ResearchRefreshRequest,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        with session.begin():
            return FiveCsResearchRefreshService(session).refresh(
                assessment_id, body.research_run_id
            )
    except ValueError as exc:
        code = str(exc)
        _record_refresh_failure(session, assessment_id, code)
        status = 404 if code.endswith("NOT_FOUND") else 422
        raise AppError(code, code.replace("_", " ").title(), status) from exc
    except Exception as exc:
        _record_refresh_failure(session, assessment_id, type(exc).__name__)
        raise


@router.get("/five-cs/{assessment_id}")
def get_five_cs(assessment_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    return assessment_payload(session, _assessment(session, assessment_id))


@router.get("/five-cs/{assessment_id}/evidence")
def get_five_cs_evidence(
    assessment_id: UUID,
    section: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    assessment = _assessment(session, assessment_id)
    query = (
        select(FiveCsEvidence, FiveCsSection.section)
        .join(FiveCsSection)
        .where(FiveCsSection.five_cs_assessment_id == assessment_id)
    )
    if section:
        try:
            query = query.where(FiveCsSection.section == validate_section(section))
        except ValueError as exc:
            raise AppError(str(exc), "Unknown 5 Cs section", 422) from exc
    rows = session.execute(query.order_by(FiveCsSection.section, FiveCsEvidence.created_at)).all()
    return [
        {
            "evidence_id": row.id,
            "section": section_name,
            "evidence_type": row.evidence_type,
            "observation_code": row.observation_code,
            "title": row.title,
            "description": row.description,
            "impact": row.impact,
            "source_type": row.source_type,
            "source_reference_id": row.source_reference_id,
            "page_number": row.page_number,
            "raw_value": row.raw_value,
            "normalized_value": row.normalized_value,
            "confidence": row.confidence_score,
            "status": row.status,
            "source_url": _source_url(row, assessment.document_id),
        }
        for row, section_name in rows
    ]


@router.get("/five-cs/{assessment_id}/review-items")
def get_five_cs_review_items(
    assessment_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _assessment(session, assessment_id)
    rows = session.scalars(
        select(FiveCsReviewItem)
        .where(FiveCsReviewItem.five_cs_assessment_id == assessment_id)
        .order_by(FiveCsReviewItem.priority.desc(), FiveCsReviewItem.created_at)
    ).all()
    return [
        {
            "review_item_id": row.id,
            "section": row.section,
            "reason_code": row.reason_code,
            "message": row.message,
            "priority": row.priority,
            "status": row.status,
            "evidence_id": row.five_cs_evidence_id,
        }
        for row in rows
    ]
