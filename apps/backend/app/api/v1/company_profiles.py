from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.company_profile import EvidenceResponse, ProfileResponse
from app.services.company_profile.service import extract_profile, get_evidence, get_profile

router = APIRouter(tags=["company profiles"])


@router.post("/documents/{document_id}/company-profile/extract", response_model=ProfileResponse)
def extract_document_profile(
    document_id: UUID, session: Session = Depends(get_db)
) -> ProfileResponse:
    return extract_profile(session, document_id)


@router.get("/documents/{document_id}/company-profile", response_model=ProfileResponse)
def read_document_profile(document_id: UUID, session: Session = Depends(get_db)) -> ProfileResponse:
    return get_profile(session, document_id)


@router.get("/company-profiles/{profile_id}/evidence", response_model=list[EvidenceResponse])
def read_profile_evidence(
    profile_id: UUID, session: Session = Depends(get_db)
) -> list[EvidenceResponse]:
    return get_evidence(session, profile_id)
