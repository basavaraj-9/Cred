from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentExtractionMethod, DocumentStatus, ParserStatus


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    analysis_job_id: UUID
    company_id: UUID
    original_filename: str
    file_type: str | None
    mime_type: str | None
    file_size_bytes: int | None
    sha256_hash: str | None
    status: DocumentStatus
    created_at: datetime
    parser_status: ParserStatus
    page_count: int | None
    extraction_method: DocumentExtractionMethod | None
    parser_version: str | None
    parsed_at: datetime | None
    parse_error_code: str | None


class UploadDocumentResult(BaseModel):
    id: UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    status: DocumentStatus


class UploadResult(BaseModel):
    analysis_id: UUID
    company_id: UUID
    document: UploadDocumentResult
    message: str
