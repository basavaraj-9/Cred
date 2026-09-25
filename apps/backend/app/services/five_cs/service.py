from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.repositories.audit_log import write_audit_log
from app.models.company_profile import CompanyProfile
from app.models.credit import CreditAssessment, CreditSubscore
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.domain_classification import DomainClassification, DomainClassificationEvidence
from app.models.enums import CreditComponent, FinancialScope
from app.models.financial import FinancialLineItem
from app.models.financial_analysis import (
    FinancialRatio,
    FinancialRatioInput,
    NormalizedFinancialValue,
)
from app.models.financial_trend import (
    FinancialAnomaly,
    FinancialAnomalyInput,
    FinancialTrend,
    FinancialTrendInput,
)
from app.models.five_cs import FiveCsAssessment, FiveCsEvidence, FiveCsReviewItem, FiveCsSection
from app.services.five_cs.capacity import build_capacity
from app.services.five_cs.capital import build_capital
from app.services.five_cs.character import build_character
from app.services.five_cs.collateral import build_collateral
from app.services.five_cs.completeness import overall_completeness, section_completeness
from app.services.five_cs.conditions import build_conditions
from app.services.five_cs.confidence import overall_confidence, section_confidence, section_status
from app.services.five_cs.policy import (
    ENGINE_VERSION,
    POLICY_VERSION,
    SECTIONS,
    SUMMARY_VERSION,
    five_cs_policy,
)
from app.services.five_cs.schemas import EvidenceDraft, SectionResult
from app.services.five_cs.summaries import summary

DISCLAIMER = "Evidence synthesis only. This is not a credit score, approval, rejection, sanction, pricing, collateral valuation, or lending decision."


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _latest_by_name(
    rows: list[object], name_attribute: str, period_attribute: str = "fiscal_year"
) -> dict[str, object]:
    result: dict[str, object] = {}
    for row in sorted(
        rows, key=lambda item: str(getattr(item, period_attribute, "")), reverse=True
    ):
        result.setdefault(str(getattr(row, name_attribute)), row)
    return result


def _value_page(
    session: Session, value: NormalizedFinancialValue, seen: set[UUID] | None = None
) -> tuple[UUID, int] | None:
    seen = seen or set()
    if value.id in seen:
        return None
    seen.add(value.id)
    if value.financial_line_item_id:
        item = session.get(FinancialLineItem, value.financial_line_item_id)
        return (item.document_page_id, item.page_number) if item else None
    for source_id in value.input_value_ids or []:
        source = session.get(NormalizedFinancialValue, UUID(source_id))
        if source and (lineage := _value_page(session, source, seen)):
            return lineage
    return None


def _source_page(session: Session, source: object) -> tuple[UUID, int] | None:
    if isinstance(source, NormalizedFinancialValue):
        return _value_page(session, source)
    if isinstance(source, FinancialRatio):
        ratio_link = session.scalar(
            select(FinancialRatioInput).where(FinancialRatioInput.financial_ratio_id == source.id)
        )
        value = (
            session.get(NormalizedFinancialValue, ratio_link.normalized_financial_value_id)
            if ratio_link
            else None
        )
        return _value_page(session, value) if value else None
    if isinstance(source, FinancialTrend):
        trend_link = session.scalar(
            select(FinancialTrendInput).where(FinancialTrendInput.financial_trend_id == source.id)
        )
        if trend_link and trend_link.normalized_financial_value_id:
            value = session.get(NormalizedFinancialValue, trend_link.normalized_financial_value_id)
            return _value_page(session, value) if value else None
        if trend_link and trend_link.financial_ratio_id:
            ratio = session.get(FinancialRatio, trend_link.financial_ratio_id)
            return _source_page(session, ratio) if ratio else None
    if isinstance(source, FinancialAnomaly):
        anomaly_link = session.scalar(
            select(FinancialAnomalyInput).where(
                FinancialAnomalyInput.financial_anomaly_id == source.id
            )
        )
        if anomaly_link:
            for model, source_id in (
                (FinancialTrend, anomaly_link.financial_trend_id),
                (NormalizedFinancialValue, anomaly_link.normalized_financial_value_id),
                (FinancialRatio, anomaly_link.financial_ratio_id),
            ):
                if source_id and (row := session.get(model, source_id)):
                    return _source_page(session, row)
    if isinstance(source, DomainClassification):
        domain_link = session.scalar(
            select(DomainClassificationEvidence).where(
                DomainClassificationEvidence.domain_classification_id == source.id
            )
        )
        page = session.get(DocumentPage, domain_link.document_page_id) if domain_link else None
        return (domain_link.document_page_id, page.page_number) if domain_link and page else None
    return None


def _review_code(item: EvidenceDraft) -> str:
    mapping = {
        "CHARACTER_PROMOTER_RESEARCH_UNAVAILABLE": "CHARACTER_EXTERNAL_DATA_REQUIRED",
        "CHARACTER_REPAYMENT_HISTORY_UNAVAILABLE": "CHARACTER_EXTERNAL_DATA_REQUIRED",
        "CHARACTER_EXTERNAL_BACKGROUND_UNAVAILABLE": "CHARACTER_EXTERNAL_DATA_REQUIRED",
        "COLLATERAL_SECURITY_MENTIONED": "COLLATERAL_DETAILS_REQUIRED",
        "COLLATERAL_SECURED_BORROWINGS_MENTIONED": "COLLATERAL_DETAILS_REQUIRED",
        "COLLATERAL_VALUE_UNAVAILABLE": "COLLATERAL_VALUE_REQUIRED",
        "CONDITIONS_EXTERNAL_SECTOR_OUTLOOK_UNAVAILABLE": "CONDITIONS_EXTERNAL_RESEARCH_REQUIRED",
        "CONDITIONS_REGULATORY_RESEARCH_UNAVAILABLE": "CONDITIONS_EXTERNAL_RESEARCH_REQUIRED",
        "CONDITIONS_DOMAIN_UNVERIFIED": "DOMAIN_CLASSIFICATION_REVIEW_REQUIRED",
        "CAPITAL_NEGATIVE_EQUITY": "CAPITAL_CONFLICTING_EQUITY",
    }
    return mapping.get(item.observation_code, item.observation_code)


class FiveCsAssessmentService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def analyze(
        self, document_id: UUID, scope: FinancialScope | None = None
    ) -> list[dict[str, object]]:
        document = self.session.get(Document, document_id)
        if document is None:
            raise ValueError("DOCUMENT_NOT_FOUND")
        profile = self.session.scalar(
            select(CompanyProfile)
            .where(CompanyProfile.document_id == document_id)
            .order_by(CompanyProfile.created_at.desc())
        )
        if profile is None:
            raise ValueError("FIVE_CS_COMPANY_PROFILE_REQUIRED")
        query = select(CreditAssessment).where(CreditAssessment.document_id == document_id)
        if scope:
            query = query.where(CreditAssessment.statement_scope == scope)
        assessments = self.session.scalars(query.order_by(CreditAssessment.created_at.desc())).all()
        latest: dict[FinancialScope, CreditAssessment] = {}
        for row in assessments:
            latest.setdefault(row.statement_scope, row)
        if not latest:
            raise ValueError("FIVE_CS_CREDIT_ASSESSMENT_REQUIRED")
        return [
            self._analyze_scope(document, profile, assessment) for assessment in latest.values()
        ]

    def _analyze_scope(
        self, document: Document, profile: CompanyProfile, assessment: CreditAssessment
    ) -> dict[str, object]:
        policy = five_cs_policy()
        pages = list(
            self.session.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == document.id)
                .order_by(DocumentPage.page_number)
            )
        )
        domain = self.session.scalar(
            select(DomainClassification)
            .where(DomainClassification.company_profile_id == profile.id)
            .order_by(DomainClassification.created_at.desc())
        )
        values_rows = list(
            self.session.scalars(
                select(NormalizedFinancialValue).where(
                    NormalizedFinancialValue.run_id == assessment.financial_analysis_run_id,
                    NormalizedFinancialValue.statement_scope == assessment.statement_scope,
                )
            )
        )
        ratios_rows = list(
            self.session.scalars(
                select(FinancialRatio).where(
                    FinancialRatio.run_id == assessment.financial_analysis_run_id,
                    FinancialRatio.statement_scope == assessment.statement_scope,
                )
            )
        )
        trends_rows = list(
            self.session.scalars(
                select(FinancialTrend).where(
                    FinancialTrend.run_id == assessment.financial_trend_run_id,
                    FinancialTrend.statement_scope == assessment.statement_scope,
                )
            )
        )
        anomalies_rows = list(
            self.session.scalars(
                select(FinancialAnomaly).where(
                    FinancialAnomaly.run_id == assessment.financial_trend_run_id,
                    FinancialAnomaly.statement_scope == assessment.statement_scope,
                )
            )
        )
        values = cast(
            dict[str, NormalizedFinancialValue],
            _latest_by_name(cast(list[object], values_rows), "canonical_name"),
        )
        ratios = cast(
            dict[str, FinancialRatio],
            _latest_by_name(cast(list[object], ratios_rows), "ratio_name"),
        )
        trends = cast(
            dict[str, FinancialTrend],
            _latest_by_name(cast(list[object], trends_rows), "metric_name", "end_fiscal_year"),
        )
        anomalies = {row.anomaly_type: row for row in anomalies_rows}
        subscores = {
            row.component_name: row
            for row in self.session.scalars(
                select(CreditSubscore).where(CreditSubscore.credit_assessment_id == assessment.id)
            )
        }
        sources: list[object] = [*values_rows, *ratios_rows, *trends_rows, *anomalies_rows]
        if domain:
            sources.append(domain)
        lineage = {
            cast(UUID, cast(Any, source).id): page
            for source in sources
            if (page := _source_page(self.session, source))
        }
        page_fingerprints = [
            (str(page.id), page.page_number, _digest(page.text_content)) for page in pages
        ]
        input_payload = {
            "document_id": str(document.id),
            "scope": assessment.statement_scope.value,
            "profile": [
                str(profile.id),
                profile.extractor_version,
                profile.status.value,
                profile.identity_match_status.value,
            ],
            "financial_analysis_run_id": str(assessment.financial_analysis_run_id),
            "financial_trend_run_id": str(assessment.financial_trend_run_id),
            "credit_assessment": [str(assessment.id), assessment.input_hash],
            "domain": [
                str(domain.id),
                domain.model_version,
                domain.status.value,
                domain.input_text_hash,
            ]
            if domain
            else None,
            "page_fingerprints": page_fingerprints,
            "policy": policy,
        }
        input_hash = _digest(input_payload)
        existing = self.session.scalar(
            select(FiveCsAssessment).where(
                FiveCsAssessment.document_id == document.id,
                FiveCsAssessment.statement_scope == assessment.statement_scope,
                FiveCsAssessment.input_hash == input_hash,
                FiveCsAssessment.policy_version == POLICY_VERSION,
                FiveCsAssessment.engine_version == ENGINE_VERSION,
            )
        )
        if existing:
            return assessment_payload(self.session, existing, idempotent=True)
        write_audit_log(
            self.session,
            entity_type="five_cs_assessment",
            entity_id=UUID(int=0),
            action="FIVE_CS_ANALYSIS_STARTED",
            event_type="FIVE_CS_ANALYSIS_STARTED",
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            metadata_json={
                "scope": assessment.statement_scope.value,
                "policy_version": POLICY_VERSION,
            },
        )
        financial_conflict = assessment.status.value == "CONFLICTING" or any(
            row.normalization_status.value == "CONFLICTING" for row in values_rows
        )
        thresholds = cast(dict[str, float], policy["thresholds"])
        evidence_by_section = {
            "CHARACTER": build_character(profile, pages, financial_conflict),
            "CAPACITY": build_capacity(
                ratios,
                values,
                trends,
                anomalies,
                subscores.get(CreditComponent.REPAYMENT_CAPACITY),
                lineage,
                thresholds,
            ),
            "CAPITAL": build_capital(
                ratios,
                values,
                trends,
                subscores.get(CreditComponent.FINANCIAL_STRENGTH),
                lineage,
                thresholds,
            ),
            "COLLATERAL": build_collateral(pages),
            "CONDITIONS": build_conditions(profile, domain, trends, anomalies, lineage),
        }
        section_results: list[SectionResult] = []
        for name in SECTIONS:
            evidence = evidence_by_section[name]
            completeness = section_completeness(name, evidence, policy)
            confidence = section_confidence(name, evidence, policy)
            section_results.append(
                SectionResult(
                    name,
                    section_status(name, evidence, completeness, confidence, policy),
                    confidence,
                    completeness,
                    summary(name, evidence),
                    tuple(evidence),
                )
            )
        completeness_values = [item.completeness for item in section_results]
        confidence_values = [item.confidence for item in section_results]
        overall_complete = overall_completeness(completeness_values)
        overall_conf = overall_confidence(confidence_values, completeness_values)
        overall_status = (
            "CONFLICTING"
            if any(item.status == "CONFLICTING" for item in section_results)
            else "NEEDS_REVIEW"
            if any(item.status == "NEEDS_REVIEW" for item in section_results)
            else "PARTIAL"
        )
        row = FiveCsAssessment(
            analysis_job_id=document.analysis_job_id,
            company_id=document.company_id,
            document_id=document.id,
            company_profile_id=profile.id,
            financial_analysis_run_id=assessment.financial_analysis_run_id,
            financial_trend_run_id=assessment.financial_trend_run_id,
            credit_assessment_id=assessment.id,
            domain_classification_id=domain.id if domain else None,
            statement_scope=assessment.statement_scope,
            overall_completeness=overall_complete,
            overall_confidence=overall_conf,
            status=overall_status,
            policy_version=POLICY_VERSION,
            engine_version=ENGINE_VERSION,
            summary_version=SUMMARY_VERSION,
            input_hash=input_hash,
        )
        self.session.add(row)
        self.session.flush()
        review_count = 0
        for result in section_results:
            section = FiveCsSection(
                five_cs_assessment_id=row.id,
                section=result.section,
                status=result.status,
                confidence_score=result.confidence,
                completeness_score=result.completeness,
                positive_count=sum(item.impact == "POSITIVE" for item in result.evidence),
                negative_count=sum(item.impact == "NEGATIVE" for item in result.evidence),
                review_count=sum(item.impact == "REVIEW" for item in result.evidence),
                summary_text=result.summary,
                summary_version=SUMMARY_VERSION,
            )
            self.session.add(section)
            self.session.flush()
            seen_review_codes: set[str] = set()
            for item in result.evidence:
                evidence_row = FiveCsEvidence(
                    five_cs_section_id=section.id,
                    evidence_type=item.evidence_type,
                    observation_code=item.observation_code,
                    title=item.title,
                    description=item.description,
                    impact=item.impact,
                    source_type=item.source_type,
                    source_reference_id=item.source_id,
                    document_page_id=item.document_page_id,
                    page_number=item.page_number,
                    raw_value=item.raw_value,
                    normalized_value=item.normalized_value,
                    confidence_score=item.confidence,
                    status=item.status,
                    created_at=datetime.now(UTC),
                )
                self.session.add(evidence_row)
                self.session.flush()
                if item.impact == "REVIEW" or (
                    result.section in {"CAPACITY", "CAPITAL"} and item.impact == "NEGATIVE"
                ):
                    reason_code = _review_code(item)
                    if reason_code not in seen_review_codes:
                        self.session.add(
                            FiveCsReviewItem(
                                five_cs_assessment_id=row.id,
                                five_cs_evidence_id=evidence_row.id,
                                section=result.section,
                                reason_code=reason_code,
                                message=item.description,
                                priority="HIGH"
                                if item.status in {"CONFLICTING", "NEEDS_REVIEW"}
                                else "MEDIUM",
                                status="OPEN",
                            )
                        )
                        seen_review_codes.add(reason_code)
                        review_count += 1
            write_audit_log(
                self.session,
                entity_type="five_cs_section",
                entity_id=section.id,
                action="FIVE_CS_SECTION_COMPLETED",
                event_type="FIVE_CS_SECTION_COMPLETED",
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
                metadata_json={
                    "assessment_id": str(row.id),
                    "scope": assessment.statement_scope.value,
                    "section": result.section,
                    "status": result.status,
                    "completeness": result.completeness,
                    "confidence": result.confidence,
                    "policy_version": POLICY_VERSION,
                },
            )
        if review_count:
            write_audit_log(
                self.session,
                entity_type="five_cs_assessment",
                entity_id=row.id,
                action="FIVE_CS_REVIEW_REQUIRED",
                event_type="FIVE_CS_REVIEW_REQUIRED",
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
                metadata_json={
                    "assessment_id": str(row.id),
                    "scope": assessment.statement_scope.value,
                    "review_count": review_count,
                    "policy_version": POLICY_VERSION,
                },
            )
        write_audit_log(
            self.session,
            entity_type="five_cs_assessment",
            entity_id=row.id,
            action="FIVE_CS_ANALYSIS_COMPLETED",
            event_type="FIVE_CS_ANALYSIS_COMPLETED",
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            metadata_json={
                "assessment_id": str(row.id),
                "scope": assessment.statement_scope.value,
                "statuses": {item.section: item.status for item in section_results},
                "completeness": overall_complete,
                "confidence": overall_conf,
                "review_count": review_count,
                "policy_version": POLICY_VERSION,
            },
        )
        if any(
            item.observation_code
            in {"COLLATERAL_SECURITY_MENTIONED", "COLLATERAL_SECURED_BORROWINGS_MENTIONED"}
            for item in evidence_by_section["COLLATERAL"]
        ):
            write_audit_log(
                self.session,
                entity_type="five_cs_assessment",
                entity_id=row.id,
                action="COLLATERAL_EVIDENCE_FOUND",
                event_type="COLLATERAL_EVIDENCE_FOUND",
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
                metadata_json={
                    "assessment_id": str(row.id),
                    "scope": assessment.statement_scope.value,
                    "policy_version": POLICY_VERSION,
                },
            )
        self.session.flush()
        return assessment_payload(self.session, row)


def assessment_payload(
    session: Session, row: FiveCsAssessment, *, idempotent: bool = False
) -> dict[str, object]:
    sections = list(
        session.scalars(
            select(FiveCsSection)
            .where(FiveCsSection.five_cs_assessment_id == row.id)
            .order_by(FiveCsSection.section)
        )
    )
    latest_credit = session.scalar(
        select(CreditAssessment)
        .where(
            CreditAssessment.document_id == row.document_id,
            CreditAssessment.statement_scope == row.statement_scope,
        )
        .order_by(CreditAssessment.created_at.desc(), CreditAssessment.id.desc())
    )
    return {
        "assessment_id": row.id,
        "document_id": row.document_id,
        "scope": row.statement_scope.value,
        "status": row.status,
        "overall_completeness": row.overall_completeness,
        "overall_confidence": row.overall_confidence,
        "policy_version": row.policy_version,
        "engine_version": row.engine_version,
        "summary_version": row.summary_version,
        "stale": bool(latest_credit and latest_credit.id != row.credit_assessment_id),
        "sections": {
            item.section.lower(): {
                "section_id": item.id,
                "status": item.status,
                "confidence": item.confidence_score,
                "completeness": item.completeness_score,
                "positive_count": item.positive_count,
                "negative_count": item.negative_count,
                "review_count": item.review_count,
                "summary": item.summary_text,
            }
            for item in sections
        },
        "no_total_credit_score": True,
        "lending_decision": None,
        "disclaimer": DISCLAIMER,
        "idempotent": idempotent,
    }


def latest_document_assessments(session: Session, document_id: UUID) -> list[FiveCsAssessment]:
    rows = session.scalars(
        select(FiveCsAssessment)
        .where(FiveCsAssessment.document_id == document_id)
        .order_by(FiveCsAssessment.created_at.desc())
    ).all()
    latest: dict[FinancialScope, FiveCsAssessment] = {}
    for row in rows:
        latest.setdefault(row.statement_scope, row)
    return list(latest.values())
