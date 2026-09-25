from __future__ import annotations

# ruff: noqa: E501
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.credit_fusion import (
    get_fusion_contributions,
    get_fusion_experiment,
    get_fusion_reasons,
    list_document_fusion_experiments,
)
from app.core.exceptions import AppError
from app.ml.credit.evaluate import CreditMLEvaluationService
from app.ml.credit.synthetic_fixture import create_synthetic_credit_dataset
from app.ml.credit.training import CreditMLTrainingService
from app.models.analysis_job import AnalysisJob
from app.models.credit import CreditAssessment
from app.models.credit_fusion import (
    CreditFusionContribution,
    CreditFusionExperiment,
    CreditFusionInput,
    CreditFusionReason,
)
from app.models.credit_ml import CreditMLFeatureSnapshot
from app.models.credit_ml_evaluation import CreditMLEvaluationRun
from app.models.document import Document
from app.models.enums import CreditAssessmentStatus, FinancialScope
from app.models.financial_analysis import FinancialAnalysisRun
from app.models.financial_trend import FinancialTrendRun
from app.models.ml import MLModel
from app.services.credit_fusion.confidence import fusion_confidence
from app.services.credit_fusion.diagnostics import experiment_diagnostic
from app.services.credit_fusion.policy import (
    FUSION_BAND_VERSION,
    FUSION_ENGINE_VERSION,
    FUSION_POLICY_VERSION,
    experimental_band,
    load_bands,
    load_policy,
    validate_policy,
)
from app.services.credit_fusion.readiness import CreditFusionReadinessService
from app.services.credit_fusion.service import CreditFusionService
from app.services.credit_fusion.strategies import agreement_level, consensus_gated, weighted_blend
from app.services.credit_fusion.transforms import rule_score_to_risk_index


def test_fusion_policy_loads_version_weights_bands_and_cap() -> None:
    value = load_policy()
    weighted = value["weighted_blend"]
    assert value["version"] == FUSION_POLICY_VERSION
    assert weighted["rule_weight"] + weighted["ml_weight"] == 1  # type: ignore[operator,index]
    assert load_bands()["version"] == FUSION_BAND_VERSION
    assert value["confidence"]["pipeline_validation_cap"] == 0.5  # type: ignore[index]
    assert FUSION_ENGINE_VERSION == "credit_fusion_engine_v1"


@pytest.mark.parametrize(
    "rule_weight,ml_weight,error",
    [(-0.1, 1.1, "OUT_OF_RANGE"), (0.8, 0.4, "SUM_TO_ONE")],
)
def test_invalid_weight_rejected(rule_weight: float, ml_weight: float, error: str) -> None:
    value = deepcopy(load_policy())
    value["weighted_blend"] = {"rule_weight": rule_weight, "ml_weight": ml_weight}
    with pytest.raises(ValueError, match=error):
        validate_policy(value)


def test_risk_band_ranges_and_gap_thresholds_valid() -> None:
    assert experimental_band(0) == "LOW_EXPERIMENTAL_RISK"
    assert experimental_band(1) == "HIGH_EXPERIMENTAL_RISK"
    assert agreement_level(Decimal("0.15"), load_policy()) == "LOW"
    assert agreement_level(Decimal("0.30"), load_policy()) == "MODERATE"
    assert agreement_level(Decimal("0.31"), load_policy()) == "HIGH"


@pytest.mark.parametrize("score,expected", [(0, 1), (100, 0), (72.4, 0.276)])
def test_rule_score_to_risk_index_boundaries(score: float, expected: float) -> None:
    assert rule_score_to_risk_index(score) == Decimal(str(expected))


def test_rule_risk_index_not_pd() -> None:
    assert rule_score_to_risk_index(80) == Decimal("0.2")
    assert "probability" not in rule_score_to_risk_index.__name__


def test_weighted_fusion_math_precision_and_contributions() -> None:
    result = weighted_blend(Decimal("0.276"), Decimal("0.38"), load_policy())
    assert result["hybrid_risk_index"] == Decimal("0.3176")
    assert result["rule_contribution"] == Decimal("0.1656")
    assert result["ml_contribution"] == Decimal("0.152")
    assert Decimal("0") <= result["hybrid_risk_index"] <= Decimal("1")  # type: ignore[operator]


def test_consensus_low_moderate_high_behavior() -> None:
    low = consensus_gated(Decimal("0.25"), Decimal("0.30"), load_policy())
    moderate = consensus_gated(Decimal("0.20"), Decimal("0.40"), load_policy())
    high = consensus_gated(Decimal("0.15"), Decimal("0.80"), load_policy())
    assert low["status"] == "EXPERIMENTAL_RESULT"
    assert moderate == {"status": "REVIEW_REQUIRED", "hybrid_risk_index": None}
    assert high == {"status": "BLOCKED_BY_DISAGREEMENT", "hybrid_risk_index": None}


def test_fusion_confidence_penalties_and_cap() -> None:
    confidence, penalties = fusion_confidence(
        rule_confidence=0.95,
        coverage=0.95,
        calibration_available=True,
        gap_level="LOW",
        drift_level="MODERATE",
        model_disagreement="MODERATE_DISAGREEMENT",
        rule_status="NEEDS_REVIEW",
        policy=load_policy(),
    )
    assert confidence <= 0.5
    assert {row["reason_code"] for row in penalties} >= {
        "SYNTHETIC_ONLY_DATA",
        "MODERATE_FEATURE_DRIFT",
        "MODERATE_MODEL_DISAGREEMENT",
    }


def test_experiment_diagnostic_never_claims_hybrid_calibration_or_winner() -> None:
    value = experiment_diagnostic(
        strategy="WEIGHTED_BLEND",
        rule_risk_index=Decimal("0.20"),
        ml_probability=Decimal("0.30"),
        hybrid_risk_index=Decimal("0.24"),
        model=None,
        evaluation=None,
        experimental_threshold=0.5,
    )
    assert value["status"] == "PIPELINE_DIAGNOSTIC_ONLY"
    assert value["hybrid_brier_score"]["status"] == "NOT_CALCULATED"  # type: ignore[index]
    assert value["strategy_winner"] is None
    assert value["comparison"]["WEIGHTED_BLEND"]["is_calibrated_probability"] is False  # type: ignore[index]


def _context(
    db_session: Session, tmp_path: Path
) -> tuple[CreditAssessment, CreditMLFeatureSnapshot, Path]:
    create_synthetic_credit_dataset(db_session, tmp_path)
    storage = tmp_path / "storage"
    CreditMLTrainingService(db_session, tmp_path, storage).train()
    CreditMLEvaluationService(db_session, tmp_path).evaluate()
    snapshot = db_session.scalar(
        select(CreditMLFeatureSnapshot).order_by(CreditMLFeatureSnapshot.observation_date)
    )
    assert snapshot is not None
    job = AnalysisJob(company_id=snapshot.company_id)
    db_session.add(job)
    db_session.flush()
    document = Document(
        analysis_job_id=job.id,
        company_id=snapshot.company_id,
        original_filename="fusion.pdf",
        sha256_hash="f" * 64,
    )
    db_session.add(document)
    db_session.flush()
    analysis = FinancialAnalysisRun(
        document_id=document.id,
        analysis_job_id=job.id,
        input_hash="a" * 64,
        status="VERIFIED",
        completeness_score=0.9,
        normalized_value_count=1,
        derived_value_count=0,
        ratio_count=1,
        validator_version="test",
        calculator_version="test",
        ratio_taxonomy_version="test",
    )
    db_session.add(analysis)
    db_session.flush()
    trend = FinancialTrendRun(
        analysis_job_id=job.id,
        company_id=snapshot.company_id,
        document_id=document.id,
        financial_analysis_run_id=analysis.id,
        input_hash="b" * 64,
        trend_calculator_version="test",
        anomaly_rule_version="test",
        status="VERIFIED",
        trend_count=1,
        anomaly_count=0,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db_session.add(trend)
    db_session.flush()
    assessment = CreditAssessment(
        analysis_job_id=job.id,
        company_id=snapshot.company_id,
        document_id=document.id,
        financial_analysis_run_id=analysis.id,
        financial_trend_run_id=trend.id,
        statement_scope=FinancialScope.CONSOLIDATED,
        overall_score=Decimal("70"),
        risk_band="MODERATE_RISK",
        component_coverage=Decimal("0.90"),
        confidence_score=Decimal("0.90"),
        status=CreditAssessmentStatus.VERIFIED,
        feature_builder_version="test",
        policy_version="credit_policy_v1",
        score_engine_version="test",
        input_hash="c" * 64,
    )
    db_session.add(assessment)
    db_session.flush()
    return assessment, snapshot, storage


def test_pipeline_validation_allows_experiment_only_and_blocks_production(
    db_session: Session, tmp_path: Path
) -> None:
    assessment, snapshot, storage = _context(db_session, tmp_path)
    result = CreditFusionReadinessService(db_session, storage).check(assessment.id, snapshot.id)
    assert result["experimental_fusion_allowed"] is True
    assert result["production_fusion_allowed"] is False
    assert {
        "INSUFFICIENT_REAL_OUTCOMES",
        "INSUFFICIENT_WALK_FORWARD_SUPPORT",
        "MODEL_NOT_PRODUCTION_PERMITTED",
    } <= set(result["production_blocking_reasons"])  # type: ignore[arg-type]


def test_weighted_and_consensus_experiments_persist_lineage_and_are_idempotent(
    db_session: Session, tmp_path: Path
) -> None:
    assessment, snapshot, storage = _context(db_session, tmp_path)
    before_model = db_session.scalar(select(func.count()).select_from(MLModel))
    before_eval = db_session.scalar(select(func.count()).select_from(CreditMLEvaluationRun))
    original_score = assessment.overall_score
    service = CreditFusionService(db_session, storage)
    weighted = service.run(
        credit_assessment_id=assessment.id,
        feature_snapshot_id=snapshot.id,
        strategy="WEIGHTED_BLEND",
    )
    repeated = service.run(
        credit_assessment_id=assessment.id,
        feature_snapshot_id=snapshot.id,
        strategy="WEIGHTED_BLEND",
    )
    consensus = service.run(
        credit_assessment_id=assessment.id,
        feature_snapshot_id=snapshot.id,
        strategy="CONSENSUS_GATED",
    )
    assert weighted["status"] == "EXPERIMENTAL_RESULT"
    assert weighted["production_use_permitted"] is False
    assert weighted["fusion_confidence"] <= 0.5  # type: ignore[operator]
    diagnostic = weighted["readiness"]["experiment_evaluation"]  # type: ignore[index]
    assert diagnostic["status"] == "PIPELINE_DIAGNOSTIC_ONLY"  # type: ignore[index]
    assert diagnostic["strategy_winner"] is None  # type: ignore[index]
    assert repeated["experiment_id"] == weighted["experiment_id"] and repeated["idempotent"] is True
    assert consensus["experiment_id"] != weighted["experiment_id"]
    assert db_session.scalar(select(func.count()).select_from(CreditFusionExperiment)) == 2
    assert db_session.scalar(select(func.count()).select_from(CreditFusionContribution)) == 4
    assert db_session.scalar(select(func.count()).select_from(CreditFusionReason)) > 0
    assert db_session.scalar(select(func.count()).select_from(CreditFusionInput)) == 6
    assert db_session.get(CreditAssessment, assessment.id).overall_score == original_score  # type: ignore[union-attr]
    assert db_session.scalar(select(func.count()).select_from(MLModel)) == before_model
    assert db_session.scalar(select(func.count()).select_from(CreditMLEvaluationRun)) == before_eval


def test_missing_or_corrupt_artifact_uses_rule_only_fallback(
    db_session: Session, tmp_path: Path
) -> None:
    assessment, snapshot, storage = _context(db_session, tmp_path)
    model = db_session.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
    assert model is not None
    path = storage / model.artifact_uri.removeprefix("local://")
    path.write_bytes(path.read_bytes() + b"corrupt")
    result = CreditFusionService(db_session, storage).run(
        credit_assessment_id=assessment.id,
        feature_snapshot_id=snapshot.id,
        strategy="WEIGHTED_BLEND",
    )
    assert result["status"] == "RULE_ONLY_FALLBACK"
    assert result["fusion_not_executed"] is True
    assert result["fallback_source"] == "DAY_10_RULE_ENGINE"
    assert result["experimental_hybrid_risk_index"] is None


def test_low_data_quality_produces_no_reliable_output(db_session: Session, tmp_path: Path) -> None:
    assessment, snapshot, storage = _context(db_session, tmp_path)
    assessment.component_coverage = Decimal("0.42")
    result = CreditFusionService(db_session, storage).run(
        credit_assessment_id=assessment.id,
        feature_snapshot_id=snapshot.id,
        strategy="WEIGHTED_BLEND",
    )
    assert result["status"] == "NO_RELIABLE_OUTPUT"
    assert result["experimental_hybrid_risk_index"] is None


def test_high_rule_ml_gap_blocks_weighted_output(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assessment, snapshot, storage = _context(db_session, tmp_path)
    assessment.overall_score = Decimal("85")
    monkeypatch.setattr(
        "app.ml.credit.inference.CreditMLInferenceService.predict",
        lambda self, snapshot_id: {
            "probability_of_default": 0.80,
            "feature_snapshot_hash": snapshot.input_hash,
        },
    )
    result = CreditFusionService(db_session, storage).run(
        credit_assessment_id=assessment.id,
        feature_snapshot_id=snapshot.id,
        strategy="WEIGHTED_BLEND",
    )
    assert result["rule_ml_gap"] == pytest.approx(0.65)
    assert result["status"] == "BLOCKED_BY_DISAGREEMENT"
    assert result["experimental_hybrid_risk_index"] is None


def test_retrieval_apis_and_unknown_404(db_session: Session, tmp_path: Path) -> None:
    assessment, snapshot, storage = _context(db_session, tmp_path)
    result = CreditFusionService(db_session, storage).run(
        credit_assessment_id=assessment.id,
        feature_snapshot_id=snapshot.id,
        strategy="WEIGHTED_BLEND",
    )
    experiment_id = result["experiment_id"]
    assert get_fusion_experiment(experiment_id, db_session)["production_use_permitted"] is False  # type: ignore[arg-type]
    assert (
        len(list_document_fusion_experiments(assessment.document_id, None, None, db_session)) == 1
    )  # type: ignore[arg-type]
    assert len(get_fusion_contributions(experiment_id, db_session)) == 2  # type: ignore[arg-type]
    assert get_fusion_reasons(experiment_id, db_session)  # type: ignore[arg-type]
    with pytest.raises(AppError):
        get_fusion_experiment(UUID(int=0), db_session)  # type: ignore[arg-type]
