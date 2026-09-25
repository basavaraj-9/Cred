from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.analysis_job import AnalysisJob
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.schemas.document import DocumentMetadata, UploadResult
from app.schemas.parsing import PageDetail, PageSummary, ParseSummary
from app.services.document_intelligence.ocr import OCRProvider, get_ocr_provider
from app.services.document_intelligence.service import parse_document
from app.services.ingestion import upload_document
from app.services.storage.base import StorageBackend
from app.services.storage.service import get_storage

router = APIRouter(tags=["documents"])


@router.post("/documents/upload", response_model=UploadResult, status_code=201)
def upload(
    request: Request,
    company_legal_name: str = Form(...),
    display_name: str | None = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> UploadResult:
    return upload_document(
        session, storage, request.app.state.settings, company_legal_name, display_name, file
    )


@router.get("/documents/{document_id}", response_model=DocumentMetadata)
def get_document(document_id: UUID, session: Session = Depends(get_db)) -> DocumentMetadata:
    document = session.get(Document, document_id)
    if document is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    return DocumentMetadata.model_validate(document)


@router.post("/documents/{document_id}/parse", response_model=ParseSummary)
def parse_uploaded_document(
    document_id: UUID,
    request: Request,
    session: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    ocr: OCRProvider = Depends(get_ocr_provider),
) -> ParseSummary:
    return parse_document(session, storage, ocr, request.app.state.settings, document_id)


@router.get("/documents/{document_id}/pages", response_model=list[PageSummary])
def list_document_pages(document_id: UUID, session: Session = Depends(get_db)) -> list[PageSummary]:
    if session.get(Document, document_id) is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    pages = session.scalars(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    ).all()
    return [PageSummary.model_validate(page) for page in pages]


@router.get("/documents/{document_id}/pages/{page_number}", response_model=PageDetail)
def get_document_page(
    document_id: UUID, page_number: int, session: Session = Depends(get_db)
) -> PageDetail:
    page = session.scalar(
        select(DocumentPage).where(
            DocumentPage.document_id == document_id, DocumentPage.page_number == page_number
        )
    )
    if page is None:
        raise AppError("PAGE_NOT_FOUND", "Document page not found", 404)
    return PageDetail.model_validate(page)


@router.get("/analysis/{analysis_id}/documents", response_model=list[DocumentMetadata])
def list_analysis_documents(
    analysis_id: UUID, session: Session = Depends(get_db)
) -> list[DocumentMetadata]:
    if session.get(AnalysisJob, analysis_id) is None:
        raise AppError("ANALYSIS_NOT_FOUND", "Analysis not found", 404)
    documents = session.scalars(
        select(Document)
        .where(Document.analysis_job_id == analysis_id)
        .order_by(Document.created_at)
    ).all()
    return [DocumentMetadata.model_validate(document) for document in documents]
