from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document import Document


def register_document_metadata(
    session: Session, analysis_job_id: UUID, company_id: UUID, original_filename: str
) -> Document:
    document = Document(
        analysis_job_id=analysis_job_id,
        company_id=company_id,
        original_filename=original_filename,
    )
    session.add(document)
    session.flush()
    return document
