from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.ml.domain.inference import classify_profile, get_classification, get_evidence
from app.schemas.domain_classification import (
    ClassificationEvidenceResponse,
    DomainClassificationResponse,
)

router = APIRouter(tags=["domain classification"])


@router.post(
    "/company-profiles/{profile_id}/domain-classification",
    response_model=DomainClassificationResponse,
)
def classify(
    profile_id: UUID, request: Request, session: Session = Depends(get_db)
) -> DomainClassificationResponse:
    return classify_profile(session, request.app.state.settings, profile_id)


@router.get(
    "/company-profiles/{profile_id}/domain-classification",
    response_model=DomainClassificationResponse,
)
def retrieve(profile_id: UUID, session: Session = Depends(get_db)) -> DomainClassificationResponse:
    return get_classification(session, profile_id)


@router.get(
    "/domain-classifications/{classification_id}/evidence",
    response_model=list[ClassificationEvidenceResponse],
)
def evidence(
    classification_id: UUID, session: Session = Depends(get_db)
) -> list[ClassificationEvidenceResponse]:
    return get_evidence(session, classification_id)
