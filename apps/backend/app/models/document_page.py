from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PageExtractionMethod

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentPage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        CheckConstraint("page_number >= 1", name="page_number_positive"),
        CheckConstraint("character_count >= 0", name="character_count_nonnegative"),
        CheckConstraint("word_count >= 0", name="word_count_nonnegative"),
        CheckConstraint(
            "text_quality_score >= 0 AND text_quality_score <= 1", name="quality_range"
        ),
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),
        Index("ix_document_pages_document_id", "document_id"),
    )

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_method: Mapped[PageExtractionMethod] = mapped_column(
        SAEnum(PageExtractionMethod, native_enum=False, create_constraint=True), nullable=False
    )
    text_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    character_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ocr_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    ocr_attempted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    ocr_succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))

    document: Mapped[Document] = relationship(back_populates="pages")
