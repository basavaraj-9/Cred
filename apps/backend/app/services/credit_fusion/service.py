from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.repositories.audit_log import write_audit_log
from app.ml.credit.inference import CreditMLInferenceService
from app.models.credit import CreditAssessment
from app.models.credit_fusion import (
    CreditFusionContribution,
    CreditFusionExperiment,
    CreditFusionInput,
    CreditFusionReason,
)
from app.models.credit_ml import CreditMLFeatureSnapshot
from app.models.credit_ml_evaluation import CreditMLEvaluationRun
from app.models.ml import MLModel
from app.services.credit_fusion.confidence import fusion_confidence
from app.services.credit_fusion.diagnostics import experiment_diagnostic
from app.services.credit_fusion.policy import (
    FUSION_BAND_VERSION,
    FUSION_ENGINE_VERSION,
    FUSION_POLICY_VERSION,
    load_policy,
)
from app.services.credit_fusion.readiness import CreditFusionReadinessService
from app.services.credit_fusion.strategies import agreement_level, consensus_gated, weighted_blend
from app.services.credit_fusion.transforms import rule_score_to_risk_index

WARNING = (
    "Experimental pipeline-validation output only. The ML model is trained on synthetic "
    "development data and this fusion result must not be used for real lending decisions."
)


def _hash(value: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _reason_message(code: str) -> str:
    messages = {
        "RULE_ML_LOW_GAP": "Rule and ML diagnostic risk inputs have a low gap.",
        "RULE_ML_MODERATE_GAP": "Rule and ML diagnostic risk inputs have a moderate gap.",
        "RULE_ML_HIGH_GAP": "Rule and ML diagnostic risk inputs have a high gap; fusion is blocked.",
        "ML_PIPELINE_VALIDATION_ONLY": "The selected ML model is limited to pipeline validation.",
        "ML_ARTIFACT_VERIFIED": "The registered ML artifact passed SHA-256 and bundle validation.",
        "ML_ARTIFACT_INVALID": "The registered ML artifact failed availability or integrity validation.",
        "SYNTHETIC_ONLY_DATA": "No verified real historical outcomes are available.",
        "INSUFFICIENT_WALK_FORWARD_SUPPORT": "Walk-forward support is below the production requirement.",
        "RULE_ONLY_FALLBACK_USED": "Fusion was not executed; the immutable Day 10 assessment remains the fallback reference.",
        "FUSION_BLOCKED": "Fusion safety gates did not permit an experimental numeric result.",
    }
    return messages.get(code, code.replace("_", " ").capitalize())


class CreditFusionService:
    def __init__(self, session: Session, storage_root: Path) -> None:
        self.session = session
        self.storage_root = storage_root

    def run(
        self,
        *,
        credit_assessment_id: UUID,
        feature_snapshot_id: UUID,
        strategy: str,
    ) -> dict[str, object]:
        policy = load_policy()
        if strategy not in cast(list[str], policy["supported_strategies"]):
            raise ValueError("FUSION_STRATEGY_UNSUPPORTED")
        assessment = self.session.get(CreditAssessment, credit_assessment_id)
        snapshot = self.session.get(CreditMLFeatureSnapshot, feature_snapshot_id)
        if assessment is None:
            raise ValueError("CREDIT_ASSESSMENT_NOT_FOUND")
        if snapshot is None:
            raise ValueError("CREDIT_ML_FEATURE_SNAPSHOT_NOT_FOUND")
        readiness = CreditFusionReadinessService(self.session, self.storage_root).check(
            credit_assessment_id, feature_snapshot_id
        )
        model = (
            self.session.get(MLModel, readiness["model_id"]) if readiness.get("model_id") else None
        )
        evaluation = (
            self.session.get(CreditMLEvaluationRun, readiness["evaluation_run_id"])
            if readiness.get("evaluation_run_id")
            else None
        )
        rule_score = (
            Decimal(str(assessment.overall_score)) if assessment.overall_score is not None else None
        )
        rule_risk = rule_score_to_risk_index(rule_score) if rule_score is not None else None
        ml_probability: Decimal | None = None
        inference: dict[str, object] | None = None
        if readiness["experimental_fusion_allowed"]:
            inference = CreditMLInferenceService(self.session, self.storage_root).predict(
                snapshot.id
            )
            ml_probability = Decimal(str(inference["probability_of_default"]))
        weighted = cast(dict[str, object], policy["weighted_blend"])
        rule_weight = Decimal(str(weighted["rule_weight"]))
        ml_weight = Decimal(str(weighted["ml_weight"]))
        gap = (
            abs(ml_probability - rule_risk)
            if ml_probability is not None and rule_risk is not None
            else None
        )
        hash_payload: dict[str, object] = {
            "credit_assessment_id": str(assessment.id),
            "credit_assessment_input_hash": assessment.input_hash,
            "model_id": str(model.id) if model else None,
            "model_version": model.model_version if model else None,
            "artifact_sha256": model.artifact_sha256 if model else None,
            "feature_snapshot_id": str(snapshot.id),
            "feature_snapshot_hash": snapshot.input_hash,
            "ml_probability": str(ml_probability) if ml_probability is not None else None,
            "evaluation_id": str(evaluation.id) if evaluation else None,
            "evaluation_input_hash": evaluation.input_hash if evaluation else None,
            "policy": policy,
            "strategy": strategy,
            "drift": readiness["drift_status"],
            "model_disagreement": readiness["model_disagreement"],
            "coverage": str(assessment.component_coverage),
        }
        input_hash = _hash(hash_payload)
        existing = self.session.scalar(
            select(CreditFusionExperiment).where(
                CreditFusionExperiment.credit_assessment_id == assessment.id,
                CreditFusionExperiment.ml_model_id == (model.id if model else None),
                CreditFusionExperiment.input_hash == input_hash,
                CreditFusionExperiment.policy_version == FUSION_POLICY_VERSION,
                CreditFusionExperiment.strategy == strategy,
            )
        )
        if existing:
            return experiment_payload(self.session, existing, idempotent=True)
        write_audit_log(
            self.session,
            entity_type="credit_fusion_experiment",
            entity_id=UUID(int=0),
            action="CREDIT_FUSION_EXPERIMENT_STARTED",
            event_type="CREDIT_FUSION_EXPERIMENT_STARTED",
            company_id=assessment.company_id,
            analysis_job_id=assessment.analysis_job_id,
            metadata_json={
                "strategy": strategy,
                "policy_version": FUSION_POLICY_VERSION,
                "credit_assessment_id": str(assessment.id),
                "model_version": model.model_version if model else None,
            },
        )
        status = "NO_RELIABLE_OUTPUT"
        fusion_not_executed = True
        fallback_source = None
        result: dict[str, object] = {
            "hybrid_risk_index": None,
            "strength_score": None,
            "band": None,
        }
        reason_codes = [
            "ML_PIPELINE_VALIDATION_ONLY",
            "SYNTHETIC_ONLY_DATA",
            "INSUFFICIENT_WALK_FORWARD_SUPPORT",
        ]
        checks = cast(dict[str, dict[str, object]], readiness["checks"])
        if bool(checks["model_artifact"]["passed"]):
            reason_codes.append("ML_ARTIFACT_VERIFIED")
        else:
            reason_codes.append("ML_ARTIFACT_INVALID")
        if not bool(checks["rule_assessment"]["passed"]) or not bool(
            checks["data_coverage"]["passed"]
        ):
            status = "NO_RELIABLE_OUTPUT"
            reason_codes.append("FUSION_BLOCKED")
        elif not readiness["experimental_fusion_allowed"]:
            blocking = set(cast(list[str], readiness["blocking_reasons"]))
            if (
                blocking
                <= {
                    "ML_ARTIFACT_INVALID",
                    "MODEL_NOT_EXPERIMENT_READY",
                    "EVALUATION_UNAVAILABLE",
                    "FEATURE_SNAPSHOT_LINEAGE_INVALID",
                }
                and readiness["rule_only_fallback_available"]
            ):
                status = "RULE_ONLY_FALLBACK"
                fallback_source = "DAY_10_RULE_ENGINE"
                reason_codes.append("RULE_ONLY_FALLBACK_USED")
            elif "HIGH_FEATURE_DRIFT" in blocking:
                status = "BLOCKED_BY_DRIFT"
                reason_codes.append("HIGH_FEATURE_DRIFT")
            elif "HIGH_MODEL_DISAGREEMENT" in blocking:
                status = "BLOCKED_BY_DISAGREEMENT"
                reason_codes.append("HIGH_MODEL_DISAGREEMENT")
            else:
                status = "BLOCKED_BY_READINESS"
                reason_codes.append("FUSION_BLOCKED")
        elif gap is not None and rule_risk is not None and ml_probability is not None:
            gap_level = agreement_level(gap, policy)
            reason_codes.append(f"RULE_ML_{gap_level}_GAP")
            if gap_level == "HIGH":
                status = "BLOCKED_BY_DISAGREEMENT"
            else:
                result = (
                    weighted_blend(rule_risk, ml_probability, policy)
                    if strategy == "WEIGHTED_BLEND"
                    else consensus_gated(rule_risk, ml_probability, policy)
                )
                status = str(result["status"])
                fusion_not_executed = result["hybrid_risk_index"] is None
        gap_level = agreement_level(gap, policy) if gap is not None else "HIGH"
        confidence, penalties = fusion_confidence(
            rule_confidence=float(assessment.confidence_score),
            coverage=float(assessment.component_coverage),
            calibration_available=bool(model and model.calibration_method == "sigmoid"),
            gap_level=gap_level,
            drift_level=str(readiness["drift_status"]),
            model_disagreement=str(readiness["model_disagreement"]),
            rule_status=assessment.status.value,
            policy=policy,
        )
        if status not in {"EXPERIMENTAL_RESULT", "REVIEW_REQUIRED"}:
            confidence = min(confidence, 0.25)
        diagnostic = experiment_diagnostic(
            strategy=strategy,
            rule_risk_index=rule_risk,
            ml_probability=ml_probability,
            hybrid_risk_index=cast(Decimal | None, result.get("hybrid_risk_index")),
            model=model,
            evaluation=evaluation,
            experimental_threshold=float(cast(float, policy["experimental_threshold"])),
        )
        experiment = CreditFusionExperiment(
            analysis_job_id=assessment.analysis_job_id,
            company_id=assessment.company_id,
            document_id=assessment.document_id,
            credit_assessment_id=assessment.id,
            ml_model_id=model.id if model else None,
            feature_snapshot_id=snapshot.id,
            evaluation_run_id=evaluation.id if evaluation else None,
            strategy=strategy,
            mode="EXPERIMENTAL",
            rule_score=rule_score,
            rule_risk_index=rule_risk,
            ml_probability=ml_probability,
            rule_weight=rule_weight,
            ml_weight=ml_weight,
            experimental_hybrid_risk_index=cast(Decimal | None, result.get("hybrid_risk_index")),
            experimental_strength_score=cast(Decimal | None, result.get("strength_score")),
            experimental_band=cast(str | None, result.get("band")),
            rule_ml_gap=gap,
            fusion_confidence=confidence,
            status=status,
            production_use_permitted=False,
            fusion_not_executed=fusion_not_executed,
            fallback_source=fallback_source,
            policy_version=FUSION_POLICY_VERSION,
            risk_band_version=FUSION_BAND_VERSION,
            fusion_engine_version=FUSION_ENGINE_VERSION,
            input_hash=input_hash,
            readiness_json=json.loads(
                json.dumps(
                    {
                        **readiness,
                        "confidence_penalties": penalties,
                        "experiment_evaluation": diagnostic,
                        "warning": WARNING,
                    },
                    default=str,
                )
            ),
        )
        self.session.add(experiment)
        self.session.flush()
        if rule_score is not None and rule_risk is not None:
            self.session.add(
                CreditFusionContribution(
                    fusion_experiment_id=experiment.id,
                    contribution_type="RULE_COMPONENT",
                    source_type="DAY_10_RULE_ENGINE",
                    raw_value=rule_score,
                    normalized_value=rule_risk,
                    weight=rule_weight,
                    weighted_contribution=cast(Decimal | None, result.get("rule_contribution")),
                    confidence=float(assessment.confidence_score),
                    status="INCLUDED" if not fusion_not_executed else "REFERENCE_ONLY",
                    created_at=datetime.now(UTC),
                )
            )
        if ml_probability is not None:
            self.session.add(
                CreditFusionContribution(
                    fusion_experiment_id=experiment.id,
                    contribution_type="ML_COMPONENT",
                    source_type="DAY_12_ACTIVE_MODEL",
                    raw_value=ml_probability,
                    normalized_value=ml_probability,
                    weight=ml_weight,
                    weighted_contribution=cast(Decimal | None, result.get("ml_contribution")),
                    confidence=None,
                    status="INCLUDED" if not fusion_not_executed else "REFERENCE_ONLY",
                    created_at=datetime.now(UTC),
                )
            )
        for code in dict.fromkeys(reason_codes):
            self.session.add(
                CreditFusionReason(
                    fusion_experiment_id=experiment.id,
                    reason_code=code,
                    category="SAFETY"
                    if "BLOCK" in code or "INSUFFICIENT" in code
                    else "DIAGNOSTIC",
                    message=_reason_message(code),
                    impact_type="BLOCK"
                    if code
                    in {
                        "RULE_ML_HIGH_GAP",
                        "FUSION_BLOCKED",
                        "HIGH_FEATURE_DRIFT",
                        "HIGH_MODEL_DISAGREEMENT",
                    }
                    else "DISCLOSE",
                    severity="HIGH" if "HIGH" in code or "BLOCK" in code else "INFO",
                    source_reference_type=None,
                    source_reference_id=None,
                    created_at=datetime.now(UTC),
                )
            )
        self.session.add(
            CreditFusionInput(
                fusion_experiment_id=experiment.id,
                credit_assessment_id=assessment.id,
                input_role="RULE_ASSESSMENT",
                metadata_json={"input_hash": assessment.input_hash},
                created_at=datetime.now(UTC),
            )
        )
        if model:
            self.session.add(
                CreditFusionInput(
                    fusion_experiment_id=experiment.id,
                    ml_model_id=model.id,
                    feature_snapshot_id=snapshot.id,
                    ml_prediction_reference=str(inference["feature_snapshot_hash"])
                    if inference
                    else None,
                    input_role="ML_PREDICTION",
                    metadata_json={
                        "model_version": model.model_version,
                        "artifact_sha256": model.artifact_sha256,
                    },
                    created_at=datetime.now(UTC),
                )
            )
        if evaluation:
            self.session.add(
                CreditFusionInput(
                    fusion_experiment_id=experiment.id,
                    evaluation_run_id=evaluation.id,
                    input_role="EVALUATION_READINESS",
                    metadata_json={
                        "input_hash": evaluation.input_hash,
                        "fusion_readiness": evaluation.fusion_readiness,
                    },
                    created_at=datetime.now(UTC),
                )
            )
        action = (
            "CREDIT_FUSION_EXPERIMENT_COMPLETED"
            if status == "EXPERIMENTAL_RESULT"
            else "CREDIT_FUSION_RULE_ONLY_FALLBACK"
            if status == "RULE_ONLY_FALLBACK"
            else "CREDIT_FUSION_DISAGREEMENT_REVIEW"
            if status in {"REVIEW_REQUIRED", "BLOCKED_BY_DISAGREEMENT"}
            else "CREDIT_FUSION_BLOCKED"
        )
        write_audit_log(
            self.session,
            entity_type="credit_fusion_experiment",
            entity_id=experiment.id,
            action=action,
            event_type=action,
            company_id=assessment.company_id,
            analysis_job_id=assessment.analysis_job_id,
            metadata_json={
                "strategy": strategy,
                "policy_version": FUSION_POLICY_VERSION,
                "model_version": model.model_version if model else None,
                "credit_assessment_id": str(assessment.id),
                "gap": float(gap) if gap is not None else None,
                "status": status,
                "production_use_permitted": False,
            },
        )
        self.session.flush()
        return experiment_payload(self.session, experiment, idempotent=False)


def experiment_payload(
    session: Session, row: CreditFusionExperiment, *, idempotent: bool = False
) -> dict[str, object]:
    return {
        "experiment_id": row.id,
        "strategy": row.strategy,
        "mode": row.mode,
        "rule_score": float(row.rule_score) if row.rule_score is not None else None,
        "rule_risk_index": float(row.rule_risk_index) if row.rule_risk_index is not None else None,
        "rule_risk_index_is_probability": False,
        "ml_probability": float(row.ml_probability) if row.ml_probability is not None else None,
        "rule_ml_gap": float(row.rule_ml_gap) if row.rule_ml_gap is not None else None,
        "rule_weight": float(row.rule_weight),
        "ml_weight": float(row.ml_weight),
        "experimental_hybrid_risk_index": float(row.experimental_hybrid_risk_index)
        if row.experimental_hybrid_risk_index is not None
        else None,
        "experimental_hybrid_is_calibrated_pd": False,
        "experimental_strength_score": float(row.experimental_strength_score)
        if row.experimental_strength_score is not None
        else None,
        "experimental_band": row.experimental_band,
        "fusion_confidence": row.fusion_confidence,
        "status": row.status,
        "fusion_not_executed": row.fusion_not_executed,
        "fallback_source": row.fallback_source,
        "production_use_permitted": False,
        "policy_version": row.policy_version,
        "risk_band_version": row.risk_band_version,
        "fusion_engine_version": row.fusion_engine_version,
        "readiness": row.readiness_json,
        "warning": WARNING,
        "idempotent": idempotent,
    }
