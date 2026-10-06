from __future__ import annotations

import math
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.stock_monitoring import router as stock_monitoring_router
from app.models.audit_log import AuditLog
from app.models.stock_intelligence import StockIntelligenceRun
from app.models.stock_ml import StockMLPrediction
from app.models.stock_monitoring import (
    StockComponentMonitoring,
    StockFeatureDrift,
    StockGovernanceAssessment,
    StockModelMonitoring,
    StockMonitoringFinding,
    StockProviderMonitoring,
    StockRankingMonitoring,
    StockScoreMonitoring,
)
from app.models.stock_validation import StockIntelligenceValidationRun
from app.services.stock_monitoring.psi import population_stability_index
from app.services.stock_monitoring.service import StockMonitoringService
from app.services.stock_validation.service import StockIntelligenceValidationService
from tests.test_day25_stock_intelligence import _day25_context


def test_psi_identical_distribution_and_zero_bins_are_stable() -> None:
    values = [float(index) for index in range(20)]
    result = population_stability_index(values, values)
    assert result.status == "AVAILABLE"
    assert result.value == 0
    zeros = population_stability_index(
        values,
        [value + 100.0 for value in values],
        epsilon=0.000001,
    )
    assert zeros.status == "AVAILABLE"
    assert zeros.value is not None and math.isfinite(zeros.value) and zeros.value > 0


def test_psi_shift_constant_and_small_sample_guards() -> None:
    shifted = population_stability_index(
        [float(index) for index in range(20)],
        [float(index + 8) for index in range(20)],
    )
    assert shifted.value is not None and shifted.value > 0.1
    assert population_stability_index([1.0] * 20, [2.0] * 20).status == ("INSUFFICIENT_VARIATION")
    tiny = population_stability_index([1.0, 2.0], [3.0, 4.0])
    assert tiny.value is None and tiny.status == "INSUFFICIENT_DATA"


def test_day27_monitoring_governance_idempotency_and_upstream_immutability(
    db_session: Session,
) -> None:
    admin, _, dates, _, _, _, _ = _day25_context(db_session)
    validation = StockIntelligenceValidationService(db_session).build_validation(
        dates[0], dates[-1], admin.id
    )
    before = (
        db_session.scalar(select(func.count()).select_from(StockMLPrediction)),
        db_session.scalar(select(func.count()).select_from(StockIntelligenceRun)),
        db_session.scalar(select(func.count()).select_from(StockIntelligenceValidationRun)),
    )
    service = StockMonitoringService(db_session)
    run = service.build_monitoring_run(dates[0], dates[2], dates[3], dates[-1], admin.id)
    repeated = service.build_monitoring_run(dates[0], dates[2], dates[3], dates[-1], admin.id)
    assert repeated.id == run.id
    assert run.monitoring_version == "stock_monitoring_v1"
    assert run.drift_policy_version == "stock_drift_policy_v1"
    assert run.governance_policy_version == "stock_model_governance_policy_v1"
    assert run.recalibration_readiness_version == "stock_recalibration_readiness_v1"
    assert run.status in {"COMPLETED", "INSUFFICIENT_DATA"}
    assert run.overall_health_status in {
        "HEALTHY",
        "WATCH",
        "REVIEW_REQUIRED",
        "INSUFFICIENT_DATA",
    }
    assert run.recalibration_readiness_status in {
        "NOT_INDICATED",
        "MONITOR",
        "RESEARCH_REVIEW_RECOMMENDED",
        "INSUFFICIENT_DATA",
    }

    findings = list(
        db_session.scalars(
            select(StockMonitoringFinding).where(StockMonitoringFinding.monitoring_run_id == run.id)
        )
    )
    assert {item.category for item in findings} >= {
        "DATA_FRESHNESS",
        "FEATURE_DRIFT",
        "FEATURE_AVAILABILITY",
        "PREDICTION_DRIFT",
        "SCORE_DRIFT",
        "COMPONENT_DRIFT",
        "CONFIDENCE_DRIFT",
        "COVERAGE_DRIFT",
        "RANKING_STABILITY",
        "UNIVERSE_CHANGE",
        "LABEL_DISTRIBUTION_DRIFT",
        "MODEL_DIAGNOSTIC_DRIFT",
    }
    feature_rows = list(
        db_session.scalars(
            select(StockFeatureDrift).where(StockFeatureDrift.monitoring_run_id == run.id)
        )
    )
    assert feature_rows
    assert all(item.psi is None or item.psi.is_finite() for item in feature_rows)
    models = list(
        db_session.scalars(
            select(StockModelMonitoring).where(StockModelMonitoring.monitoring_run_id == run.id)
        )
    )
    assert models
    assert all(
        item.reference_probability_median is not None
        and item.current_probability_median is not None
        and item.reference_probability_min is not None
        and item.current_probability_max is not None
        for item in models
        if item.status == "AVAILABLE"
    )
    score_monitoring = db_session.scalar(
        select(StockScoreMonitoring).where(StockScoreMonitoring.monitoring_run_id == run.id)
    )
    assert score_monitoring is not None
    assert score_monitoring.reference_median is not None
    assert score_monitoring.current_median is not None
    assert score_monitoring.confidence_reference_below_rate is not None
    assert score_monitoring.coverage_current_below_rate is not None
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(StockScoreMonitoring)
            .where(StockScoreMonitoring.monitoring_run_id == run.id)
        )
        == 1
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(StockComponentMonitoring)
            .where(StockComponentMonitoring.monitoring_run_id == run.id)
        )
        == 11
    )
    ranking = db_session.scalar(
        select(StockRankingMonitoring).where(StockRankingMonitoring.monitoring_run_id == run.id)
    )
    assert ranking is not None
    if ranking.status == "AVAILABLE":
        assert ranking.rank_spearman is not None
        assert ranking.top_k_overlap is not None
        assert ranking.turnover == Decimal("1") - ranking.top_k_overlap
        assert ranking.mean_absolute_rank_change is not None
    providers = list(
        db_session.scalars(
            select(StockProviderMonitoring).where(
                StockProviderMonitoring.monitoring_run_id == run.id
            )
        )
    )
    assert {item.provider_type for item in providers} >= {
        "MARKET",
        "FUNDAMENTAL",
        "FEATURE_STORE",
        "SCORE",
    }
    assert all(item.provider_classification == "DEVELOPMENT" for item in providers)
    governance = db_session.scalar(
        select(StockGovernanceAssessment).where(
            StockGovernanceAssessment.monitoring_run_id == run.id
        )
    )
    assert governance is not None
    assert governance.reasons_against_review
    assert "No automatic" in governance.reasons_against_review[0]
    changed_score = db_session.scalar(
        select(StockIntelligenceRun)
        .where(StockIntelligenceRun.as_of_date.between(dates[3], dates[-1]))
        .where(StockIntelligenceRun.score.is_not(None))
        .limit(1)
    )
    assert changed_score is not None and changed_score.score is not None
    original_score = changed_score.score
    changed_score.score += (
        Decimal("-0.0001") if changed_score.score == Decimal("100") else Decimal("0.0001")
    )
    changed_input_run = service.build_monitoring_run(
        dates[0], dates[2], dates[3], dates[-1], admin.id
    )
    assert changed_input_run.id != run.id
    changed_score.score = original_score
    assert before == (
        db_session.scalar(select(func.count()).select_from(StockMLPrediction)),
        db_session.scalar(select(func.count()).select_from(StockIntelligenceRun)),
        db_session.scalar(select(func.count()).select_from(StockIntelligenceValidationRun)),
    )
    changed = service.build_monitoring_run(dates[0], dates[1], dates[2], dates[-1], admin.id)
    assert changed.id != run.id
    events = set(
        db_session.scalars(
            select(AuditLog.event_type).where(
                AuditLog.event_type.in_({"STOCK_MONITORING_BUILT", "STOCK_MONITORING_REUSED"})
            )
        )
    )
    assert events == {"STOCK_MONITORING_BUILT", "STOCK_MONITORING_REUSED"}
    assert validation.status == "COMPLETED"


def test_day27_routes_and_status(client: TestClient) -> None:
    paths = {route.path for route in stock_monitoring_router.routes if hasattr(route, "path")}
    assert {
        "/stock-monitoring/runs/build",
        "/stock-monitoring/runs",
        "/stock-monitoring/runs/{run_id}",
        "/stock-monitoring/runs/{run_id}/findings",
        "/stock-monitoring/runs/{run_id}/features",
        "/stock-monitoring/runs/{run_id}/models",
        "/stock-monitoring/runs/{run_id}/scores",
        "/stock-monitoring/runs/{run_id}/components",
        "/stock-monitoring/runs/{run_id}/rankings",
        "/stock-monitoring/runs/{run_id}/providers",
        "/stock-monitoring/runs/{run_id}/governance",
    } <= paths
    status = client.get("/api/v1/status").json()
    assert status["development_stage"] == {
        "day": 29,
        "name": "Production Hardening & Deployment Readiness",
    }
    assert status["components"]["stock_monitoring"] in {"ready", "unavailable"}
    assert status["components"]["automatic_stock_retraining"] == "disabled"
    assert status["components"]["live_prediction_serving"] == "disabled"
