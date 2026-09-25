from __future__ import annotations

# ruff: noqa: E501
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.database.session import get_db
from app.models.credit import CreditAssessment
from app.models.credit_fusion import (
    CreditFusionContribution,
    CreditFusionExperiment,
    CreditFusionReason,
)
from app.models.credit_ml import CreditMLFeatureSnapshot
from app.models.document import Document
from app.services.credit_fusion.policy import FUSION_POLICY_VERSION
from app.services.credit_fusion.readiness import CreditFusionReadinessService
from app.services.credit_fusion.service import CreditFusionService, experiment_payload

router = APIRouter(tags=["experimental credit fusion"])


class FusionExperimentRequest(BaseModel):
    credit_assessment_id: UUID
    feature_snapshot_id: UUID
    strategy: str


def _record_failed_attempt(
    session: Session, body: FusionExperimentRequest, error_code: str
) -> None:
    """Persist a sanitized failure event after the experiment transaction rolls back."""
    try:
        session.rollback()
        assessment = session.get(CreditAssessment, body.credit_assessment_id)
        write_audit_log(
            session,
            entity_type="credit_fusion_experiment_attempt",
            entity_id=body.credit_assessment_id,
            action="CREDIT_FUSION_EXPERIMENT_FAILED",
            event_type="CREDIT_FUSION_EXPERIMENT_FAILED",
            company_id=assessment.company_id if assessment else None,
            analysis_job_id=assessment.analysis_job_id if assessment else None,
            metadata_json={
                "strategy": body.strategy,
                "policy_version": FUSION_POLICY_VERSION,
                "credit_assessment_id": str(body.credit_assessment_id),
                "status": "FAILED",
                "error_code": error_code,
                "production_use_permitted": False,
            },
        )
        session.commit()
    except Exception:
        session.rollback()


def _experiment(session: Session, experiment_id: UUID) -> CreditFusionExperiment:
    row = session.get(CreditFusionExperiment, experiment_id)
    if row is None:
        raise AppError(
            "CREDIT_FUSION_EXPERIMENT_NOT_FOUND", "Credit fusion experiment not found", 404
        )
    return row


@router.post("/credit-fusion/experiments")
def create_fusion_experiment(
    body: FusionExperimentRequest, request: Request, session: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        with session.begin():
            return CreditFusionService(session, request.app.state.settings.storage_root).run(
                credit_assessment_id=body.credit_assessment_id,
                feature_snapshot_id=body.feature_snapshot_id,
                strategy=body.strategy,
            )
    except ValueError as exc:
        code = str(exc)
        _record_failed_attempt(session, body, code)
        status = (
            404
            if code in {"CREDIT_ASSESSMENT_NOT_FOUND", "CREDIT_ML_FEATURE_SNAPSHOT_NOT_FOUND"}
            else 422
        )
        raise AppError(code, code.replace("_", " ").title(), status) from exc
    except Exception as exc:
        _record_failed_attempt(session, body, type(exc).__name__)
        raise


@router.get("/credit-fusion/experiments/{experiment_id}")
def get_fusion_experiment(
    experiment_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    return experiment_payload(session, _experiment(session, experiment_id))


@router.get("/documents/{document_id}/credit-fusion/experiments")
def list_document_fusion_experiments(
    document_id: UUID,
    strategy: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if session.get(Document, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    query = select(CreditFusionExperiment).where(CreditFusionExperiment.document_id == document_id)
    if strategy:
        query = query.where(CreditFusionExperiment.strategy == strategy)
    if status:
        query = query.where(CreditFusionExperiment.status == status)
    rows = session.scalars(query.order_by(CreditFusionExperiment.created_at.desc())).all()
    return [experiment_payload(session, row) for row in rows]


@router.get("/credit-fusion/experiments/{experiment_id}/contributions")
def get_fusion_contributions(
    experiment_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _experiment(session, experiment_id)
    rows = session.scalars(
        select(CreditFusionContribution)
        .where(CreditFusionContribution.fusion_experiment_id == experiment_id)
        .order_by(CreditFusionContribution.contribution_type)
    ).all()
    return [
        {
            "contribution_type": row.contribution_type,
            "source_type": row.source_type,
            "raw_value": float(row.raw_value),
            "normalized_value": float(row.normalized_value),
            "weight": float(row.weight),
            "weighted_contribution": float(row.weighted_contribution)
            if row.weighted_contribution is not None
            else None,
            "confidence": row.confidence,
            "status": row.status,
        }
        for row in rows
    ]


@router.get("/credit-fusion/experiments/{experiment_id}/reasons")
def get_fusion_reasons(
    experiment_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _experiment(session, experiment_id)
    rows = session.scalars(
        select(CreditFusionReason)
        .where(CreditFusionReason.fusion_experiment_id == experiment_id)
        .order_by(CreditFusionReason.created_at)
    ).all()
    return [
        {
            "reason_code": row.reason_code,
            "category": row.category,
            "message": row.message,
            "impact_type": row.impact_type,
            "severity": row.severity,
        }
        for row in rows
    ]


@router.get("/documents/{document_id}/credit-fusion/readiness")
def get_fusion_readiness(
    document_id: UUID, request: Request, session: Session = Depends(get_db)
) -> dict[str, object]:
    document = session.get(Document, document_id)
    if document is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    assessment = session.scalar(
        select(CreditAssessment)
        .where(CreditAssessment.document_id == document_id)
        .order_by(CreditAssessment.created_at.desc())
    )
    snapshot = session.scalar(
        select(CreditMLFeatureSnapshot)
        .where(CreditMLFeatureSnapshot.company_id == document.company_id)
        .order_by(CreditMLFeatureSnapshot.created_at.desc())
    )
    if assessment is None or snapshot is None:
        return {
            "status": "BLOCKED",
            "experimental_fusion_allowed": False,
            "production_fusion_allowed": False,
            "blocking_reasons": ["RULE_OR_FEATURE_INPUT_UNAVAILABLE"],
        }
    result = CreditFusionReadinessService(session, request.app.state.settings.storage_root).check(
        assessment.id, snapshot.id
    )
    write_audit_log(
        session,
        entity_type="credit_fusion_readiness",
        entity_id=document.id,
        action="CREDIT_FUSION_READINESS_CHECKED",
        event_type="CREDIT_FUSION_READINESS_CHECKED",
        company_id=document.company_id,
        analysis_job_id=document.analysis_job_id,
        metadata_json={
            "status": result["status"],
            "production_fusion_allowed": False,
        },
    )
    session.commit()
    return result
