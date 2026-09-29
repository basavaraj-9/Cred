from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.stock import ListedCompany, StockListing
from app.models.stock_intelligence import (
    StockIntelligenceComponent,
    StockIntelligenceComponentInput,
    StockIntelligenceRun,
    StockRankingMember,
    StockRankingRun,
)
from app.services.rag.service import CreditRagIndexService
from app.services.stock_intelligence.service import StockIntelligenceService

router = APIRouter(prefix="/stock-intelligence", tags=["stock intelligence research"])


class ScoreBuild(BaseModel):
    actor_user_id: UUID
    stock_listing_id: UUID
    as_of_date: date


class RankingBuild(BaseModel):
    actor_user_id: UUID
    as_of_date: date
    stock_listing_ids: list[UUID] | None = None


def score_payload(run: StockIntelligenceRun) -> dict[str, object]:
    return {
        "id": run.id,
        "listed_company_id": run.listed_company_id,
        "stock_listing_id": run.stock_listing_id,
        "as_of_date": run.as_of_date,
        "score_version": run.score_version,
        "fusion_policy_version": run.fusion_policy_version,
        "normalization_policy_version": run.normalization_policy_version,
        "ranking_policy_version": run.ranking_policy_version,
        "watchlist_policy_version": run.watchlist_policy_version,
        "status": run.status,
        "score": run.score,
        "confidence": run.confidence,
        "coverage": run.coverage,
        "available_weight": run.available_weight,
        "available_component_count": run.available_component_count,
        "missing_component_count": run.missing_component_count,
        "band": run.band,
        "agreement_score": run.agreement_score,
        "production_use_permitted": False,
        "research_only": True,
    }


def components_payload(session: Session, run_id: UUID) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for component in session.scalars(
        select(StockIntelligenceComponent)
        .where(StockIntelligenceComponent.run_id == run_id)
        .order_by(StockIntelligenceComponent.component_name)
    ):
        inputs = list(
            session.scalars(
                select(StockIntelligenceComponentInput).where(
                    StockIntelligenceComponentInput.component_id == component.id
                )
            )
        )
        output.append(
            {
                "id": component.id,
                "name": component.component_name,
                "score": component.normalized_score,
                "weight": component.configured_weight,
                "effective_weight": component.effective_weight,
                "contribution": component.contribution,
                "confidence": component.confidence,
                "status": component.status,
                "explanation": component.explanation,
                "inputs": [
                    {
                        "source_type": item.source_type,
                        "source_id": item.source_id,
                        "feature_name": item.feature_name,
                        "source_value": item.source_value,
                        "source_status": item.source_status,
                    }
                    for item in inputs
                ],
            }
        )
    return output


def ranking_payload(session: Session, run: StockRankingRun) -> dict[str, object]:
    members = list(
        session.scalars(
            select(StockRankingMember)
            .where(StockRankingMember.ranking_run_id == run.id)
            .order_by(StockRankingMember.rank)
        )
    )
    listing_map = {
        listing.id: listing
        for listing in session.scalars(
            select(StockListing).where(
                StockListing.id.in_([member.stock_listing_id for member in members])
            )
        )
    }
    company_map = {
        company.id: company
        for company in session.scalars(
            select(ListedCompany).where(
                ListedCompany.id.in_([member.listed_company_id for member in members])
            )
        )
    }
    return {
        "id": run.id,
        "as_of_date": run.as_of_date,
        "ranking_policy_version": run.ranking_policy_version,
        "watchlist_policy_version": run.watchlist_policy_version,
        "universe_hash": run.universe_hash,
        "status": run.status,
        "eligible_company_count": run.eligible_company_count,
        "members": [
            {
                "stock_intelligence_run_id": member.stock_intelligence_run_id,
                "listed_company_id": member.listed_company_id,
                "stock_listing_id": member.stock_listing_id,
                "company_name": company_map[member.listed_company_id].canonical_name,
                "ticker": listing_map[member.stock_listing_id].symbol,
                "score": member.score,
                "confidence": member.confidence,
                "coverage": member.coverage,
                "rank": member.rank,
                "percentile": member.percentile,
                "rank_status": member.rank_status,
                "research_priority": member.research_priority,
            }
            for member in members
        ],
        "research_only": True,
    }


@router.post("/scores/build")
def build_score(body: ScoreBuild, session: Session = Depends(get_db)) -> dict[str, object]:
    with session.begin():
        run = StockIntelligenceService(session).build_score(
            body.stock_listing_id, body.as_of_date, body.actor_user_id
        )
    return score_payload(run)


@router.get("/scores/{score_run_id}")
def get_score(
    score_run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    CreditRagIndexService(session)._user(actor_user_id)
    run = session.get(StockIntelligenceRun, score_run_id)
    if run is None:
        raise AppError("STOCK_INTELLIGENCE_NOT_FOUND", "Stock intelligence score not found", 404)
    return score_payload(run)


@router.get("/scores")
def list_scores(
    actor_user_id: UUID,
    listing: UUID | None = None,
    company: UUID | None = None,
    as_of_date: date | None = None,
    status: str | None = None,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    query = select(StockIntelligenceRun)
    if listing:
        query = query.where(StockIntelligenceRun.stock_listing_id == listing)
    if company:
        query = query.where(StockIntelligenceRun.listed_company_id == company)
    if as_of_date:
        query = query.where(StockIntelligenceRun.as_of_date == as_of_date)
    if status:
        query = query.where(StockIntelligenceRun.status == status)
    return [
        score_payload(run)
        for run in session.scalars(query.order_by(StockIntelligenceRun.created_at))
    ]


@router.get("/scores/{score_run_id}/components")
def get_components(
    score_run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    CreditRagIndexService(session)._user(actor_user_id)
    return components_payload(session, score_run_id)


@router.get("/scores/{score_run_id}/explanation")
def get_explanation(
    score_run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    CreditRagIndexService(session)._user(actor_user_id)
    run = session.get(StockIntelligenceRun, score_run_id)
    if run is None:
        raise AppError("STOCK_INTELLIGENCE_NOT_FOUND", "Stock intelligence score not found", 404)
    return {
        "score_run_id": run.id,
        "positive_drivers": run.top_positive_drivers,
        "negative_drivers": run.top_negative_drivers,
        "neutral_factors": [],
        "missing_evidence": run.missing_evidence,
        "contradictions": run.contradictions,
        "confidence_limitations": ["Day 24 ML evidence remains pipeline-validation-only."],
        "research_only": True,
    }


@router.post("/rankings/build")
def build_ranking(body: RankingBuild, session: Session = Depends(get_db)) -> dict[str, object]:
    with session.begin():
        run = StockIntelligenceService(session).build_ranking(
            body.as_of_date, body.actor_user_id, body.stock_listing_ids
        )
    return ranking_payload(session, run)


@router.get("/rankings/{ranking_run_id}")
def get_ranking(
    ranking_run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    CreditRagIndexService(session)._user(actor_user_id)
    run = session.get(StockRankingRun, ranking_run_id)
    if run is None:
        raise AppError("STOCK_RANKING_NOT_FOUND", "Stock ranking not found", 404)
    return ranking_payload(session, run)


@router.get("/rankings/{ranking_run_id}/watchlist")
def get_watchlist(
    ranking_run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        members = StockIntelligenceService(session).build_watchlist(ranking_run_id, actor_user_id)
    return {
        "ranking_run_id": ranking_run_id,
        "entries": [
            {
                "stock_intelligence_run_id": member.stock_intelligence_run_id,
                "listed_company_id": member.listed_company_id,
                "stock_listing_id": member.stock_listing_id,
                "research_priority": member.research_priority,
                "score": member.score,
                "confidence": member.confidence,
                "coverage": member.coverage,
                "rank": member.rank,
                "percentile": member.percentile,
            }
            for member in members
        ],
        "research_only": True,
        "disclaimer": (
            "Stock Intelligence Scores and rankings are analytical research tools only. "
            "They are not investment recommendations and do not predict guaranteed "
            "future returns."
        ),
    }
