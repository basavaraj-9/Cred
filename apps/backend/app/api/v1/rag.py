from __future__ import annotations

# ruff: noqa: E501
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.database.session import get_db
from app.models.rag import (
    AnalystChatMessage,
    AnalystChatSession,
    RagAnswer,
    RagAnswerFeedback,
    RagChunk,
    RagIndexRun,
    RagQueryRun,
    RagRetrievalResult,
)
from app.services.rag.service import (
    CreditAnalystAssistantService,
    CreditRagIndexService,
    answer_payload,
)

router = APIRouter(tags=["credit analyst assistant"])


class ActorRequest(BaseModel):
    actor_user_id: UUID


class AskRequest(ActorRequest):
    question: str = Field(min_length=1, max_length=2000)
    scope: str | None = None
    period: str | None = None
    session_id: UUID | None = None


class SessionRequest(ActorRequest):
    company_id: UUID | None = None
    document_id: UUID | None = None
    review_case_id: UUID | None = None


class FeedbackRequest(ActorRequest):
    rating: Literal["HELPFUL", "NOT_HELPFUL", "INCORRECT", "MISSING_SOURCE"]
    comment: str | None = None


def _session_payload(row: AnalystChatSession) -> dict[str, object]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "company_id": row.company_id,
        "document_id": row.document_id,
        "review_case_id": row.review_case_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.post("/companies/{company_id}/rag/index")
def build_index(
    company_id: UUID, body: ActorRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        row = CreditRagIndexService(session).build(company_id, body.actor_user_id)
    return {
        "id": row.id,
        "company_id": row.company_id,
        "index_version": row.index_version,
        "chunk_builder_version": row.chunk_builder_version,
        "embedding_provider": row.embedding_provider,
        "embedding_model": row.embedding_model,
        "embedding_version": row.embedding_version,
        "status": row.status,
        "source_count": row.source_count,
        "chunk_count": row.chunk_count,
        "new_chunk_count": row.new_chunk_count,
        "input_hash": row.input_hash,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
    }


@router.get("/companies/{company_id}/rag/index")
def index_status(
    company_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    CreditRagIndexService(session)._user(actor_user_id)
    row = session.scalar(
        select(RagIndexRun)
        .where(RagIndexRun.company_id == company_id)
        .order_by(desc(RagIndexRun.created_at))
        .limit(1)
    )
    if row is None:
        raise AppError("RAG_INDEX_NOT_FOUND", "RAG index not found", 404)
    coverage: dict[str, int] = {
        source_type: count
        for source_type, count in session.execute(
            select(RagChunk.source_type, func.count())
            .where(RagChunk.company_id == company_id, RagChunk.is_current.is_(True))
            .group_by(RagChunk.source_type)
        )
    }
    return {
        "id": row.id,
        "index_version": row.index_version,
        "status": row.status,
        "chunk_count": row.chunk_count,
        "source_count": row.source_count,
        "source_coverage": coverage,
        "embedding_provider": row.embedding_provider,
        "embedding_model": row.embedding_model,
        "completed_at": row.completed_at,
    }


@router.post("/companies/{company_id}/analyst/ask")
def ask(
    company_id: UUID, body: AskRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        answer = CreditAnalystAssistantService(session).ask(
            company_id,
            body.actor_user_id,
            body.question,
            scope=body.scope,
            period=body.period,
            session_id=body.session_id,
        )
    return answer_payload(session, answer)


@router.post("/analyst/sessions")
def create_session(body: SessionRequest, session: Session = Depends(get_db)) -> dict[str, object]:
    with session.begin():
        CreditRagIndexService(session)._user(body.actor_user_id)
        row = AnalystChatSession(
            user_id=body.actor_user_id,
            company_id=body.company_id,
            document_id=body.document_id,
            review_case_id=body.review_case_id,
        )
        session.add(row)
        session.flush()
    return _session_payload(row)


@router.get("/analyst/sessions/{session_id}")
def get_session(
    session_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    CreditRagIndexService(session)._user(actor_user_id)
    row = session.get(AnalystChatSession, session_id)
    if row is None:
        raise AppError("ANALYST_SESSION_NOT_FOUND", "Analyst session not found", 404)
    if row.user_id != actor_user_id:
        raise AppError("ANALYST_SESSION_FORBIDDEN", "Session belongs to another user", 403)
    return _session_payload(row)


@router.get("/analyst/sessions/{session_id}/messages")
def get_messages(
    session_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    get_session(session_id, actor_user_id, session)
    return [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "query_type": row.query_type,
            "answer_status": row.answer_status,
            "created_at": row.created_at,
        }
        for row in session.scalars(
            select(AnalystChatMessage)
            .where(AnalystChatMessage.session_id == session_id)
            .order_by(AnalystChatMessage.created_at)
        )
    ]


@router.post("/analyst/sessions/{session_id}/messages")
def send_message(
    session_id: UUID, body: AskRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        chat = session.get(AnalystChatSession, session_id)
        if chat is None or chat.company_id is None:
            raise AppError("ANALYST_SESSION_COMPANY_REQUIRED", "Session requires a company", 422)
        answer = CreditAnalystAssistantService(session).ask(
            chat.company_id,
            body.actor_user_id,
            body.question,
            scope=body.scope,
            period=body.period,
            session_id=session_id,
        )
    return answer_payload(session, answer)


@router.get("/analyst/answers/{answer_id}/citations")
def get_citations(
    answer_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    answer = session.get(RagAnswer, answer_id)
    if answer is None:
        raise AppError("RAG_ANSWER_NOT_FOUND", "Answer not found", 404)
    return cast(list[dict[str, object]], answer_payload(session, answer)["citations"])


@router.get("/analyst/queries/{query_run_id}/retrieval")
def retrieval_debug(
    query_run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id, admin=True)
    query = session.get(RagQueryRun, query_run_id)
    if query is None:
        raise AppError("RAG_QUERY_NOT_FOUND", "Query run not found", 404)
    return [
        {
            "rank": row.rank,
            "chunk_id": row.rag_chunk_id,
            "semantic_score": row.semantic_score,
            "keyword_score": row.keyword_score,
            "combined_score": row.combined_score,
            "selected_for_context": row.selected_for_context,
        }
        for row in session.scalars(
            select(RagRetrievalResult)
            .where(RagRetrievalResult.rag_query_run_id == query.id)
            .order_by(RagRetrievalResult.rank)
        )
    ]


@router.post("/analyst/answers/{answer_id}/feedback")
def feedback(
    answer_id: UUID, body: FeedbackRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        user = CreditRagIndexService(session)._user(body.actor_user_id)
        if session.get(RagAnswer, answer_id) is None:
            raise AppError("RAG_ANSWER_NOT_FOUND", "Answer not found", 404)
        row = RagAnswerFeedback(
            rag_answer_id=answer_id,
            user_id=user.id,
            rating=body.rating,
            comment=body.comment,
            created_at=datetime.now(UTC),
        )
        session.add(row)
        session.flush()
        write_audit_log(
            session,
            entity_type="rag_answer",
            entity_id=answer_id,
            action="ANALYST_FEEDBACK_RECORDED",
            event_type="ANALYST_FEEDBACK_RECORDED",
            user_id=user.id,
            metadata_json={"rating": body.rating},
        )
    return {
        "id": row.id,
        "answer_id": answer_id,
        "rating": row.rating,
        "created_at": row.created_at,
    }
