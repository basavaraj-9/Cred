from __future__ import annotations

# ruff: noqa: E501, E701, E702
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.database.session import get_db
from app.models.decision import (
    CreditDecisionGate,
    CreditDecisionReviewItem,
    CreditDecisionSupport,
    CreditLimitMethod,
    CreditLimitPreparation,
    CreditPolicyException,
)
from app.models.document import Document
from app.models.enums import FinancialScope
from app.services.credit_decision.policy import POLICY_VERSION
from app.services.credit_decision.service import (
    CreditDecisionSupportService,
    decision_payload,
    exception_payload,
    gate_payload,
    limit_payload,
    review_payload,
)

router = APIRouter(tags=["credit decision support"])


class DecisionSupportRequest(BaseModel):
    scope: FinancialScope | None = None
    recommendation_preparation_id: UUID | None = None


def _decision(session: Session, row_id: UUID) -> CreditDecisionSupport:
    row = session.get(CreditDecisionSupport, row_id)
    if row is None:
        raise AppError(
            "CREDIT_DECISION_SUPPORT_NOT_FOUND", "Credit decision support record not found", 404
        )
    return row


def _failure(session: Session, document_id: UUID, code: str) -> None:
    try:
        session.rollback()
        document = session.get(Document, document_id)
        if document:
            write_audit_log(
                session,
                entity_type="credit_decision_support_attempt",
                entity_id=document_id,
                action="CREDIT_DECISION_SUPPORT_FAILED",
                event_type="CREDIT_DECISION_SUPPORT_FAILED",
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
                metadata_json={"error_code": code, "policy_version": POLICY_VERSION},
            )
            session.commit()
    except Exception:
        session.rollback()


@router.post("/documents/{document_id}/credit-decision/prepare")
def prepare_credit_decision(
    document_id: UUID, body: DecisionSupportRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        with session.begin():
            return CreditDecisionSupportService(session).prepare(
                document_id,
                scope=body.scope,
                recommendation_preparation_id=body.recommendation_preparation_id,
            )
    except ValueError as exc:
        code = str(exc)
        _failure(session, document_id, code)
        raise AppError(
            code, code.replace("_", " ").title(), 404 if code.endswith("NOT_FOUND") else 422
        ) from exc
    except Exception as exc:
        _failure(session, document_id, type(exc).__name__)
        raise


@router.get("/credit-decisions/{decision_support_id}")
def get_credit_decision(
    decision_support_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    return decision_payload(session, _decision(session, decision_support_id))


@router.get("/documents/{document_id}/credit-decisions")
def list_credit_decisions(
    document_id: UUID,
    scope: FinancialScope | None = Query(default=None),
    system_recommendation: str | None = Query(default=None),
    latest: bool = Query(default=False),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if session.get(Document, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    query = select(CreditDecisionSupport).where(CreditDecisionSupport.document_id == document_id)
    if scope:
        query = query.where(CreditDecisionSupport.statement_scope == scope)
    if system_recommendation:
        query = query.where(
            CreditDecisionSupport.system_recommendation == system_recommendation.upper()
        )
    rows = session.scalars(
        query.order_by(
            CreditDecisionSupport.created_at.desc(), CreditDecisionSupport.id.desc()
        ).limit(1 if latest else 100)
    )
    return [decision_payload(session, row) for row in rows]


@router.get("/credit-decisions/{decision_support_id}/gates")
def get_decision_gates(
    decision_support_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _decision(session, decision_support_id)
    return [
        gate_payload(x)
        for x in session.scalars(
            select(CreditDecisionGate)
            .where(CreditDecisionGate.credit_decision_support_id == decision_support_id)
            .order_by(CreditDecisionGate.created_at)
        )
    ]


@router.get("/credit-decisions/{decision_support_id}/exceptions")
def get_policy_exceptions(
    decision_support_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _decision(session, decision_support_id)
    return [
        exception_payload(x)
        for x in session.scalars(
            select(CreditPolicyException)
            .where(CreditPolicyException.credit_decision_support_id == decision_support_id)
            .order_by(CreditPolicyException.created_at)
        )
    ]


@router.get("/credit-decisions/{decision_support_id}/review-items")
def get_decision_review_items(
    decision_support_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _decision(session, decision_support_id)
    return [
        review_payload(x)
        for x in session.scalars(
            select(CreditDecisionReviewItem)
            .where(CreditDecisionReviewItem.credit_decision_support_id == decision_support_id)
            .order_by(CreditDecisionReviewItem.blocking.desc(), CreditDecisionReviewItem.created_at)
        )
    ]


@router.get("/credit-decisions/{decision_support_id}/limit-preparation")
def get_limit_preparation(
    decision_support_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    _decision(session, decision_support_id)
    row = session.scalar(
        select(CreditLimitPreparation).where(
            CreditLimitPreparation.credit_decision_support_id == decision_support_id
        )
    )
    if row is None:
        raise AppError(
            "CREDIT_LIMIT_PREPARATION_NOT_FOUND", "Credit limit preparation not found", 404
        )
    methods = list(
        session.scalars(
            select(CreditLimitMethod)
            .where(CreditLimitMethod.credit_decision_support_id == decision_support_id)
            .order_by(CreditLimitMethod.method_code)
        )
    )
    return limit_payload(row, methods)


@router.get("/credit-decisions/{decision_support_id}/evidence")
def get_decision_evidence(
    decision_support_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    row = _decision(session, decision_support_id)
    limit = get_limit_preparation(decision_support_id, session)
    return {
        "decision_support_id": row.id,
        "recommendation_preparation": {
            "id": row.recommendation_preparation_id,
            "url": f"/api/v1/credit-recommendations/{row.recommendation_preparation_id}/evidence",
        },
        "five_cs": {
            "id": row.five_cs_assessment_id,
            "url": f"/api/v1/five-cs/{row.five_cs_assessment_id}/evidence",
        },
        "credit_assessment": {
            "id": row.credit_assessment_id,
            "url": f"/api/v1/credit-assessments/{row.credit_assessment_id}/evidence",
        },
        "research": {
            "id": row.research_run_id,
            "url": f"/api/v1/research-runs/{row.research_run_id}/evidence"
            if row.research_run_id
            else None,
        },
        "limit_methods": limit["methods"],
        "production_ml_used": False,
        "experimental_ml_decision_weight": 0,
    }
