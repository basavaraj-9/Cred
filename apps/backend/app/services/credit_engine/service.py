from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.credit import (
    CreditAssessment,
    CreditAssessmentInput,
    CreditRuleResult,
    CreditSubscore,
)
from app.models.document import Document
from app.models.enums import AnalysisStage, CreditAssessmentStatus, FinancialScope
from app.models.financial_analysis import FinancialAnalysisRun, FinancialRatio
from app.models.financial_trend import FinancialTrend, FinancialTrendRun
from app.services.credit_engine.features import FEATURE_BUILDER_VERSION, build_credit_features
from app.services.credit_engine.policy import CREDIT_POLICY_VERSION
from app.services.credit_engine.schemas import AssessmentResult, CreditFeatures
from app.services.credit_engine.scoring import SCORE_ENGINE_VERSION, score_credit

logger = logging.getLogger(__name__)


def latest_credit_assessments(session: Session, document_id: UUID) -> list[CreditAssessment]:
    day8, day9 = _latest_sources(session, document_id)
    rows = list(
        session.scalars(
            select(CreditAssessment)
            .where(
                CreditAssessment.document_id == document_id,
                CreditAssessment.financial_analysis_run_id == day8.id,
                CreditAssessment.financial_trend_run_id == day9.id,
            )
            .order_by(CreditAssessment.created_at.desc())
        ).all()
    )
    selected: dict[FinancialScope, CreditAssessment] = {}
    for row in rows:
        selected.setdefault(row.statement_scope, row)
    return list(selected.values())


def _latest_sources(
    session: Session, document_id: UUID
) -> tuple[FinancialAnalysisRun, FinancialTrendRun]:
    day8 = session.scalar(
        select(FinancialAnalysisRun)
        .where(FinancialAnalysisRun.document_id == document_id)
        .order_by(FinancialAnalysisRun.created_at.desc())
    )
    if day8 is None:
        raise AppError(
            "FINANCIAL_ANALYSIS_REQUIRED", "Run financial analysis before credit risk analysis", 409
        )
    day9 = session.scalar(
        select(FinancialTrendRun)
        .where(FinancialTrendRun.document_id == document_id)
        .order_by(FinancialTrendRun.created_at.desc())
    )
    if day9 is None:
        raise AppError(
            "FINANCIAL_TREND_ANALYSIS_REQUIRED",
            "Run financial trend analysis before credit risk analysis",
            409,
        )
    if day9.financial_analysis_run_id != day8.id:
        raise AppError(
            "FINANCIAL_TREND_ANALYSIS_STALE",
            "Re-run financial trend analysis for the latest financial analysis",
            409,
        )
    return day8, day9


def _scopes(
    session: Session, day8: FinancialAnalysisRun, day9: FinancialTrendRun
) -> list[FinancialScope]:
    scopes = set(
        session.scalars(
            select(FinancialTrend.statement_scope)
            .where(FinancialTrend.run_id == day9.id)
            .distinct()
        ).all()
    )
    scopes.update(
        session.scalars(
            select(FinancialRatio.statement_scope)
            .where(FinancialRatio.run_id == day8.id)
            .distinct()
        ).all()
    )
    return sorted(scopes, key=lambda item: item.value)


def _fingerprint(
    day8: FinancialAnalysisRun, day9: FinancialTrendRun, features: CreditFeatures
) -> str:
    digest = hashlib.sha256(
        f"{day8.id}|{day9.id}|{features.scope.value}|{FEATURE_BUILDER_VERSION}|{CREDIT_POLICY_VERSION}|{SCORE_ENGINE_VERSION}\n".encode()
    )
    for input_ref in sorted(features.input_refs, key=lambda row: (row.role, str(row.source_id))):
        digest.update(f"{input_ref.role}|{input_ref.source_type}|{input_ref.source_id}\n".encode())
    for group_name, group in (
        ("ratio", features.ratios),
        ("value", features.values),
    ):
        for name, metric_feature in sorted(group.items()):
            digest.update(
                f"{group_name}|{name}|{metric_feature.value}|{metric_feature.status}|"
                f"{metric_feature.confidence}\n".encode()
            )
    for name, trend_feature in sorted(features.trends.items()):
        digest.update(
            f"trend|{name}|{trend_feature.direction}|{trend_feature.status}|"
            f"{trend_feature.confidence}|{trend_feature.missing_periods}|"
            f"{trend_feature.source_signature}\n".encode()
        )
    for name, anomaly_feature in sorted(features.anomalies.items()):
        digest.update(
            f"anomaly|{name}|{anomaly_feature.severity}|{anomaly_feature.status}|"
            f"{anomaly_feature.confidence}|{anomaly_feature.source_signature}\n".encode()
        )
    digest.update(
        f"{features.completeness}|{features.validation_errors}|{features.conflicting_inputs}|{features.verified_ratio_share}|{features.missing_period_count}|{features.profile_status}|{features.profile_confidence}|{features.domain_status}|{features.domain_confidence}".encode()
    )
    return digest.hexdigest()


def assessment_payload(session: Session, assessment: CreditAssessment) -> dict[str, object]:
    subscores = list(
        session.scalars(
            select(CreditSubscore)
            .where(CreditSubscore.credit_assessment_id == assessment.id)
            .order_by(CreditSubscore.component_name)
        ).all()
    )
    reasons = list(
        session.scalars(
            select(CreditRuleResult)
            .where(CreditRuleResult.credit_assessment_id == assessment.id)
            .order_by(CreditRuleResult.component, CreditRuleResult.rule_code)
        ).all()
    )
    return {
        "assessment_id": assessment.id,
        "document_id": assessment.document_id,
        "statement_scope": assessment.statement_scope,
        "scope": assessment.statement_scope,
        "overall_score": assessment.overall_score,
        "risk_band": assessment.risk_band,
        "component_coverage": assessment.component_coverage,
        "coverage": assessment.component_coverage,
        "confidence_score": assessment.confidence_score,
        "confidence": assessment.confidence_score,
        "status": assessment.status,
        "policy_version": assessment.policy_version,
        "feature_builder_version": assessment.feature_builder_version,
        "score_engine_version": assessment.score_engine_version,
        "financial_analysis_run_id": assessment.financial_analysis_run_id,
        "financial_trend_run_id": assessment.financial_trend_run_id,
        "subscores": [
            {
                "component": row.component_name,
                "score": row.normalized_score,
                "weight": row.weight,
                "weighted_score": row.weighted_score,
                "coverage": row.coverage_ratio,
                "confidence_score": row.confidence_score,
                "status": row.status,
            }
            for row in subscores
        ],
        "top_positive_factors": [
            {
                "rule_code": row.rule_code,
                "component": row.component,
                "impact": row.score_impact,
                "message": row.message,
            }
            for row in sorted(
                (item for item in reasons if item.score_impact > 0),
                key=lambda item: item.score_impact,
                reverse=True,
            )[:5]
        ],
        "top_negative_factors": [
            {
                "rule_code": row.rule_code,
                "component": row.component,
                "impact": row.score_impact,
                "message": row.message,
            }
            for row in sorted(
                (item for item in reasons if item.score_impact < 0),
                key=lambda item: item.score_impact,
            )[:5]
        ],
        "disclaimer": (
            "Development-stage analytical score. It is not an approval, rejection, "
            "pricing, limit, or lending decision."
        ),
    }


def _persist(
    session: Session,
    document: Document,
    day8: FinancialAnalysisRun,
    day9: FinancialTrendRun,
    features: CreditFeatures,
    result: AssessmentResult,
    fingerprint: str,
) -> CreditAssessment:
    assessment = CreditAssessment(
        analysis_job_id=document.analysis_job_id,
        company_id=document.company_id,
        document_id=document.id,
        financial_analysis_run_id=day8.id,
        financial_trend_run_id=day9.id,
        statement_scope=features.scope,
        overall_score=result.score,
        risk_band=result.risk_band,
        component_coverage=result.component_coverage,
        confidence_score=result.confidence,
        status=result.status,
        feature_builder_version=FEATURE_BUILDER_VERSION,
        policy_version=CREDIT_POLICY_VERSION,
        score_engine_version=SCORE_ENGINE_VERSION,
        input_hash=fingerprint,
    )
    session.add(assessment)
    session.flush()
    input_ids: dict[str, UUID] = {}
    source_columns = {
        "normalized_financial_value": "normalized_financial_value_id",
        "financial_ratio": "financial_ratio_id",
        "financial_trend": "financial_trend_id",
        "financial_anomaly": "financial_anomaly_id",
        "company_profile": "company_profile_id",
        "domain_classification": "domain_classification_id",
    }
    for ref in features.input_refs:
        values: dict[str, UUID | None] = {name: None for name in source_columns.values()}
        values[source_columns[ref.source_type]] = ref.source_id
        link = CreditAssessmentInput(
            credit_assessment_id=assessment.id, input_role=ref.role, **values
        )
        session.add(link)
        session.flush()
        input_ids[ref.role] = link.id
    eligible_weight = result.component_coverage
    for component in result.components:
        weighted = (
            component.score * component.weight / eligible_weight
            if eligible_weight
            and component.status
            not in {
                CreditAssessmentStatus.INSUFFICIENT_DATA,
                CreditAssessmentStatus.UNAVAILABLE,
                CreditAssessmentStatus.FAILED,
            }
            else None
        )
        session.add(
            CreditSubscore(
                credit_assessment_id=assessment.id,
                component_name=component.component,
                raw_score=component.score,
                max_score=Decimal(100),
                normalized_score=component.score,
                weight=component.weight,
                weighted_score=weighted,
                coverage_ratio=component.coverage,
                confidence_score=component.confidence,
                status=component.status,
            )
        )
        for reason in component.rules:
            session.add(
                CreditRuleResult(
                    credit_assessment_id=assessment.id,
                    credit_assessment_input_id=input_ids.get(reason.source_role or ""),
                    component=reason.component,
                    rule_code=reason.code,
                    rule_version=CREDIT_POLICY_VERSION,
                    input_metric=reason.input_metric,
                    input_value=reason.input_value,
                    input_status=reason.input_status,
                    score_impact=reason.impact,
                    max_score_impact=reason.max_impact,
                    reason_type=reason.reason_type,
                    message=reason.message,
                    confidence_score=float(reason.confidence),
                    status=reason.status,
                )
            )
    session.flush()
    return assessment


def _run(
    session: Session, document_id: UUID, scope: FinancialScope | None
) -> list[dict[str, object]]:
    with session.begin():
        document = session.get(Document, document_id)
        if document is None:
            raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
        day8, day9 = _latest_sources(session, document_id)
        available = _scopes(session, day8, day9)
        if scope and scope not in available:
            raise AppError(
                "FINANCIAL_SCOPE_NOT_FOUND",
                "The requested financial statement scope is unavailable",
                404,
            )
        selected = [scope] if scope else available
        if not selected:
            raise AppError(
                "CREDIT_INPUTS_UNAVAILABLE", "No scoped Day 8 or Day 9 inputs are available", 409
            )
        document.analysis_job.current_stage = AnalysisStage.CREDIT_ANALYSIS
        output: list[dict[str, object]] = []
        for current_scope in selected:
            features = build_credit_features(session, day8, day9, current_scope)
            fingerprint = _fingerprint(day8, day9, features)
            existing = session.scalar(
                select(CreditAssessment).where(
                    CreditAssessment.document_id == document.id,
                    CreditAssessment.statement_scope == current_scope,
                    CreditAssessment.input_hash == fingerprint,
                    CreditAssessment.policy_version == CREDIT_POLICY_VERSION,
                    CreditAssessment.feature_builder_version == FEATURE_BUILDER_VERSION,
                    CreditAssessment.score_engine_version == SCORE_ENGINE_VERSION,
                )
            )
            if existing:
                output.append(assessment_payload(session, existing))
                continue
            write_audit_log(
                session,
                entity_type="document",
                entity_id=document.id,
                action="CREDIT_RISK_ANALYSIS_STARTED",
                event_type="CREDIT_RISK_ANALYSIS_STARTED",
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
                metadata_json={
                    "scope": current_scope.value,
                    "policy_version": CREDIT_POLICY_VERSION,
                    "score_engine_version": SCORE_ENGINE_VERSION,
                },
            )
            result = score_credit(features)
            assessment = _persist(session, document, day8, day9, features, result, fingerprint)
            for component in result.components:
                write_audit_log(
                    session,
                    entity_type="credit_assessment",
                    entity_id=assessment.id,
                    action="CREDIT_SUBSCORE_CALCULATED",
                    event_type="CREDIT_SUBSCORE_CALCULATED",
                    company_id=document.company_id,
                    analysis_job_id=document.analysis_job_id,
                    metadata_json={
                        "component": component.component.value,
                        "score": str(component.score),
                        "coverage": str(component.coverage),
                        "status": component.status.value,
                    },
                )
            write_audit_log(
                session,
                entity_type="credit_assessment",
                entity_id=assessment.id,
                action="CREDIT_RISK_ANALYSIS_COMPLETED",
                event_type="CREDIT_RISK_ANALYSIS_COMPLETED",
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
                metadata_json={
                    "scope": current_scope.value,
                    "status": result.status.value,
                    "score": str(result.score) if result.score is not None else None,
                    "coverage": str(result.component_coverage),
                    "confidence": str(result.confidence),
                    "risk_band": result.risk_band.value if result.risk_band else None,
                    "policy_version": CREDIT_POLICY_VERSION,
                    "score_engine_version": SCORE_ENGINE_VERSION,
                },
            )
            if result.status in {
                CreditAssessmentStatus.NEEDS_REVIEW,
                CreditAssessmentStatus.CONFLICTING,
                CreditAssessmentStatus.INSUFFICIENT_DATA,
            }:
                write_audit_log(
                    session,
                    entity_type="credit_assessment",
                    entity_id=assessment.id,
                    action="CREDIT_RISK_REVIEW_REQUIRED",
                    event_type="CREDIT_RISK_REVIEW_REQUIRED",
                    company_id=document.company_id,
                    analysis_job_id=document.analysis_job_id,
                    metadata_json={"status": result.status.value},
                )
            output.append(assessment_payload(session, assessment))
        return output


def run_credit_analysis(
    session: Session, document_id: UUID, scope: FinancialScope | None = None
) -> list[dict[str, object]]:
    try:
        return _run(session, document_id, scope)
    except AppError:
        raise
    except Exception as exc:
        logger.exception(
            "Credit analysis failed: document=%s error=%s", document_id, type(exc).__name__
        )
        session.rollback()
        try:
            with session.begin():
                document = session.get(Document, document_id)
                if document:
                    write_audit_log(
                        session,
                        entity_type="document",
                        entity_id=document.id,
                        action="CREDIT_RISK_ANALYSIS_FAILED",
                        event_type="CREDIT_RISK_ANALYSIS_FAILED",
                        company_id=document.company_id,
                        analysis_job_id=document.analysis_job_id,
                        metadata_json={"error_type": type(exc).__name__},
                    )
        except Exception:
            session.rollback()
        raise
