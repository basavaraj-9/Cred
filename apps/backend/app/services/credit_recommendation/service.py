from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.repositories.audit_log import write_audit_log
from app.models.credit import CreditAssessment, CreditRuleResult
from app.models.credit_fusion import CreditFusionExperiment
from app.models.document import Document
from app.models.enums import FinancialScope
from app.models.five_cs import FiveCsAssessment, FiveCsEvidence, FiveCsReviewItem, FiveCsSection
from app.models.recommendation import (
    CreditRecommendationFactor,
    CreditRecommendationPreparation,
    CreditRecommendationReviewItem,
    FiveCsRefreshRun,
)
from app.models.research import ResearchFinding, ResearchQuery, ResearchRun
from app.services.credit_recommendation.policy import (
    ENGINE_VERSION,
    POLICY_VERSION,
    SUMMARY_VERSION,
    policy,
    policy_number,
    recommendation_status,
)

DISCLAIMER = "This is a credit recommendation preparation layer, not a final lending decision. No approval, rejection, sanction amount, pricing, or credit limit has been generated."


@dataclass(frozen=True)
class Factor:
    code: str
    category: str
    title: str
    description: str
    source_type: str
    source_id: UUID
    confidence: float
    severity: str | None = None


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _category(impact: str) -> str:
    return (
        "STRENGTH"
        if impact == "POSITIVE"
        else "RISK"
        if impact == "NEGATIVE"
        else "REVIEW_REQUIRED"
    )


def _critical_code(observation_code: str) -> str | None:
    configured = cast(dict[str, str], policy()["critical_risk_codes"])
    direct = configured.get(observation_code)
    if direct:
        return direct
    upper = observation_code.upper()
    if "NEGATIVE_EQUITY" in upper:
        return "CRITICAL_NEGATIVE_EQUITY"
    if "NEGATIVE" in upper and ("OCF" in upper or "OPERATING_CASH" in upper):
        return "CRITICAL_PERSISTENT_NEGATIVE_OCF"
    if "INTEREST_COVERAGE" in upper and ("BELOW_ONE" in upper or "WEAK" in upper):
        return "CRITICAL_INTEREST_COVERAGE_BELOW_ONE"
    if "INSOLVENCY" in upper:
        return "CRITICAL_INSOLVENCY_PROCEEDING"
    return None


class CreditRecommendationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def prepare(
        self,
        document_id: UUID,
        *,
        scope: FinancialScope | None = None,
        five_cs_assessment_id: UUID | None = None,
        research_run_id: UUID | None = None,
        fusion_experiment_id: UUID | None = None,
    ) -> dict[str, object]:
        document = self.session.get(Document, document_id)
        if document is None:
            raise ValueError("DOCUMENT_NOT_FOUND")
        five_cs = self._five_cs(document_id, scope, five_cs_assessment_id)
        credit = self.session.get(CreditAssessment, five_cs.credit_assessment_id)
        if credit is None or credit.document_id != document_id:
            raise ValueError("CREDIT_ASSESSMENT_NOT_FOUND")
        if five_cs.engine_version != "five_cs_engine_v2":
            raise ValueError("REFRESHED_FIVE_CS_REQUIRED")
        refresh = self.session.scalar(
            select(FiveCsRefreshRun).where(
                FiveCsRefreshRun.refreshed_five_cs_assessment_id == five_cs.id
            )
        )
        if refresh is None:
            raise ValueError("FIVE_CS_REFRESH_LINEAGE_NOT_FOUND")
        effective_research_id = research_run_id or refresh.research_run_id
        if effective_research_id != refresh.research_run_id:
            raise ValueError("RESEARCH_REFRESH_MISMATCH")
        research = self.session.get(ResearchRun, effective_research_id)
        if research is None or research.company_id != document.company_id:
            raise ValueError("RESEARCH_RUN_NOT_FOUND")
        fusion = self._fusion(fusion_experiment_id, document_id, credit.id)
        input_hash = _hash(
            {
                "document": str(document_id),
                "credit": [str(credit.id), credit.input_hash],
                "five_cs": [str(five_cs.id), five_cs.input_hash],
                "research": [str(research.id), research.input_hash],
                "fusion": str(fusion.id) if fusion else None,
                "policy": policy(),
                "engine": ENGINE_VERSION,
            }
        )
        existing = self.session.scalar(
            select(CreditRecommendationPreparation).where(
                CreditRecommendationPreparation.document_id == document_id,
                CreditRecommendationPreparation.input_hash == input_hash,
                CreditRecommendationPreparation.policy_version == POLICY_VERSION,
                CreditRecommendationPreparation.engine_version == ENGINE_VERSION,
            )
        )
        if existing:
            return recommendation_payload(self.session, existing, idempotent=True)
        self._audit(
            document,
            credit.analysis_job_id,
            "CREDIT_RECOMMENDATION_PREPARATION_STARTED",
            {"credit_assessment_id": str(credit.id), "five_cs_assessment_id": str(five_cs.id)},
        )
        factors = self._factors(credit, five_cs, research, fusion)
        reviews = self._reviews(five_cs, research)
        conflict = (
            credit.status.value == "CONFLICTING"
            or five_cs.status == "CONFLICTING"
            or any(
                item.status == "CONFLICTING"
                for item in self.session.scalars(
                    select(ResearchFinding).where(ResearchFinding.research_run_id == research.id)
                )
            )
        )
        if conflict:
            factors.append(
                Factor(
                    "CRITICAL_FINANCIAL_CONFLICT",
                    "CRITICAL_RISK",
                    "Conflicting evidence",
                    "Unresolved source evidence conflicts require human review.",
                    "FIVE_CS_ASSESSMENT",
                    five_cs.id,
                    min(float(credit.confidence_score), five_cs.overall_confidence),
                    "CRITICAL",
                )
            )
        critical_count = sum(item.category == "CRITICAL_RISK" for item in factors)
        risk_count = sum(item.category == "RISK" for item in factors)
        strength_count = sum(item.category == "STRENGTH" for item in factors)
        missing_count = sum(item.category == "MISSING_EVIDENCE" for item in factors)
        open_review_count = len(reviews) + sum(
            item.category == "REVIEW_REQUIRED" for item in factors
        )
        sections = {
            item.section: item
            for item in self.session.scalars(
                select(FiveCsSection).where(FiveCsSection.five_cs_assessment_id == five_cs.id)
            )
        }
        inputs_ready = credit.status.value in cast(
            list[str], policy()["acceptable_credit_statuses"]
        ) and research.status in cast(list[str], policy()["acceptable_research_statuses"])
        sufficient = (
            float(credit.component_coverage) >= policy_number("minimum_day10_coverage")
            and five_cs.overall_completeness >= policy_number("minimum_five_cs_completeness")
            and five_cs.overall_confidence >= policy_number("minimum_five_cs_confidence")
            and sections.get("CAPACITY") is not None
            and sections["CAPACITY"].completeness_score
            >= policy_number("minimum_capacity_completeness")
            and sections.get("CAPITAL") is not None
            and sections["CAPITAL"].completeness_score
            >= policy_number("minimum_capital_completeness")
        )
        status = recommendation_status(
            inputs_ready=inputs_ready,
            conflict=conflict,
            critical_count=critical_count,
            sufficient=sufficient,
            review_count=open_review_count,
            missing_count=missing_count,
        )
        completeness = round(
            (
                float(credit.component_coverage)
                + five_cs.overall_completeness
                + self._research_coverage(research)
            )
            / 3,
            4,
        )
        confidence = round(
            (
                float(credit.confidence_score)
                + five_cs.overall_confidence
                + self._research_confidence(research)
            )
            / 3,
            4,
        )
        if not research.scopes or not {"LEGAL", "RATINGS", "INDUSTRY", "SECTOR"}.issubset(
            set(research.scopes)
        ):
            confidence = min(confidence, policy_number("missing_external_confidence_cap"))
        if research.status in {"PARTIAL", "NEEDS_REVIEW"}:
            confidence = min(confidence, policy_number("partial_research_confidence_cap"))
        if conflict:
            confidence = min(confidence, policy_number("conflict_confidence_cap"))
        row = CreditRecommendationPreparation(
            analysis_job_id=credit.analysis_job_id,
            company_id=document.company_id,
            document_id=document_id,
            credit_assessment_id=credit.id,
            five_cs_assessment_id=five_cs.id,
            research_run_id=research.id,
            fusion_experiment_id=fusion.id if fusion else None,
            status=status,
            overall_confidence=confidence,
            overall_completeness=completeness,
            critical_risk_count=critical_count,
            risk_count=risk_count,
            strength_count=strength_count,
            review_item_count=open_review_count,
            missing_evidence_count=missing_count,
            summary_text=self._summary(status, factors, reviews),
            summary_version=SUMMARY_VERSION,
            policy_version=POLICY_VERSION,
            engine_version=ENGINE_VERSION,
            input_hash=input_hash,
        )
        self.session.add(row)
        self.session.flush()
        for item in factors:
            saved = CreditRecommendationFactor(
                recommendation_preparation_id=row.id,
                factor_code=item.code,
                category=item.category,
                title=item.title,
                description=item.description,
                source_type=item.source_type,
                source_reference_id=item.source_id,
                confidence_score=item.confidence,
                severity=item.severity,
            )
            self.session.add(saved)
            self._audit(
                document,
                credit.analysis_job_id,
                "CREDIT_RECOMMENDATION_FACTOR_CREATED",
                {
                    "preparation_id": str(row.id),
                    "factor_code": item.code,
                    "category": item.category,
                },
            )
        for code, category, message, blocking, source_type, source_id in reviews:
            self.session.add(
                CreditRecommendationReviewItem(
                    recommendation_preparation_id=row.id,
                    review_code=code,
                    category=category,
                    message=message,
                    blocking=blocking,
                    resolved=False,
                    source_type=source_type,
                    source_reference_id=source_id,
                )
            )
            self._audit(
                document,
                credit.analysis_job_id,
                "CREDIT_RECOMMENDATION_REVIEW_REQUIRED",
                {"preparation_id": str(row.id), "review_code": code},
            )
        self.session.flush()
        self._audit(
            document,
            credit.analysis_job_id,
            "CREDIT_RECOMMENDATION_PREPARED",
            {"preparation_id": str(row.id), "status": status},
        )
        return recommendation_payload(self.session, row)

    def _five_cs(
        self, document_id: UUID, scope: FinancialScope | None, assessment_id: UUID | None
    ) -> FiveCsAssessment:
        if assessment_id:
            row = self.session.get(FiveCsAssessment, assessment_id)
            if (
                row is None
                or row.document_id != document_id
                or (scope and row.statement_scope != scope)
            ):
                raise ValueError("FIVE_CS_ASSESSMENT_NOT_FOUND")
            return row
        query = select(FiveCsAssessment).where(
            FiveCsAssessment.document_id == document_id,
            FiveCsAssessment.engine_version == "five_cs_engine_v2",
        )
        if scope:
            query = query.where(FiveCsAssessment.statement_scope == scope)
        row = self.session.scalar(
            query.order_by(FiveCsAssessment.created_at.desc(), FiveCsAssessment.id.desc())
        )
        if row is None:
            raise ValueError("REFRESHED_FIVE_CS_REQUIRED")
        return row

    def _fusion(
        self, fusion_id: UUID | None, document_id: UUID, credit_id: UUID
    ) -> CreditFusionExperiment | None:
        if fusion_id is None:
            return None
        row = self.session.get(CreditFusionExperiment, fusion_id)
        if row is None or row.document_id != document_id or row.credit_assessment_id != credit_id:
            raise ValueError("FUSION_EXPERIMENT_MISMATCH")
        return row

    def _factors(
        self,
        credit: CreditAssessment,
        five_cs: FiveCsAssessment,
        research: ResearchRun,
        fusion: CreditFusionExperiment | None,
    ) -> list[Factor]:
        result: list[Factor] = []
        for rule in self.session.scalars(
            select(CreditRuleResult).where(CreditRuleResult.credit_assessment_id == credit.id)
        ):
            category = (
                "STRENGTH"
                if rule.reason_type.value == "POSITIVE"
                else "RISK"
                if rule.reason_type.value == "NEGATIVE"
                else "REVIEW_REQUIRED"
            )
            result.append(
                Factor(
                    f"DAY10_{rule.rule_code}",
                    category,
                    rule.rule_code.replace("_", " ").title(),
                    rule.message,
                    "CREDIT_RULE_RESULT",
                    rule.id,
                    rule.confidence_score,
                    "HIGH" if category == "RISK" and float(rule.score_impact) < -10 else None,
                )
            )
        rows = self.session.execute(
            select(FiveCsEvidence, FiveCsSection.section)
            .join(FiveCsSection)
            .where(FiveCsSection.five_cs_assessment_id == five_cs.id)
        ).all()
        for evidence, section in rows:
            if evidence.impact == "NEUTRAL":
                continue
            critical = _critical_code(evidence.observation_code)
            category = (
                "CRITICAL_RISK"
                if critical and evidence.impact == "NEGATIVE"
                else "MISSING_EVIDENCE"
                if evidence.status == "UNAVAILABLE"
                else _category(evidence.impact)
            )
            code = critical or f"FIVE_CS_{evidence.observation_code}"
            result.append(
                Factor(
                    code,
                    category,
                    evidence.title,
                    evidence.description,
                    evidence.source_type or "FIVE_CS_EVIDENCE",
                    evidence.source_reference_id or evidence.id,
                    evidence.confidence_score,
                    "CRITICAL"
                    if category == "CRITICAL_RISK"
                    else "HIGH"
                    if category == "RISK"
                    else None,
                )
            )
        if fusion:
            result.append(
                Factor(
                    "EXPERIMENTAL_FUSION_CONTEXT",
                    "EXPERIMENTAL_CONTEXT",
                    "Experimental ML fusion context",
                    f"Experimental fusion status {fusion.status}; production use permitted is {fusion.production_use_permitted}.",
                    "CREDIT_FUSION_EXPERIMENT",
                    fusion.id,
                    fusion.fusion_confidence,
                    "INFO",
                )
            )
        unique: dict[tuple[str, str, UUID], Factor] = {}
        for item in result:
            unique[(item.code, item.source_type, item.source_id)] = item
        return list(unique.values())

    def _reviews(
        self, five_cs: FiveCsAssessment, research: ResearchRun
    ) -> list[tuple[str, str, str, bool, str | None, UUID | None]]:
        values = [
            (
                item.reason_code,
                item.section
                if item.section in {"CHARACTER", "CAPACITY", "CAPITAL", "COLLATERAL", "CONDITIONS"}
                else "DATA",
                item.message,
                item.priority == "CRITICAL",
                "FIVE_CS_REVIEW_ITEM",
                item.id,
            )
            for item in self.session.scalars(
                select(FiveCsReviewItem).where(
                    FiveCsReviewItem.five_cs_assessment_id == five_cs.id,
                    FiveCsReviewItem.status == "OPEN",
                )
            )
        ]
        for query in self.session.scalars(
            select(ResearchQuery).where(
                ResearchQuery.research_run_id == research.id,
                ResearchQuery.status.in_(["FAILED", "PARTIAL"]),
            )
        ):
            values.append(
                (
                    f"RESEARCH_{query.scope}_{query.status}",
                    "RESEARCH",
                    f"{query.scope.title()} research coverage is {query.status.lower()}.",
                    False,
                    "RESEARCH_QUERY",
                    query.id,
                )
            )
        return list({item[0]: item for item in values}.values())

    @staticmethod
    def _research_coverage(run: ResearchRun) -> float:
        raw = run.coverage_json.get("coverage_ratio")
        if isinstance(raw, (int, float, str)):
            return max(0.0, min(1.0, float(raw)))
        if not run.scopes:
            return 0.0
        covered = 0
        for scope in run.scopes:
            scope_coverage = run.coverage_json.get(scope)
            if isinstance(scope_coverage, dict) and scope_coverage.get("queried"):
                covered += 1
        return covered / len(run.scopes)

    def _research_confidence(self, run: ResearchRun) -> float:
        values = [
            row.confidence
            for row in self.session.scalars(
                select(ResearchFinding).where(
                    ResearchFinding.research_run_id == run.id,
                    ResearchFinding.status.notin_(["STALE", "CONFLICTING"]),
                )
            )
        ]
        return round(sum(values) / len(values), 4) if values else 0.5

    @staticmethod
    def _summary(
        status: str,
        factors: list[Factor],
        reviews: list[tuple[str, str, str, bool, str | None, UUID | None]],
    ) -> str:
        strengths = sum(item.category == "STRENGTH" for item in factors)
        risks = sum(item.category in {"RISK", "CRITICAL_RISK"} for item in factors)
        return f"The case is {status.lower().replace('_', ' ')} with {strengths} documented strength(s), {risks} documented risk(s), and {len(reviews)} explicit review item(s). Evidence is prepared for human decision review; no lending outcome is produced."

    def _audit(
        self, document: Document, job_id: UUID, event: str, metadata: dict[str, object]
    ) -> None:
        write_audit_log(
            self.session,
            entity_type="credit_recommendation",
            entity_id=document.id,
            action=event,
            event_type=event,
            company_id=document.company_id,
            analysis_job_id=job_id,
            metadata_json=metadata,
        )


def recommendation_payload(
    session: Session, row: CreditRecommendationPreparation, *, idempotent: bool = False
) -> dict[str, object]:
    factors = session.scalars(
        select(CreditRecommendationFactor)
        .where(CreditRecommendationFactor.recommendation_preparation_id == row.id)
        .order_by(CreditRecommendationFactor.category, CreditRecommendationFactor.created_at)
    ).all()
    reviews = session.scalars(
        select(CreditRecommendationReviewItem)
        .where(CreditRecommendationReviewItem.recommendation_preparation_id == row.id)
        .order_by(
            CreditRecommendationReviewItem.blocking.desc(),
            CreditRecommendationReviewItem.created_at,
        )
    ).all()
    return {
        "preparation_id": row.id,
        "document_id": row.document_id,
        "status": row.status,
        "overall_confidence": row.overall_confidence,
        "overall_completeness": row.overall_completeness,
        "counts": {
            "critical_risks": row.critical_risk_count,
            "risks": row.risk_count,
            "strengths": row.strength_count,
            "review_items": row.review_item_count,
            "missing_evidence": row.missing_evidence_count,
        },
        "summary": row.summary_text,
        "policy_version": row.policy_version,
        "engine_version": row.engine_version,
        "summary_version": row.summary_version,
        "lineage": {
            "credit_assessment_id": row.credit_assessment_id,
            "five_cs_assessment_id": row.five_cs_assessment_id,
            "research_run_id": row.research_run_id,
            "fusion_experiment_id": row.fusion_experiment_id,
        },
        "factors": [factor_payload(item) for item in factors],
        "review_items": [review_payload(item) for item in reviews],
        "final_lending_decision": None,
        "proposed_credit_limit": None,
        "pricing": None,
        "disclaimer": DISCLAIMER,
        "idempotent": idempotent,
    }


def factor_payload(row: CreditRecommendationFactor) -> dict[str, object]:
    return {
        "factor_id": row.id,
        "factor_code": row.factor_code,
        "category": row.category,
        "title": row.title,
        "description": row.description,
        "source_type": row.source_type,
        "source_reference_id": row.source_reference_id,
        "confidence": row.confidence_score,
        "severity": row.severity,
    }


def review_payload(row: CreditRecommendationReviewItem) -> dict[str, object]:
    return {
        "review_item_id": row.id,
        "review_code": row.review_code,
        "category": row.category,
        "message": row.message,
        "blocking": row.blocking,
        "resolved": row.resolved,
        "source_type": row.source_type,
        "source_reference_id": row.source_reference_id,
    }
