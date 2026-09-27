from __future__ import annotations

# ruff: noqa: E501
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RagIndexRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rag_index_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','BUILDING','COMPLETED','PARTIAL','FAILED')", name="status_valid"
        ),
        UniqueConstraint(
            "company_id",
            "index_version",
            "embedding_version",
            "input_hash",
            name="uq_rag_index_input",
        ),
        Index("ix_rag_index_runs_company_created", "company_id", "created_at"),
    )
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    index_version: Mapped[str] = mapped_column(String(100), nullable=False)
    chunk_builder_version: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))


class RagChunk(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        CheckConstraint("char_length(chunk_hash) = 64", name="chunk_hash_valid"),
        UniqueConstraint(
            "company_id",
            "source_type",
            "source_reference_id",
            "source_version",
            "chunk_hash",
            "index_version",
            name="uq_rag_chunk_source_version",
        ),
        Index("ix_rag_chunks_company_current", "company_id", "is_current"),
        Index("ix_rag_chunks_source", "source_type", "source_reference_id"),
    )
    index_run_id: Mapped[UUID] = mapped_column(ForeignKey("rag_index_runs.id"), nullable=False)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(nullable=False)
    source_version: Mapped[str] = mapped_column(String(150), nullable=False)
    section_type: Mapped[str] = mapped_column(String(100), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[date | None] = mapped_column(Date)
    event_date: Mapped[date | None] = mapped_column(Date)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(50))
    statement_scope: Mapped[str | None] = mapped_column(String(30))
    currency: Mapped[str | None] = mapped_column(String(10))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    source_priority: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    index_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RagEmbedding(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rag_embeddings"
    __table_args__ = (
        UniqueConstraint("rag_chunk_id", "embedding_version", name="uq_rag_embedding_version"),
        CheckConstraint("dimension > 0", name="dimension_positive"),
    )
    rag_chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("rag_chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    embedding_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_json: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    embedding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AnalystChatSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analyst_chat_sessions"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id"))
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))
    review_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("credit_review_cases.id"))


class AnalystChatMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "analyst_chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('USER','ASSISTANT')", name="role_valid"),
        Index("ix_analyst_messages_session_created", "session_id", "created_at"),
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("analyst_chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[str | None] = mapped_column(String(50))
    answer_status: Mapped[str | None] = mapped_column(String(40))
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    model_provider: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RagQueryRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rag_query_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('COMPLETED','INSUFFICIENT_EVIDENCE','CONFLICTING_EVIDENCE','FAILED')",
            name="status_valid",
        ),
        Index("ix_rag_queries_company_created", "company_id", "created_at"),
    )
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("analyst_chat_sessions.id"))
    user_message_id: Mapped[UUID | None] = mapped_column(ForeignKey("analyst_chat_messages.id"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filters_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    retrieval_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    chunk_index_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_provider: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RagRetrievalResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rag_retrieval_results"
    __table_args__ = (UniqueConstraint("rag_query_run_id", "rank", name="uq_rag_retrieval_rank"),)
    rag_query_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("rag_query_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rag_chunk_id: Mapped[UUID] = mapped_column(ForeignKey("rag_chunks.id"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    semantic_score: Mapped[float] = mapped_column(Float, nullable=False)
    keyword_score: Mapped[float] = mapped_column(Float, nullable=False)
    combined_score: Mapped[float] = mapped_column(Float, nullable=False)
    selected_for_context: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RagAnswer(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rag_answers"
    __table_args__ = (
        CheckConstraint(
            "answer_status IN ('ANSWERED','PARTIAL','INSUFFICIENT_EVIDENCE','CONFLICTING_EVIDENCE','REQUIRES_HUMAN_REVIEW','FAILED')",
            name="answer_status_valid",
        ),
        UniqueConstraint("rag_query_run_id", name="uq_rag_answer_query"),
    )
    rag_query_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("rag_query_runs.id", ondelete="CASCADE"), nullable=False
    )
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_status: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unsupported_claim_count: Mapped[int] = mapped_column(Integer, nullable=False)
    citation_coverage_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RagAnswerCitation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rag_answer_citations"
    __table_args__ = (
        UniqueConstraint("rag_answer_id", "citation_index", name="uq_rag_answer_citation_index"),
    )
    rag_answer_id: Mapped[UUID] = mapped_column(
        ForeignKey("rag_answers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rag_chunk_id: Mapped[UUID] = mapped_column(ForeignKey("rag_chunks.id"), nullable=False)
    citation_index: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_text: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RagAnswerFeedback(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rag_answer_feedback"
    __table_args__ = (
        CheckConstraint(
            "rating IN ('HELPFUL','NOT_HELPFUL','INCORRECT','MISSING_SOURCE')", name="rating_valid"
        ),
        UniqueConstraint("rag_answer_id", "user_id", name="uq_rag_feedback_user"),
    )
    rag_answer_id: Mapped[UUID] = mapped_column(
        ForeignKey("rag_answers.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    rating: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
