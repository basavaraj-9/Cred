import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.enums import (
    AnalysisStage,
    DocumentExtractionMethod,
    DocumentStatus,
    PageExtractionMethod,
    ParserStatus,
)
from app.schemas.parsing import ParseSummary
from app.services.document_intelligence.ocr import OCRProvider
from app.services.document_intelligence.pdf_parser import (
    PARSER_VERSION,
    ParsedDocument,
    PDFParseError,
    parse_pdf,
)
from app.services.storage.base import StorageBackend

logger = logging.getLogger(__name__)
TERMINAL_STATUSES = {
    ParserStatus.PARSED,
    ParserStatus.PARTIAL,
    ParserStatus.FAILED,
    ParserStatus.REVIEW_REQUIRED,
}


def _summary_from_existing(session: Session, document: Document) -> ParseSummary:
    methods = session.scalars(
        select(DocumentPage.extraction_method).where(DocumentPage.document_id == document.id)
    ).all()
    counts = {method: methods.count(method) for method in PageExtractionMethod}
    return ParseSummary(
        document_id=document.id,
        parser_status=document.parser_status,
        page_count=document.page_count or 0,
        native_text_pages=counts[PageExtractionMethod.NATIVE_TEXT],
        ocr_pages=counts[PageExtractionMethod.OCR],
        blank_pages=counts[PageExtractionMethod.BLANK],
        failed_pages=counts[PageExtractionMethod.FAILED],
        extraction_method=document.extraction_method or DocumentExtractionMethod.FAILED,
        parser_version=document.parser_version or PARSER_VERSION,
    )


def _mark_failed(session: Session, document_id: UUID, error: PDFParseError) -> None:
    with session.begin():
        document = session.get(Document, document_id, with_for_update=True)
        assert document is not None
        document.parser_status = ParserStatus.FAILED
        document.parser_version = PARSER_VERSION
        document.extraction_method = DocumentExtractionMethod.FAILED
        document.parse_error_code = error.code
        document.parse_error_message = error.message
        document.parsed_at = datetime.now(UTC)
        write_audit_log(
            session,
            entity_type="document",
            entity_id=document.id,
            action="DOCUMENT_PARSE_FAILED",
            event_type="DOCUMENT_PARSE_FAILED",
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            metadata_json={"error_code": error.code, "parser_version": PARSER_VERSION},
        )


def _persist_parsed(session: Session, document_id: UUID, parsed: ParsedDocument) -> None:
    with session.begin():
        document = session.get(Document, document_id, with_for_update=True)
        assert document is not None
        for page in parsed.pages:
            session.add(
                DocumentPage(
                    document_id=document_id,
                    page_number=page.page_number,
                    extraction_method=page.extraction_method,
                    text_content=page.text_content,
                    character_count=page.character_count,
                    word_count=page.word_count,
                    text_quality_score=page.text_quality_score,
                    ocr_required=page.ocr_required,
                    ocr_attempted=page.ocr_attempted,
                    ocr_succeeded=page.ocr_succeeded,
                    parser_version=PARSER_VERSION,
                    error_code=page.error_code,
                    error_message=page.error_message,
                )
            )
        document.page_count = parsed.page_count
        document.parser_status = parsed.parser_status
        document.parser_version = PARSER_VERSION
        document.extraction_method = parsed.extraction_method
        document.parsed_at = datetime.now(UTC)
        document.parse_error_code = None
        document.parse_error_message = None
        event_type = (
            "DOCUMENT_PARSE_COMPLETED"
            if parsed.parser_status == ParserStatus.PARSED
            else "DOCUMENT_PARSE_PARTIAL"
        )
        metadata = {
            "page_count": parsed.page_count,
            "native_pages": parsed.native_text_pages,
            "ocr_pages": parsed.ocr_pages,
            "blank_pages": parsed.blank_pages,
            "failed_pages": parsed.failed_pages,
            "parser_version": PARSER_VERSION,
        }
        write_audit_log(
            session,
            entity_type="document",
            entity_id=document.id,
            action=event_type,
            event_type=event_type,
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            metadata_json=metadata,
        )
        if any(page.ocr_attempted for page in parsed.pages):
            write_audit_log(
                session,
                entity_type="document",
                entity_id=document.id,
                action="OCR_FALLBACK_USED",
                event_type="OCR_FALLBACK_USED",
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
                metadata_json={"ocr_pages": parsed.ocr_pages, "parser_version": PARSER_VERSION},
            )


def parse_document(
    session: Session,
    storage: StorageBackend,
    ocr: OCRProvider,
    settings: Settings,
    document_id: UUID,
) -> ParseSummary:
    with session.begin():
        document = session.get(Document, document_id, with_for_update=True)
        if document is None:
            raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
        if document.status != DocumentStatus.UPLOADED or not document.storage_uri:
            raise AppError("DOCUMENT_NOT_UPLOADED", "Document has no stored upload", 409)
        if document.parser_status in TERMINAL_STATUSES:
            return _summary_from_existing(session, document)
        if document.parser_status == ParserStatus.PARSING:
            raise AppError("PARSE_IN_PROGRESS", "Document parsing is already in progress", 409)
        storage_uri = document.storage_uri
        document.parser_status = ParserStatus.PARSING
        document.parser_version = PARSER_VERSION
        document.analysis_job.current_stage = AnalysisStage.DOCUMENT_PARSING
        write_audit_log(
            session,
            entity_type="document",
            entity_id=document.id,
            action="DOCUMENT_PARSE_STARTED",
            event_type="DOCUMENT_PARSE_STARTED",
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            metadata_json={"parser_version": PARSER_VERSION},
        )
    logger.info("Document parse started: %s", document_id)
    try:
        if not storage.exists(storage_uri):
            raise PDFParseError("SOURCE_FILE_MISSING", "The stored PDF file is missing")
        parsed = parse_pdf(storage.get_file_path(storage_uri), ocr, settings)
    except PDFParseError as error:
        _mark_failed(session, document_id, error)
        logger.warning("Document parse failed: %s (%s)", document_id, error.code)
        raise AppError(
            error.code, error.message, 404 if error.code == "SOURCE_FILE_MISSING" else 422
        ) from error

    try:
        _persist_parsed(session, document_id, parsed)
    except Exception:
        logger.exception("Document parse persistence failed: %s", document_id)
        session.rollback()
        try:
            _mark_failed(
                session,
                document_id,
                PDFParseError("PARSE_PERSISTENCE_ERROR", "Parsed pages could not be saved"),
            )
        except Exception:
            logger.exception("Could not record parser failure: %s", document_id)
        raise
    logger.info(
        "Document parse finished: %s pages=%s native=%s ocr=%s failed=%s",
        document_id,
        parsed.page_count,
        parsed.native_text_pages,
        parsed.ocr_pages,
        parsed.failed_pages,
    )
    return ParseSummary(
        document_id=document_id,
        parser_status=parsed.parser_status,
        page_count=parsed.page_count,
        native_text_pages=parsed.native_text_pages,
        ocr_pages=parsed.ocr_pages,
        blank_pages=parsed.blank_pages,
        failed_pages=parsed.failed_pages,
        extraction_method=parsed.extraction_method,
        parser_version=PARSER_VERSION,
    )
