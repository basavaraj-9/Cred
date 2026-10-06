from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.stock_analytics import (
    SectorMetric,
    SectorMetricRun,
    StockFeature,
    StockFeatureRun,
    StockFundamental,
    StockFundamentalRun,
    StockValuation,
    StockValuationRun,
)
from app.services.stock.authorization import require_stock_actor
from app.services.stock_analytics.service import (
    FeatureService,
    FundamentalService,
    RelativeMetricService,
    ValuationService,
)

router = APIRouter(tags=["stock fundamentals and features"])


class Actor(BaseModel):
    actor_user_id: UUID


class FundamentalSync(Actor):
    listed_company_ids: list[UUID] | None = None
    provider: str | None = None


class DateAction(Actor):
    as_of_date: date
    sector: str | None = None
    industry: str | None = None


class ValuationAction(Actor):
    valuation_date: date


@router.post("/stock-fundamentals/sync")
def sync_fundamentals(
    body: FundamentalSync, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        count = FundamentalService(session).sync(body.actor_user_id, body.listed_company_ids)
    return {
        "provider": "development_fixture_fundamentals_provider",
        "provider_version": "fixture_fundamentals_v1",
        "companies_synced": count,
    }


@router.get("/stocks/{company_id}/fundamentals")
def fundamentals(
    company_id: UUID,
    actor_user_id: UUID,
    period: str | None = None,
    scope: str | None = None,
    metric: str | None = None,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    require_stock_actor(session, actor_user_id)
    q = (
        select(StockFundamental, StockFundamentalRun)
        .join(StockFundamentalRun)
        .where(StockFundamental.listed_company_id == company_id)
    )
    if period:
        q = q.where(StockFundamentalRun.reporting_period == period)
    if scope:
        q = q.where(StockFundamental.statement_scope == scope)
    if metric:
        q = q.where(StockFundamental.metric_code == metric)
    return [
        {
            "id": x.id,
            "run_id": r.id,
            "metric_code": x.metric_code,
            "value": x.value,
            "unit": x.unit,
            "currency": x.currency,
            "period": r.reporting_period,
            "period_end": x.period_end,
            "availability_date": x.availability_date,
            "scope": x.statement_scope,
            "provenance": x.provenance_type,
            "provider": x.source_provider,
            "status": x.status,
        }
        for x, r in session.execute(
            q.order_by(desc(StockFundamental.period_end), StockFundamental.metric_code)
        )
    ]


@router.post("/stocks/{listing_id}/valuations/build")
def build_valuation(
    listing_id: UUID, body: ValuationAction, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        run = ValuationService(session).build(listing_id, body.valuation_date, body.actor_user_id)
    return valuation_payload(session, run)


def valuation_payload(session: Session, run: StockValuationRun) -> dict[str, object]:
    metrics = list(
        session.scalars(
            select(StockValuation)
            .where(StockValuation.valuation_run_id == run.id)
            .order_by(StockValuation.metric_code)
        )
    )
    return {
        "run_id": run.id,
        "listing_id": run.stock_listing_id,
        "valuation_date": run.valuation_date,
        "status": run.status,
        "policy_version": run.policy_version,
        "engine_version": run.engine_version,
        "price_record_id": run.price_record_id,
        "fundamental_run_id": run.fundamental_run_id,
        "metrics": [
            {
                "code": x.metric_code,
                "value": x.value,
                "status": x.status,
                "formula_version": x.formula_version,
            }
            for x in metrics
        ],
    }


@router.get("/stocks/{listing_id}/valuations")
def valuations(
    listing_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    require_stock_actor(session, actor_user_id)
    return [
        valuation_payload(session, x)
        for x in session.scalars(
            select(StockValuationRun)
            .where(StockValuationRun.stock_listing_id == listing_id)
            .order_by(desc(StockValuationRun.valuation_date))
        )
    ]


@router.post("/sector-metrics/build")
def build_relative(body: DateAction, session: Session = Depends(get_db)) -> dict[str, object]:
    with session.begin():
        runs = RelativeMetricService(session).build(
            body.as_of_date,
            body.actor_user_id,
            sector=body.sector,
            industry=body.industry,
        )
    return {"as_of_date": body.as_of_date, "run_count": len(runs)}


@router.get("/stocks/{company_id}/relative-metrics")
def relative(
    company_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    require_stock_actor(session, actor_user_id)
    q = (
        select(SectorMetric, SectorMetricRun)
        .join(SectorMetricRun)
        .where(SectorMetric.listed_company_id == company_id)
    )
    return [
        {
            "group_type": r.group_type,
            "group": r.domain or r.industry or r.sector,
            "as_of_date": r.as_of_date,
            "metric_code": x.metric_code,
            "value": x.raw_value,
            "percentile": x.percentile,
            "z_score": x.z_score,
            "rank": x.rank,
            "group_size": x.eligible_company_count,
            "status": x.status,
        }
        for x, r in session.execute(
            q.order_by(desc(SectorMetricRun.as_of_date), SectorMetric.metric_code)
        )
    ]


@router.post("/stocks/{listing_id}/features/build")
def build_features(
    listing_id: UUID, body: DateAction, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        run = FeatureService(session).build(listing_id, body.as_of_date, body.actor_user_id)
    return feature_payload(session, run)


def feature_payload(
    session: Session, run: StockFeatureRun, group: str | None = None
) -> dict[str, object]:
    q = select(StockFeature).where(StockFeature.feature_run_id == run.id)
    if group:
        q = q.where(StockFeature.feature_group == group)
    return {
        "run_id": run.id,
        "listing_id": run.stock_listing_id,
        "as_of_date": run.as_of_date,
        "feature_set_version": run.feature_set_version,
        "status": run.status,
        "features": [
            {
                "name": x.feature_name,
                "group": x.feature_group,
                "value": x.value,
                "status": x.status,
                "source_count": x.source_count,
            }
            for x in session.scalars(
                q.order_by(StockFeature.feature_group, StockFeature.feature_name)
            )
        ],
    }


@router.get("/stocks/{listing_id}/features")
def features(
    listing_id: UUID,
    actor_user_id: UUID,
    as_of_date: date | None = None,
    feature_group: str | None = None,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    require_stock_actor(session, actor_user_id)
    q = select(StockFeatureRun).where(StockFeatureRun.stock_listing_id == listing_id)
    if as_of_date:
        q = q.where(StockFeatureRun.as_of_date == as_of_date)
    return [
        feature_payload(session, x, feature_group)
        for x in session.scalars(q.order_by(desc(StockFeatureRun.as_of_date)))
    ]
