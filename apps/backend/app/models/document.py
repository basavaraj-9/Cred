from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DocumentExtractionMethod, DocumentStatus, ParserStatus

if TYPE_CHECKING:
    from app.models.analysis_job import AnalysisJob
    from app.models.company import Company
    from app.models.document_page import DocumentPage


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("file_size_bytes >= 0", name="file_size_nonnegative"),
        Index("ix_documents_analysis_job_id", "analysis_job_id"),
        Index("ix_documents_company_id", "company_id"),
        Index("ix_documents_sha256_hash", "sha256_hash"),
        UniqueConstraint("company_id", "sha256_hash", name="uq_documents_company_sha256"),
    )

    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_filename: Mapped[str | None] = mapped_column(String(512))
    file_type: Mapped[str | None] = mapped_column(String(50))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256_hash: Mapped[str | None] = mapped_column(String(64))
    storage_uri: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, native_enum=False, create_constraint=True),
        nullable=False,
        default=DocumentStatus.REGISTERED,
    )
    parser_status: Mapped[ParserStatus] = mapped_column(
        SAEnum(ParserStatus, native_enum=False, create_constraint=True),
        nullable=False,
        default=ParserStatus.NOT_STARTED,
        server_default=ParserStatus.NOT_STARTED,
    )
    page_count: Mapped[int | None] = mapped_column(Integer)
    parser_version: Mapped[str | None] = mapped_column(String(100))
    extraction_method: Mapped[DocumentExtractionMethod | None] = mapped_column(
        SAEnum(DocumentExtractionMethod, native_enum=False, create_constraint=True)
    )
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parse_error_code: Mapped[str | None] = mapped_column(String(100))
    parse_error_message: Mapped[str | None] = mapped_column(String(500))

    analysis_job: Mapped[AnalysisJob] = relationship(back_populates="documents")
    company: Mapped[Company] = relationship(back_populates="documents")
    pages: Mapped[list[DocumentPage]] = relationship(back_populates="document")
