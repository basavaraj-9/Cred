from __future__ import annotations

# ruff: noqa: E501
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.stock import (
    ListedCompany,
    PeerGroup,
    PeerGroupMember,
    StockListing,
    StockPrice,
)
from app.services.stock.authorization import require_stock_actor
from app.services.stock.service import MarketDataService, PeerDiscoveryService, StockUniverseService

router = APIRouter(tags=["stock intelligence foundation"])


class ActorRequest(BaseModel):
    actor_user_id: UUID


class UniverseSyncRequest(ActorRequest):
    exchange: str | None = None
    provider: str | None = None


class PeerRequest(ActorRequest):
    max_peers: int | None = Field(default=None, ge=1, le=50)


class MarketSyncRequest(ActorRequest):
    exchange: str | None = None
    symbols: list[str] | None = None
    start_date: date
    end_date: date
    provider: str | None = None


def peer_payload(session: Session, group: PeerGroup) -> dict[str, object]:
    members = list(
        session.scalars(
            select(PeerGroupMember)
            .where(PeerGroupMember.peer_group_id == group.id)
            .order_by(PeerGroupMember.rank)
        )
    )
    companies = (
        {
            x.id: x
            for x in session.scalars(
                select(ListedCompany).where(
                    ListedCompany.id.in_([m.listed_company_id for m in members])
                )
            )
        }
        if members
        else {}
    )
    listings = (
        {
            x.id: x
            for x in session.scalars(
                select(StockListing).where(
                    StockListing.id.in_([m.stock_listing_id for m in members if m.stock_listing_id])
                )
            )
        }
        if members
        else {}
    )
    return {
        "peer_group_id": group.id,
        "document_id": group.document_id,
        "status": group.status,
        "policy_version": group.policy_version,
        "engine_version": group.engine_version,
        "universe_version": group.universe_version,
        "universe_snapshot_hash": group.universe_snapshot_hash,
        "peers": [
            {
                "rank": m.rank,
                "company_id": m.listed_company_id,
                "company_name": companies[m.listed_company_id].canonical_name,
                "listing_id": m.stock_listing_id,
                "exchange": listings[m.stock_listing_id].exchange if m.stock_listing_id else None,
                "symbol": listings[m.stock_listing_id].symbol if m.stock_listing_id else None,
                "similarity_score": m.similarity_score,
                "components": {
                    "sector": m.sector_score,
                    "industry": m.industry_score,
                    "domain": m.domain_score,
                    "sub_domain": m.sub_domain_score,
                    "business_similarity": m.business_similarity_score,
                    "product_overlap": m.product_overlap_score,
                },
                "status": m.status,
                "review_required": m.review_required,
                "rationale": m.rationale_json,
                "market_data": {
                    "status": listings[m.stock_listing_id].price_data_status
                    if m.stock_listing_id
                    else "MISSING",
                    "latest_date": listings[m.stock_listing_id].last_price_date
                    if m.stock_listing_id
                    else None,
                },
            }
            for m in members
        ],
        "disclaimer": "Peer similarity identifies business comparability only. It is not an investment recommendation, valuation conclusion, return forecast, or BUY/SELL/HOLD signal.",
    }


@router.post("/stock-universe/sync")
def sync_universe(
    body: UniverseSyncRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        return StockUniverseService(session).sync(body.actor_user_id, body.exchange)


@router.get("/stock-universe")
def list_universe(
    actor_user_id: UUID,
    exchange: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    domain: str | None = None,
    sub_domain: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    require_stock_actor(session, actor_user_id)
    query = select(ListedCompany, StockListing).join(StockListing)
    if exchange:
        query = query.where(StockListing.exchange == exchange)
    if sector:
        query = query.where(ListedCompany.sector == sector)
    if industry:
        query = query.where(ListedCompany.industry == industry)
    if domain:
        query = query.where(ListedCompany.domain == domain)
    if sub_domain:
        query = query.where(ListedCompany.sub_domain == sub_domain)
    if status:
        query = query.where(StockListing.listing_status == status)
    return [
        {
            "company_id": c.id,
            "company_name": c.canonical_name,
            "isin": c.isin,
            "sector": c.sector,
            "industry": c.industry,
            "domain": c.domain,
            "sub_domain": c.sub_domain,
            "exchange": listing.exchange,
            "symbol": listing.symbol,
            "listing_status": listing.listing_status,
            "security_type": listing.security_type,
            "is_primary": listing.is_primary,
            "market_data_status": listing.price_data_status,
        }
        for c, listing in session.execute(
            query.order_by(ListedCompany.canonical_name, StockListing.exchange)
        )
    ]


@router.get("/stock-universe/{company_id}")
def get_company(
    company_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    require_stock_actor(session, actor_user_id)
    company = session.get(ListedCompany, company_id)
    if company is None:
        raise AppError("LISTED_COMPANY_NOT_FOUND", "Listed company not found", 404)
    listings = list(
        session.scalars(
            select(StockListing)
            .where(StockListing.listed_company_id == company.id)
            .order_by(desc(StockListing.is_primary))
        )
    )
    return {
        "company": {
            "id": company.id,
            "canonical_name": company.canonical_name,
            "legal_name": company.legal_name,
            "isin": company.isin,
            "website": company.website,
        },
        "classification": {
            "sector": company.sector,
            "industry": company.industry,
            "domain": company.domain,
            "sub_domain": company.sub_domain,
            "status": company.classification_status,
        },
        "listings": [
            {
                "id": x.id,
                "exchange": x.exchange,
                "symbol": x.symbol,
                "status": x.listing_status,
                "security_type": x.security_type,
                "currency": x.currency,
                "is_primary": x.is_primary,
                "market_data_status": x.price_data_status,
                "last_price_date": x.last_price_date,
            }
            for x in listings
        ],
    }


@router.post("/documents/{document_id}/peers/discover")
def discover(
    document_id: UUID, body: PeerRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        group = PeerDiscoveryService(session).discover(
            document_id, body.actor_user_id, body.max_peers
        )
    return peer_payload(session, group)


@router.get("/documents/{document_id}/peers")
def get_peers(
    document_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    require_stock_actor(session, actor_user_id)
    group = session.scalar(
        select(PeerGroup)
        .where(PeerGroup.document_id == document_id)
        .order_by(desc(PeerGroup.created_at))
        .limit(1)
    )
    if group is None:
        raise AppError("PEER_GROUP_NOT_FOUND", "Peer group not found", 404)
    return peer_payload(session, group)


@router.get("/peer-groups/{group_id}")
def get_peer_group(
    group_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    require_stock_actor(session, actor_user_id)
    group = session.get(PeerGroup, group_id)
    if group is None:
        raise AppError("PEER_GROUP_NOT_FOUND", "Peer group not found", 404)
    return peer_payload(session, group)


@router.post("/market-data/sync")
def sync_market(body: MarketSyncRequest, session: Session = Depends(get_db)) -> dict[str, object]:
    if body.end_date < body.start_date:
        raise AppError("DATE_RANGE_INVALID", "end_date must be on or after start_date", 422)
    with session.begin():
        run = MarketDataService(session).sync(
            body.actor_user_id, body.start_date, body.end_date, body.exchange, body.symbols
        )
    return {
        "run_id": run.id,
        "provider": run.provider,
        "provider_version": run.provider_version,
        "status": run.status,
        "symbol_count": run.symbol_count,
        "success_count": run.success_count,
        "failure_count": run.failure_count,
        "start_date": run.start_date,
        "end_date": run.end_date,
    }


@router.get("/stocks/{listing_id}/prices")
def prices(
    listing_id: UUID,
    actor_user_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    require_stock_actor(session, actor_user_id)
    query = select(StockPrice).where(StockPrice.stock_listing_id == listing_id)
    if start_date:
        query = query.where(StockPrice.trade_date >= start_date)
    if end_date:
        query = query.where(StockPrice.trade_date <= end_date)
    return [
        {
            "trade_date": x.trade_date,
            "open": x.open,
            "high": x.high,
            "low": x.low,
            "close": x.close,
            "adjusted_close": x.adjusted_close,
            "volume": x.volume,
            "currency": x.currency,
            "provider": x.provider,
            "provider_version": x.provider_version,
            "is_adjusted": x.is_adjusted,
        }
        for x in session.scalars(query.order_by(StockPrice.trade_date))
    ]


@router.get("/stocks/{listing_id}/market-data-status")
def market_status(
    listing_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    require_stock_actor(session, actor_user_id)
    listing = session.get(StockListing, listing_id)
    if listing is None:
        raise AppError("STOCK_LISTING_NOT_FOUND", "Stock listing not found", 404)
    count = (
        session.scalar(
            select(func.count())
            .select_from(StockPrice)
            .where(StockPrice.stock_listing_id == listing.id)
        )
        or 0
    )
    latest = session.scalar(
        select(StockPrice)
        .where(StockPrice.stock_listing_id == listing.id)
        .order_by(desc(StockPrice.trade_date))
        .limit(1)
    )
    return {
        "listing_id": listing.id,
        "exchange": listing.exchange,
        "symbol": listing.symbol,
        "latest_date": listing.last_price_date,
        "coverage_rows": count,
        "freshness": listing.price_data_status,
        "provider": latest.provider if latest else None,
        "latest_close": latest.close if latest else None,
        "currency": listing.currency,
    }
