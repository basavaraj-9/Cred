import hashlib
import logging
import re
from dataclasses import dataclass

from fastapi import UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.database.repositories.analysis_job import create_analysis_job
from app.database.repositories.audit_log import write_audit_log
from app.database.repositories.company import create_company
from app.database.repositories.document import register_document_metadata
from app.models.company import Company
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.schemas.document import UploadDocumentResult, UploadResult
from app.services.storage.base import StorageBackend

logger = logging.getLogger(__name__)
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class ValidatedFile:
    original_filename: str
    size_bytes: int
    sha256_hash: str


def validate_and_hash(file: UploadFile, max_size_bytes: int) -> ValidatedFile:
    raw_name = file.filename or ""
    basename = raw_name.replace("\\", "/").rsplit("/", 1)[-1]
    safe_name = re.sub(r"[\x00-\x1f\x7f]", "_", basename).strip()[:512]
    if not safe_name or not safe_name.lower().endswith(".pdf"):
        raise AppError("INVALID_FILE_TYPE", "Only PDF files are supported")
    if file.content_type != "application/pdf":
        raise AppError("INVALID_MIME_TYPE", "File MIME type must be application/pdf")

    digest = hashlib.sha256()
    size = 0
    file.file.seek(0)
    first_chunk = True
    while chunk := file.file.read(CHUNK_SIZE):
        if first_chunk and not chunk.startswith(b"%PDF-"):
            raise AppError("INVALID_PDF_SIGNATURE", "File does not have a PDF signature")
        first_chunk = False
        size += len(chunk)
        if size > max_size_bytes:
            raise AppError("FILE_TOO_LARGE", "File exceeds the configured size limit", 413)
        digest.update(chunk)
    if size == 0:
        raise AppError("EMPTY_FILE", "Uploaded file is empty")
    file.file.seek(0)
    return ValidatedFile(safe_name, size, digest.hexdigest())


def upload_document(
    session: Session,
    storage: StorageBackend,
    settings: Settings,
    company_legal_name: str,
    display_name: str | None,
    file: UploadFile,
) -> UploadResult:
    legal_name = " ".join(company_legal_name.split())
    if not legal_name or len(legal_name) > 255:
        raise AppError(
            "INVALID_COMPANY_NAME", "Company legal name is required (max 255 characters)"
        )
    if display_name is not None:
        display_name = display_name.strip() or None
        if display_name and len(display_name) > 255:
            raise AppError("INVALID_DISPLAY_NAME", "Display name exceeds 255 characters")

    logger.info("Upload request received")
    validated = validate_and_hash(file, settings.max_upload_size_bytes)
    logger.info("Upload validation and SHA-256 completed")
    storage_uri: str | None = None
    try:
        with session.begin():
            # Serialize lookups for a normalized name so concurrent uploads reuse one company.
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:name))"), {"name": legal_name.lower()}
            )
            company = session.scalar(
                select(Company)
                .where(func.lower(Company.legal_name) == legal_name.lower())
                .order_by(Company.created_at, Company.id)
                .limit(1)
            )
            if company is None:
                company = create_company(session, legal_name, display_name=display_name)
            existing = session.scalar(
                select(Document)
                .where(
                    Document.company_id == company.id,
                    Document.sha256_hash == validated.sha256_hash,
                )
                .limit(1)
            )
            if existing is not None:
                raise AppError(
                    "DUPLICATE_DOCUMENT",
                    "This document has already been uploaded for this company.",
                    409,
                    {"existing_document_id": str(existing.id)},
                )

            job = create_analysis_job(session, company.id)
            document = register_document_metadata(
                session, job.id, company.id, validated.original_filename
            )
            stored_filename = f"{document.id.hex}.pdf"
            storage_uri = storage.save_file(file.file, stored_filename)
            logger.info("Upload file stored")
            document.stored_filename = stored_filename
            document.file_type = "pdf"
            document.mime_type = "application/pdf"
            document.file_size_bytes = validated.size_bytes
            document.sha256_hash = validated.sha256_hash
            document.storage_uri = storage_uri
            document.status = DocumentStatus.UPLOADED
            write_audit_log(
                session,
                entity_type="document",
                entity_id=document.id,
                action="DOCUMENT_REGISTERED",
                event_type="DOCUMENT_UPLOADED",
                company_id=company.id,
                analysis_job_id=job.id,
                metadata_json={
                    "file_size_bytes": validated.size_bytes,
                    "mime_type": "application/pdf",
                    "storage_provider": "local",
                },
            )
        logger.info("Upload completed")
        return UploadResult(
            analysis_id=job.id,
            company_id=company.id,
            document=UploadDocumentResult(
                id=document.id,
                original_filename=validated.original_filename,
                mime_type="application/pdf",
                file_size_bytes=validated.size_bytes,
                sha256_hash=validated.sha256_hash,
                status=DocumentStatus.UPLOADED,
            ),
            message="Document uploaded successfully.",
        )
    except Exception:
        if storage_uri is not None:
            try:
                storage.delete_file(storage_uri)
            except Exception:
                logger.exception("Stored file cleanup failed after upload rollback")
        logger.warning("Upload failed; database transaction rolled back")
        raise
