from __future__ import annotations

import json
import math
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.stock_validation import router as stock_validation_router
from app.models.audit_log import AuditLog
from app.models.stock_ml import StockMLDataset, StockMLDatasetRow, StockMLPrediction, StockMLRun
from app.models.stock_validation import (
    StockIntelligenceAblationMetric,
    StockIntelligenceComponentCorrelation,
    StockIntelligenceComponentValidation,
    StockIntelligenceSegmentValidation,
    StockIntelligenceSensitivityRun,
    StockIntelligenceValidationBucket,
    StockIntelligenceValidationMember,
    StockIntelligenceValidationPeriod,
)
from app.services.stock_validation.service import StockIntelligenceValidationService
from app.services.stock_validation.statistics import monotonicity, quantile_buckets, spearman
from tests.test_day25_stock_intelligence import _day25_context


def test_day26_statistics_are_deterministic_and_small_universes_are_honest() -> None:
    values = [Decimal("1"), Decimal("2"), Decimal("2"), Decimal("4")]
    assert spearman(values, values) == Decimal("1.0")
    assert spearman(values, list(reversed(values))) == Decimal("-1.0")
    quintiles = quantile_buckets([Decimal(index) for index in range(10)], "QUINTILE")
    assert [bucket.name for bucket in quintiles] == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert [len(bucket.indexes) for bucket in quintiles] == [2, 2, 2, 2, 2]
    terciles = quantile_buckets([Decimal(index) for index in range(7)], "TERCILE")
    assert [bucket.name for bucket in terciles] == ["T1", "T2", "T3"]
    assert monotonicity([Decimal("1"), Decimal("2"), Decimal("3")]) == (
        Decimal("1"),
        "STRONG",
    )
    assert monotonicity([]) == (None, "INSUFFICIENT_DATA")


def test_day26_full_validation_ablation_sensitivity_and_immutability(
    db_session: Session,
) -> None:
    admin, _, dates, _, _, _, _ = _day25_context(db_session)
    day24_counts = (
        db_session.scalar(select(func.count()).select_from(StockMLDataset)),
        db_session.scalar(select(func.count()).select_from(StockMLDatasetRow)),
        db_session.scalar(select(func.count()).select_from(StockMLRun)),
        db_session.scalar(select(func.count()).select_from(StockMLPrediction)),
    )
    label_snapshot = list(
        db_session.execute(
            select(
                StockMLDatasetRow.id,
                StockMLDatasetRow.relative_return,
                StockMLDatasetRow.label_class,
                StockMLDatasetRow.eligibility_status,
            ).order_by(StockMLDatasetRow.id)
        )
    )
    policy_path = (
        Path(__file__).parents[1]
        / "app/services/stock_intelligence/stock_intelligence_fusion_policy_v1.json"
    )
    day25_policy_before = json.loads(policy_path.read_text(encoding="utf-8"))

    service = StockIntelligenceValidationService(db_session)
    run = service.build_validation(dates[0], dates[-1], admin.id)
    repeated = service.build_validation(dates[0], dates[-1], admin.id)
    assert repeated.id == run.id
    assert run.validation_version == "stock_intelligence_validation_v1"
    assert run.validation_policy_version == "stock_intelligence_validation_policy_v1"
    assert run.label_policy_version == "stock_label_policy_v1"
    assert run.status == "COMPLETED"
    assert run.result_status == "RESEARCH_DIAGNOSTICS_AVAILABLE"
    assert run.historical_date_count >= 3
    assert run.eligible_row_count >= 30
    assert run.censored_row_count > 0
    assert service.validate_lineage(run.id)

    periods = list(
        db_session.scalars(
            select(StockIntelligenceValidationPeriod).where(
                StockIntelligenceValidationPeriod.validation_run_id == run.id
            )
        )
    )
    assert len(periods) == run.historical_date_count
    members = list(
        db_session.scalars(
            select(StockIntelligenceValidationMember).where(
                StockIntelligenceValidationMember.validation_run_id == run.id
            )
        )
    )
    assert len(members) == run.eligible_row_count
    assert all(
        member.score is not None
        and member.confidence is not None
        and member.coverage is not None
        and member.rank > 0
        and member.label_status == "LABELED"
        for member in members
    )
    assert all(period.bucket_method in {"QUINTILE", "TERCILE"} for period in periods)
    buckets = list(
        db_session.scalars(
            select(StockIntelligenceValidationBucket)
            .join(StockIntelligenceValidationPeriod)
            .where(StockIntelligenceValidationPeriod.validation_run_id == run.id)
        )
    )
    assert buckets and {bucket.bucket_name for bucket in buckets} >= {"Q1", "Q5"}
    assert all(bucket.company_count >= 2 for bucket in buckets)
    components = list(
        db_session.scalars(
            select(StockIntelligenceComponentValidation).where(
                StockIntelligenceComponentValidation.validation_run_id == run.id
            )
        )
    )
    correlations = list(
        db_session.scalars(
            select(StockIntelligenceComponentCorrelation).where(
                StockIntelligenceComponentCorrelation.validation_run_id == run.id
            )
        )
    )
    assert len(components) == 11
    assert len(correlations) == 55
    assert {item.redundancy_status for item in correlations} <= {
        "LOW",
        "MODERATE",
        "HIGH",
        "INSUFFICIENT_DATA",
    }
    segments = list(
        db_session.scalars(
            select(StockIntelligenceSegmentValidation).where(
                StockIntelligenceSegmentValidation.validation_run_id == run.id
            )
        )
    )
    assert {item.segment_type for item in segments} >= {
        "CONFIDENCE",
        "COVERAGE",
        "SECTOR",
        "WATCHLIST",
        "CONTRADICTION",
    }
    assert (
        next(
            item
            for item in segments
            if item.segment_type == "CONFIDENCE" and item.segment_value == "LOW"
        ).status
        == "INSUFFICIENT_DATA"
    )
    assert all(
        item.status == "INSUFFICIENT_DATA"
        for item in segments
        if item.segment_type == "SECTOR"
        and item.spearman is None
        and item.top_bottom_spread is None
    )
    watchlist_segments = [item for item in segments if item.segment_type == "WATCHLIST"]
    assert len(watchlist_segments) == 3
    assert all(
        item.mean_relative_return is not None for item in watchlist_segments if item.sample_count
    )

    ablations = service.run_ablation(run.id, admin.id)
    repeated_ablations = service.run_ablation(run.id, admin.id)
    assert [item.id for item in repeated_ablations] == [item.id for item in ablations]
    names = {item.experiment_name for item in ablations}
    assert {
        "NO_ML",
        "RULE_ONLY",
        "NO_VALUATION",
        "NO_FUNDAMENTAL_QUALITY",
        "NO_GROWTH",
        "NO_PROFITABILITY",
        "NO_BALANCE_SHEET",
        "NO_MOMENTUM",
        "NO_RISK",
        "NO_PEER_RELATIVE",
        "NO_SECTOR_RELATIVE",
        "NO_DATA_QUALITY",
        "ML_ONLY",
        "MOMENTUM_ONLY",
        "VALUATION_ONLY",
        "FUNDAMENTAL_ONLY",
    } == names
    for item in ablations:
        assert math.isclose(sum(item.weights_json.values()), 100.0, abs_tol=1e-8)
    metrics = list(
        db_session.scalars(
            select(StockIntelligenceAblationMetric).where(
                StockIntelligenceAblationMetric.ablation_run_id.in_([item.id for item in ablations])
            )
        )
    )
    assert metrics

    sensitivity = service.run_sensitivity(run.id, admin.id)
    repeated_sensitivity = service.run_sensitivity(run.id, admin.id)
    assert [item.id for item in repeated_sensitivity] == [item.id for item in sensitivity]
    assert len(sensitivity) == 6
    assert all(
        math.isclose(sum(item.weights_json.values()), 100.0, abs_tol=1e-8) for item in sensitivity
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(StockIntelligenceSensitivityRun)
            .where(StockIntelligenceSensitivityRun.validation_run_id == run.id)
        )
        == 6
    )

    changed_label = db_session.scalar(
        select(StockMLDatasetRow)
        .where(
            StockMLDatasetRow.eligibility_status == "LABELED",
            StockMLDatasetRow.relative_return.is_not(None),
        )
        .order_by(StockMLDatasetRow.as_of_date, StockMLDatasetRow.id)
    )
    assert changed_label is not None and changed_label.relative_return is not None
    original_relative_return = changed_label.relative_return
    changed_label.relative_return += Decimal("0.0001")
    changed_run = service.build_validation(dates[0], dates[-1], admin.id)
    assert changed_run.id != run.id
    changed_label.relative_return = original_relative_return

    assert day24_counts == (
        db_session.scalar(select(func.count()).select_from(StockMLDataset)),
        db_session.scalar(select(func.count()).select_from(StockMLDatasetRow)),
        db_session.scalar(select(func.count()).select_from(StockMLRun)),
        db_session.scalar(select(func.count()).select_from(StockMLPrediction)),
    )
    assert label_snapshot == list(
        db_session.execute(
            select(
                StockMLDatasetRow.id,
                StockMLDatasetRow.relative_return,
                StockMLDatasetRow.label_class,
                StockMLDatasetRow.eligibility_status,
            ).order_by(StockMLDatasetRow.id)
        )
    )
    assert json.loads(policy_path.read_text(encoding="utf-8")) == day25_policy_before
    audit_events = set(
        db_session.scalars(
            select(AuditLog.event_type).where(
                AuditLog.event_type.in_(
                    {
                        "STOCK_INTELLIGENCE_VALIDATION_BUILT",
                        "STOCK_INTELLIGENCE_VALIDATION_REUSED",
                        "STOCK_INTELLIGENCE_ABLATION_BUILT",
                        "STOCK_INTELLIGENCE_SENSITIVITY_BUILT",
                    }
                )
            )
        )
    )
    assert audit_events == {
        "STOCK_INTELLIGENCE_VALIDATION_BUILT",
        "STOCK_INTELLIGENCE_VALIDATION_REUSED",
        "STOCK_INTELLIGENCE_ABLATION_BUILT",
        "STOCK_INTELLIGENCE_SENSITIVITY_BUILT",
    }


def test_day26_routes_and_status(client: TestClient) -> None:
    paths = {route.path for route in stock_validation_router.routes if hasattr(route, "path")}
    assert {
        "/stock-validation/runs/build",
        "/stock-validation/runs/{validation_run_id}",
        "/stock-validation/runs",
        "/stock-validation/runs/{validation_run_id}/periods",
        "/stock-validation/runs/{validation_run_id}/buckets",
        "/stock-validation/runs/{validation_run_id}/components",
        "/stock-validation/runs/{validation_run_id}/correlations",
        "/stock-validation/runs/{validation_run_id}/ablations/build",
        "/stock-validation/runs/{validation_run_id}/ablations",
        "/stock-validation/runs/{validation_run_id}/sensitivity/build",
        "/stock-validation/runs/{validation_run_id}/sensitivity",
        "/stock-validation/runs/{validation_run_id}/segments",
    } <= paths
    status = client.get("/api/v1/status").json()
    assert status["development_stage"] == {
        "day": 28,
        "name": "360° Company Intelligence Report",
    }
    assert status["components"]["historical_stock_score_validation"] in {
        "ready",
        "unavailable",
    }
    assert status["components"]["trade_execution"] == "disabled"
