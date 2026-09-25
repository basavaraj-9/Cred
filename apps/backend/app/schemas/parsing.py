from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentExtractionMethod, PageExtractionMethod, ParserStatus


class ParseSummary(BaseModel):
    document_id: UUID
    parser_status: ParserStatus
    page_count: int
    native_text_pages: int
    ocr_pages: int
    blank_pages: int
    failed_pages: int
    extraction_method: DocumentExtractionMethod
    parser_version: str


class PageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    extraction_method: PageExtractionMethod
    character_count: int
    word_count: int
    text_quality_score: float
    ocr_required: bool
    ocr_attempted: bool
    ocr_succeeded: bool
    error_code: str | None


class PageDetail(PageSummary):
    document_id: UUID
    text_content: str
    parser_version: str
