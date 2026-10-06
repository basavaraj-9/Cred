from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.stock_monitoring import (
    StockComponentMonitoring,
    StockFeatureDrift,
    StockGovernanceAssessment,
    StockModelMonitoring,
    StockMonitoringFinding,
    StockMonitoringRun,
    StockProviderMonitoring,
    StockRankingMonitoring,
    StockScoreMonitoring,
)
from app.services.stock.authorization import require_stock_actor
from app.services.stock_monitoring.service import StockMonitoringService

router = APIRouter(prefix="/stock-monitoring", tags=["stock monitoring"])


class MonitoringBuild(BaseModel):
    actor_user_id: UUID
    reference_start_date: date
    reference_end_date: date
    current_start_date: date
    current_end_date: date


def _run(session: Session, run_id: UUID) -> StockMonitoringRun:
    run = session.get(StockMonitoringRun, run_id)
    if run is None:
        raise AppError("STOCK_MONITORING_NOT_FOUND", "Stock monitoring run not found", 404)
    return run


def run_payload(run: StockMonitoringRun) -> dict[str, object]:
    return {
        "id": run.id,
        "monitoring_version": run.monitoring_version,
        "drift_policy_version": run.drift_policy_version,
        "governance_policy_version": run.governance_policy_version,
        "window_policy_version": run.window_policy_version,
        "recalibration_readiness_version": run.recalibration_readiness_version,
        "reference_start_date": run.reference_start_date,
        "reference_end_date": run.reference_end_date,
        "current_start_date": run.current_start_date,
        "current_end_date": run.current_end_date,
        "reference_universe_hash": run.reference_universe_hash,
        "current_universe_hash": run.current_universe_hash,
        "changed_member_count": run.changed_member_count,
        "comparability_status": run.comparability_status,
        "status": run.status,
        "overall_health_status": run.overall_health_status,
        "recalibration_readiness_status": run.recalibration_readiness_status,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "research_only": True,
        "automatic_action": False,
    }


@router.post("/runs/build")
def build(body: MonitoringBuild, session: Session = Depends(get_db)) -> dict[str, object]:
    with session.begin():
        run = StockMonitoringService(session).build_monitoring_run(
            body.reference_start_date,
            body.reference_end_date,
            body.current_start_date,
            body.current_end_date,
            body.actor_user_id,
        )
    return run_payload(run)


@router.get("/runs")
def list_runs(
    actor_user_id: UUID,
    status: str | None = None,
    health: str | None = None,
    readiness: str | None = None,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    require_stock_actor(session, actor_user_id)
    query = select(StockMonitoringRun)
    if status:
        query = query.where(StockMonitoringRun.status == status)
    if health:
        query = query.where(StockMonitoringRun.overall_health_status == health)
    if readiness:
        query = query.where(StockMonitoringRun.recalibration_readiness_status == readiness)
    return [
        run_payload(item)
        for item in session.scalars(query.order_by(StockMonitoringRun.created_at.desc()))
    ]


@router.get("/runs/{run_id}")
def get_run(
    run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    require_stock_actor(session, actor_user_id)
    return run_payload(_run(session, run_id))


def _rows(
    session: Session,
    run_id: UUID,
    actor_user_id: UUID,
    model: Any,
) -> list[dict[str, object]]:
    require_stock_actor(session, actor_user_id)
    _run(session, run_id)
    items: list[Any] = list(session.scalars(select(model).where(model.monitoring_run_id == run_id)))
    return [
        {
            column.name: getattr(item, column.name)
            for column in item.__table__.columns
            if column.name != "monitoring_run_id"
        }
        for item in items
    ]


@router.get("/runs/{run_id}/findings")
def findings(run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)):
    return _rows(session, run_id, actor_user_id, StockMonitoringFinding)


@router.get("/runs/{run_id}/features")
def features(run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)):
    return _rows(session, run_id, actor_user_id, StockFeatureDrift)


@router.get("/runs/{run_id}/models")
def models(run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)):
    return _rows(session, run_id, actor_user_id, StockModelMonitoring)


@router.get("/runs/{run_id}/scores")
def scores(run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)):
    return _rows(session, run_id, actor_user_id, StockScoreMonitoring)


@router.get("/runs/{run_id}/components")
def components(run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)):
    return _rows(session, run_id, actor_user_id, StockComponentMonitoring)


@router.get("/runs/{run_id}/rankings")
def rankings(run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)):
    return _rows(session, run_id, actor_user_id, StockRankingMonitoring)


@router.get("/runs/{run_id}/providers")
def providers(run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)):
    return _rows(session, run_id, actor_user_id, StockProviderMonitoring)


@router.get("/runs/{run_id}/governance")
def governance(run_id: UUID, actor_user_id: UUID, session: Session = Depends(get_db)):
    rows = _rows(session, run_id, actor_user_id, StockGovernanceAssessment)
    if not rows:
        raise AppError("STOCK_GOVERNANCE_NOT_FOUND", "Governance assessment not found", 404)
    return rows[0]
