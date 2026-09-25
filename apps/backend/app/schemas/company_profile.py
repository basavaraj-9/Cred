from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import FieldStatus, IdentityMatchStatus, ProfileStatus


class FieldSummary(BaseModel):
    id: UUID
    field_name: str
    value: str
    confidence: float
    status: FieldStatus
    page_number: int


class ProfileResponse(BaseModel):
    profile_id: UUID
    document_id: UUID
    company_id: UUID
    analysis_job_id: UUID
    uploaded_company_name: str
    status: ProfileStatus
    identity_match_status: IdentityMatchStatus
    overall_confidence: float
    extractor_version: str
    fields: dict[str, list[FieldSummary]]


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    document_page_id: UUID
    page_number: int
    field_group: str
    field_name: str
    raw_value: str
    normalized_value: str
    evidence_text: str
    confidence_score: float
    status: FieldStatus
    extraction_method: str
    extractor_version: str
