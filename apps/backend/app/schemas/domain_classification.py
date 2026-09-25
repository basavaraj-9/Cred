from uuid import UUID

from pydantic import BaseModel

from app.models.enums import ClassificationStatus


class LabelConfidence(BaseModel):
    label: str
    confidence: float


class DomainClassificationResponse(BaseModel):
    classification_id: UUID
    company_profile_id: UUID
    sector: LabelConfidence
    industry: LabelConfidence
    domain: LabelConfidence
    sub_domain: LabelConfidence
    overall_confidence: float
    status: ClassificationStatus
    alternative_sub_domain: LabelConfidence | None
    taxonomy_version: str
    model_version: str
    dataset_version: str
    input_builder_version: str
    input_text_hash: str
    stale: bool


class ClassificationEvidenceResponse(BaseModel):
    extracted_field_id: UUID
    document_page_id: UUID
    document_id: UUID
    page_number: int
    field_name: str
    evidence_role: str
    evidence_text: str
    confidence_score: float
