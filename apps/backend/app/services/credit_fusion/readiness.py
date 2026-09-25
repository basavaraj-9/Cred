from __future__ import annotations

# ruff: noqa: E501
from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.credit.artifacts import ArtifactError, load_verified_artifact
from app.models.credit import CreditAssessment
from app.models.credit_ml import CreditMLFeatureSnapshot
from app.models.credit_ml_evaluation import CreditMLEvaluationRun
from app.models.ml import MLDataset, MLModel
from app.services.credit_fusion.policy import load_policy


class CreditFusionReadinessService:
    def __init__(self, session: Session, storage_root: Path) -> None:
        self.session = session
        self.storage_root = storage_root

    def check(self, credit_assessment_id: object, feature_snapshot_id: object) -> dict[str, object]:
        policy = load_policy()
        gates = cast(dict[str, object], policy["gates"])
        assessment = self.session.get(CreditAssessment, credit_assessment_id)
        snapshot = self.session.get(CreditMLFeatureSnapshot, feature_snapshot_id)
        model = self.session.scalar(
            select(MLModel).where(MLModel.task_type == "CREDIT_RISK", MLModel.is_active.is_(True))
        )
        checks: dict[str, dict[str, object]] = {}
        reasons: list[str] = []
        rule_valid = bool(
            assessment
            and assessment.overall_score is not None
            and assessment.status.value in cast(list[str], gates["accepted_rule_statuses"])
        )
        checks["rule_assessment"] = {"passed": rule_valid}
        if not rule_valid:
            reasons.append("RULE_INPUT_UNAVAILABLE")
        rule_confidence = float(assessment.confidence_score) if assessment else 0
        assessment_coverage = float(assessment.component_coverage) if assessment else 0
        feature_completeness = (
            snapshot.features_json.get("financial_completeness") if snapshot else None
        )
        coverage = min(
            assessment_coverage,
            float(feature_completeness)
            if isinstance(feature_completeness, (int, float))
            else assessment_coverage,
        )
        checks["rule_confidence"] = {
            "passed": rule_confidence >= float(cast(float, gates["minimum_rule_confidence"])),
            "value": rule_confidence,
        }
        checks["data_coverage"] = {
            "passed": coverage >= float(cast(float, gates["minimum_data_coverage"])),
            "value": coverage,
        }
        if rule_valid and not checks["rule_confidence"]["passed"]:
            reasons.append("RULE_CONFIDENCE_LOW")
        if rule_valid and not checks["data_coverage"]["passed"]:
            reasons.append("DATA_COVERAGE_INSUFFICIENT")
        snapshot_valid = bool(
            assessment
            and snapshot
            and assessment.company_id == snapshot.company_id
            and model
            and snapshot.feature_group == model.feature_group
        )
        checks["feature_snapshot_lineage"] = {"passed": snapshot_valid}
        if not snapshot_valid:
            reasons.append("FEATURE_SNAPSHOT_LINEAGE_INVALID")
        artifact_status = "UNAVAILABLE"
        if model:
            try:
                load_verified_artifact(self.storage_root, model.artifact_uri, model.artifact_sha256)
                artifact_status = "VERIFIED"
            except ArtifactError as exc:
                artifact_status = str(exc)
        checks["model_artifact"] = {
            "passed": artifact_status == "VERIFIED",
            "status": artifact_status,
        }
        if artifact_status != "VERIFIED":
            reasons.append("ML_ARTIFACT_INVALID")
        readiness_valid = bool(
            model
            and model.model_readiness_status
            in cast(list[str], gates["accepted_experimental_ml_readiness"])
            and model.lifecycle_status
            in cast(list[str], gates["accepted_experimental_ml_lifecycle"])
        )
        checks["ml_readiness"] = {
            "passed": readiness_valid,
            "readiness": model.model_readiness_status if model else None,
            "lifecycle": model.lifecycle_status if model else None,
        }
        if not readiness_valid:
            reasons.append("MODEL_NOT_EXPERIMENT_READY")
        evaluation = None
        if model:
            evaluation = self.session.scalar(
                select(CreditMLEvaluationRun)
                .where(
                    CreditMLEvaluationRun.dataset_id == model.dataset_id,
                    CreditMLEvaluationRun.status == "COMPLETED",
                )
                .order_by(CreditMLEvaluationRun.completed_at.desc())
            )
        drift_counts = cast(
            dict[str, int],
            (evaluation.summary_json if evaluation else {}).get("drift_status_counts", {}),
        )
        drift_level = (
            "HIGH"
            if drift_counts.get("HIGH")
            else "MODERATE"
            if drift_counts.get("MODERATE")
            else "LOW"
            if evaluation and not drift_counts.get("INSUFFICIENT_DATA")
            else "INSUFFICIENT_DATA"
        )
        disagreement_counts = cast(
            dict[str, int],
            cast(
                dict[str, object],
                (evaluation.summary_json if evaluation else {}).get("model_disagreement", {}),
            ).get("status_counts", {}),
        )
        disagreement = (
            "HIGH_DISAGREEMENT"
            if disagreement_counts.get("HIGH_DISAGREEMENT")
            else "MODERATE_DISAGREEMENT"
            if disagreement_counts.get("MODERATE_DISAGREEMENT")
            else "LOW_DISAGREEMENT"
            if evaluation
            else "INSUFFICIENT_DATA"
        )
        checks["drift"] = {"passed": drift_level != "HIGH", "status": drift_level}
        checks["model_disagreement"] = {
            "passed": disagreement != "HIGH_DISAGREEMENT",
            "status": disagreement,
        }
        if drift_level == "HIGH":
            reasons.append("HIGH_FEATURE_DRIFT")
        if disagreement == "HIGH_DISAGREEMENT":
            reasons.append("HIGH_MODEL_DISAGREEMENT")
        if evaluation is None:
            reasons.append("EVALUATION_UNAVAILABLE")
        dataset = self.session.get(MLDataset, model.dataset_id) if model else None
        synthetic_only = (
            not dataset or int(cast(int, (dataset.metadata_json or {}).get("real_count", 0))) == 0
        )
        production_reasons = list(reasons)
        if synthetic_only:
            production_reasons.append("INSUFFICIENT_REAL_OUTCOMES")
        if not evaluation or evaluation.valid_window_count < int(
            cast(int, gates["required_walk_forward_windows_production"])
        ):
            production_reasons.append("INSUFFICIENT_WALK_FORWARD_SUPPORT")
        if not model or model.lifecycle_status == "PIPELINE_VALIDATION_ONLY":
            production_reasons.append("MODEL_NOT_PRODUCTION_PERMITTED")
        experimental_allowed = all(
            bool(checks[name]["passed"])
            for name in (
                "rule_assessment",
                "rule_confidence",
                "data_coverage",
                "feature_snapshot_lineage",
                "model_artifact",
                "ml_readiness",
                "drift",
                "model_disagreement",
            )
        )
        return {
            "status": "EXPERIMENT_READY" if experimental_allowed else "BLOCKED",
            "experimental_fusion_allowed": experimental_allowed,
            "production_fusion_allowed": False,
            "blocking_reasons": list(dict.fromkeys(reasons)),
            "production_blocking_reasons": list(dict.fromkeys(production_reasons)),
            "checks": checks,
            "model_id": model.id if model else None,
            "model_version": model.model_version if model else None,
            "evaluation_run_id": evaluation.id if evaluation else None,
            "evaluation_valid_windows": evaluation.valid_window_count if evaluation else 0,
            "drift_status": drift_level,
            "model_disagreement": disagreement,
            "synthetic_only": synthetic_only,
            "rule_only_fallback_available": rule_valid
            and checks["rule_confidence"]["passed"]
            and checks["data_coverage"]["passed"],
        }
