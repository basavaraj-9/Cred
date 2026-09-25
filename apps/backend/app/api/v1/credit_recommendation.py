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
from app.models.recommendation import (
    CreditRecommendationFactor,
    CreditRecommendationPreparation,
    CreditRecommendationReviewItem,
)
from app.models.research import ResearchEvidence, ResearchFindingSource, ResearchSource
from app.services.credit_recommendation.policy import POLICY_VERSION
from app.services.credit_recommendation.service import (
    CreditRecommendationService,
    factor_payload,
    recommendation_payload,
    review_payload,
)

router = APIRouter(tags=["credit recommendation preparation"])


class RecommendationRequest(BaseModel):
    scope: FinancialScope | None = None
    five_cs_assessment_id: UUID | None = None
    research_run_id: UUID | None = None
    fusion_experiment_id: UUID | None = None


def _preparation(session: Session, preparation_id: UUID) -> CreditRecommendationPreparation:
    row = session.get(CreditRecommendationPreparation, preparation_id)
    if row is None:
        raise AppError(
            "CREDIT_RECOMMENDATION_NOT_FOUND",
            "Credit recommendation preparation not found",
            404,
        )
    return row


def _record_failure(session: Session, document_id: UUID, code: str) -> None:
    try:
        session.rollback()
        document = session.get(Document, document_id)
        if document:
            write_audit_log(
                session,
                entity_type="credit_recommendation_attempt",
                entity_id=document_id,
                action="CREDIT_RECOMMENDATION_PREPARATION_FAILED",
                event_type="CREDIT_RECOMMENDATION_PREPARATION_FAILED",
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
                metadata_json={"error_code": code, "policy_version": POLICY_VERSION},
            )
            session.commit()
    except Exception:
        session.rollback()


@router.post("/documents/{document_id}/credit-recommendation/prepare")
def prepare_credit_recommendation(
    document_id: UUID,
    body: RecommendationRequest,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        with session.begin():
            return CreditRecommendationService(session).prepare(
                document_id,
                scope=body.scope,
                five_cs_assessment_id=body.five_cs_assessment_id,
                research_run_id=body.research_run_id,
                fusion_experiment_id=body.fusion_experiment_id,
            )
    except ValueError as exc:
        code = str(exc)
        _record_failure(session, document_id, code)
        status = 404 if code.endswith("NOT_FOUND") else 422
        raise AppError(code, code.replace("_", " ").title(), status) from exc
    except Exception as exc:
        _record_failure(session, document_id, type(exc).__name__)
        raise


@router.get("/credit-recommendations/{preparation_id}")
def get_credit_recommendation(
    preparation_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    return recommendation_payload(session, _preparation(session, preparation_id))


@router.get("/documents/{document_id}/credit-recommendations")
def list_credit_recommendations(
    document_id: UUID,
    status: str | None = Query(default=None),
    latest: bool = Query(default=False),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if session.get(Document, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    query = select(CreditRecommendationPreparation).where(
        CreditRecommendationPreparation.document_id == document_id
    )
    if status:
        query = query.where(CreditRecommendationPreparation.status == status.upper())
    rows = list(
        session.scalars(
            query.order_by(
                CreditRecommendationPreparation.created_at.desc(),
                CreditRecommendationPreparation.id.desc(),
            ).limit(1 if latest else 100)
        )
    )
    return [recommendation_payload(session, row) for row in rows]


@router.get("/credit-recommendations/{preparation_id}/factors")
def get_recommendation_factors(
    preparation_id: UUID,
    category: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _preparation(session, preparation_id)
    query = select(CreditRecommendationFactor).where(
        CreditRecommendationFactor.recommendation_preparation_id == preparation_id
    )
    if category:
        query = query.where(CreditRecommendationFactor.category == category.upper())
    if source_type:
        query = query.where(CreditRecommendationFactor.source_type == source_type.upper())
    return [
        factor_payload(row)
        for row in session.scalars(query.order_by(CreditRecommendationFactor.created_at))
    ]


@router.get("/credit-recommendations/{preparation_id}/review-items")
def get_recommendation_review_items(
    preparation_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _preparation(session, preparation_id)
    rows = session.scalars(
        select(CreditRecommendationReviewItem)
        .where(CreditRecommendationReviewItem.recommendation_preparation_id == preparation_id)
        .order_by(
            CreditRecommendationReviewItem.blocking.desc(),
            CreditRecommendationReviewItem.created_at,
        )
    )
    return [review_payload(row) for row in rows]


@router.get("/credit-recommendations/{preparation_id}/evidence")
def get_recommendation_evidence(
    preparation_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    row = _preparation(session, preparation_id)
    factors = list(
        session.scalars(
            select(CreditRecommendationFactor).where(
                CreditRecommendationFactor.recommendation_preparation_id == preparation_id
            )
        )
    )
    research_sources: list[dict[str, object]] = []
    if row.research_run_id:
        research_sources = [
            {
                "finding_id": link.research_finding_id,
                "evidence_id": link.research_evidence_id,
                "source_id": source.id,
                "publisher": source.publisher,
                "source_type": source.source_type,
                "url": source.canonical_url,
                "publication_date": source.publication_date,
                "event_date": source.event_date,
                "freshness": source.freshness_status,
            }
            for link, source in session.execute(
                select(ResearchFindingSource, ResearchSource)
                .join(ResearchSource, ResearchSource.id == ResearchFindingSource.research_source_id)
                .where(
                    ResearchFindingSource.research_evidence_id.in_(
                        select(ResearchEvidence.id).where(
                            ResearchEvidence.research_run_id == row.research_run_id
                        )
                    )
                )
            )
        ]
    return {
        "preparation_id": row.id,
        "credit_assessment": {
            "id": row.credit_assessment_id,
            "url": f"/api/v1/credit-assessments/{row.credit_assessment_id}",
        },
        "five_cs_assessment": {
            "id": row.five_cs_assessment_id,
            "url": f"/api/v1/five-cs/{row.five_cs_assessment_id}",
        },
        "research_run": {
            "id": row.research_run_id,
            "url": f"/api/v1/research-runs/{row.research_run_id}" if row.research_run_id else None,
        },
        "fusion_experiment": {
            "id": row.fusion_experiment_id,
            "url": f"/api/v1/credit-fusion/experiments/{row.fusion_experiment_id}"
            if row.fusion_experiment_id
            else None,
            "role": "SUPPORTING_EXPERIMENTAL_CONTEXT_ONLY",
        },
        "factor_sources": [factor_payload(item) for item in factors],
        "external_sources": research_sources,
    }
