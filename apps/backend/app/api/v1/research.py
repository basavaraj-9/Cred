from __future__ import annotations

# ruff: noqa: E501
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.document import Document
from app.models.research import (
    ResearchEvidence,
    ResearchFinding,
    ResearchFindingSource,
    ResearchRun,
    ResearchSource,
)
from app.services.external_research.policy import VALID_SCOPES
from app.services.external_research.service import ExternalResearchService, run_payload

router = APIRouter(tags=["external research"])


class ResearchRequest(BaseModel):
    scopes: list[str] = Field(default_factory=lambda: list(VALID_SCOPES), min_length=1)
    refresh: bool = False


def _run(session: Session, run_id: UUID) -> ResearchRun:
    row = session.get(ResearchRun, run_id)
    if row is None:
        raise AppError("RESEARCH_RUN_NOT_FOUND", "Research run not found", 404)
    return row


def _start(session: Session, company_id: UUID, body: ResearchRequest) -> dict[str, object]:
    try:
        with session.begin():
            row = ExternalResearchService(session).research_company(
                company_id, body.scopes, body.refresh
            )
        return run_payload(session, row)
    except ValueError as exc:
        code = str(exc)
        status = 404 if code == "COMPANY_NOT_FOUND" else 422
        raise AppError(code, code.replace("_", " ").title(), status) from exc


@router.post("/companies/{company_id}/research")
def research_company(
    company_id: UUID, body: ResearchRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    return _start(session, company_id, body)


@router.post("/documents/{document_id}/research")
def research_document(
    document_id: UUID, body: ResearchRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    document = session.get(Document, document_id)
    if document is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
    return _start(session, document.company_id, body)


@router.get("/research-runs/{run_id}")
def get_research_run(run_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    return run_payload(session, _run(session, run_id))


@router.get("/research-runs/{run_id}/sources")
def get_sources(
    run_id: UUID,
    source_type: str | None = Query(default=None),
    publisher: str | None = Query(default=None),
    status: str | None = Query(default=None),
    published_on: date | None = Query(default=None, alias="date"),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _run(session, run_id)
    query = select(ResearchSource).where(ResearchSource.research_run_id == run_id)
    if source_type:
        query = query.where(ResearchSource.source_type == source_type.upper())
    if publisher:
        query = query.where(ResearchSource.publisher.ilike(f"%{publisher}%"))
    if status:
        query = query.where(ResearchSource.status == status.upper())
    if published_on:
        query = query.where(ResearchSource.publication_date == published_on)
    rows = session.scalars(
        query.order_by(ResearchSource.retrieved_at, ResearchSource.publisher)
    ).all()
    return [
        {
            "source_id": row.id,
            "title": row.title,
            "publisher": row.publisher,
            "source_type": row.source_type,
            "source_tier": row.source_tier,
            "quality": row.quality_score,
            "url": row.canonical_url,
            "publication_date": row.publication_date,
            "event_date": row.event_date,
            "retrieved_at": row.retrieved_at,
            "freshness": row.freshness_status,
            "entity_match_status": row.entity_match_status,
            "entity_match_score": row.entity_match_score,
            "content_hash": row.content_hash,
            "status": row.status,
            "duplicate_of_source_id": row.duplicate_of_source_id,
            "error_code": row.error_code,
        }
        for row in rows
    ]


@router.get("/research-runs/{run_id}/evidence")
def get_evidence(
    run_id: UUID,
    category: str | None = Query(default=None),
    impact: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    candidate_section: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _run(session, run_id)
    query = select(ResearchEvidence).where(ResearchEvidence.research_run_id == run_id)
    for column, value in (
        (ResearchEvidence.category, category),
        (ResearchEvidence.impact, impact),
        (ResearchEvidence.entity_type, entity_type),
        (ResearchEvidence.status, status),
        (ResearchEvidence.candidate_section, candidate_section),
    ):
        if value:
            query = query.where(column == value.upper())
    rows = session.scalars(query.order_by(ResearchEvidence.created_at)).all()
    return [
        {
            "evidence_id": row.id,
            "source_id": row.research_source_id,
            "category": row.category,
            "event_code": row.event_code,
            "evidence_text": row.evidence_text,
            "evidence_hash": row.evidence_hash,
            "entity_type": row.entity_type,
            "entity_name": row.entity_name,
            "impact": row.impact,
            "confidence": row.confidence,
            "status": row.status,
            "candidate_section": row.candidate_section,
            "event_date": row.event_date,
            "attributes": row.attributes_json,
        }
        for row in rows
    ]


def _finding_payload(
    session: Session, row: ResearchFinding, lineage: bool = False
) -> dict[str, object]:
    payload: dict[str, object] = {
        "finding_id": row.id,
        "finding_code": row.finding_code,
        "category": row.category,
        "summary": row.summary,
        "entity_type": row.entity_type,
        "entity_name": row.entity_name,
        "impact": row.impact,
        "status": row.status,
        "confidence": row.confidence,
        "source_count": row.source_count,
        "candidate_section": row.candidate_section,
        "event_date": row.event_date,
        "first_published_at": row.first_published_at,
        "latest_published_at": row.latest_published_at,
        "contradiction_code": row.contradiction_code,
        "applied_to_day15": False,
    }
    if lineage:
        links = session.execute(
            select(ResearchFindingSource, ResearchSource, ResearchEvidence)
            .join(ResearchSource, ResearchSource.id == ResearchFindingSource.research_source_id)
            .join(
                ResearchEvidence, ResearchEvidence.id == ResearchFindingSource.research_evidence_id
            )
            .where(ResearchFindingSource.research_finding_id == row.id)
        ).all()
        payload["lineage"] = [
            {
                "source_id": source.id,
                "evidence_id": evidence.id,
                "publisher": source.publisher,
                "url": source.canonical_url,
                "evidence_text": evidence.evidence_text,
                "is_independent": link.is_independent,
            }
            for link, source, evidence in links
        ]
    return payload


@router.get("/research-runs/{run_id}/findings")
def get_findings(run_id: UUID, session: Session = Depends(get_db)) -> list[dict[str, object]]:
    _run(session, run_id)
    rows = session.scalars(
        select(ResearchFinding)
        .where(ResearchFinding.research_run_id == run_id)
        .order_by(ResearchFinding.category, ResearchFinding.created_at)
    ).all()
    return [_finding_payload(session, row) for row in rows]


@router.get("/research-findings/{finding_id}")
def get_finding(finding_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    row = session.get(ResearchFinding, finding_id)
    if row is None:
        raise AppError("RESEARCH_FINDING_NOT_FOUND", "Research finding not found", 404)
    return _finding_payload(session, row, lineage=True)


@router.get("/research-runs/{run_id}/five-cs-candidates")
def get_five_cs_candidates(run_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    _run(session, run_id)
    rows = session.scalars(
        select(ResearchFinding)
        .where(
            ResearchFinding.research_run_id == run_id,
            ResearchFinding.candidate_section.is_not(None),
        )
        .order_by(ResearchFinding.candidate_section, ResearchFinding.created_at)
    ).all()
    return {
        "research_run_id": run_id,
        "character": [
            _finding_payload(session, row) for row in rows if row.candidate_section == "CHARACTER"
        ],
        "conditions": [
            _finding_payload(session, row) for row in rows if row.candidate_section == "CONDITIONS"
        ],
        "applied_to_day15": False,
    }
