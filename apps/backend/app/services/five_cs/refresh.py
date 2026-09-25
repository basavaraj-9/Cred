from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.repositories.audit_log import write_audit_log
from app.models.five_cs import FiveCsAssessment, FiveCsEvidence, FiveCsReviewItem, FiveCsSection
from app.models.recommendation import FiveCsRefreshRun, FiveCsResearchEvidenceLink
from app.models.research import (
    ResearchEvidence,
    ResearchFinding,
    ResearchFindingSource,
    ResearchRun,
    ResearchSource,
)
from app.services.five_cs.research_mapping import mapping_for
from app.services.five_cs.service import assessment_payload

REFRESH_POLICY_VERSION = "five_cs_research_refresh_v1"
REFRESH_ENGINE_VERSION = "five_cs_engine_v2"
REFRESH_SUMMARY_VERSION = "five_cs_summary_v2"


@lru_cache
def refresh_policy() -> dict[str, object]:
    value = cast(
        dict[str, object],
        json.loads((Path(__file__).parent / "five_cs_research_refresh_policy_v1.json").read_text()),
    )
    if (
        value.get("version") != REFRESH_POLICY_VERSION
        or value.get("engine_version") != REFRESH_ENGINE_VERSION
    ):
        raise ValueError("FIVE_CS_REFRESH_POLICY_INVALID")
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _policy_number(key: str) -> float:
    value = refresh_policy()[key]
    if not isinstance(value, (int, float)):
        raise ValueError("FIVE_CS_REFRESH_POLICY_INVALID")
    return float(value)


def _effective_finding_confidence(session: Session, finding: ResearchFinding) -> float:
    _, freshness, _ = _finding_source_context(session, finding.id)
    multiplier = 0.7 if freshness == "HISTORICAL" else 1.0
    return round(finding.confidence * multiplier, 4)


def _finding_source_context(session: Session, finding_id: UUID) -> tuple[float, str, UUID | None]:
    links = session.execute(
        select(ResearchFindingSource, ResearchSource)
        .join(ResearchSource, ResearchSource.id == ResearchFindingSource.research_source_id)
        .where(ResearchFindingSource.research_finding_id == finding_id)
    ).all()
    if not links:
        return 0.0, "UNKNOWN", None
    ranked = sorted(links, key=lambda item: item[1].quality_score, reverse=True)
    evidence_id = ranked[0][0].research_evidence_id
    return ranked[0][1].quality_score, ranked[0][1].freshness_status, evidence_id


def eligible_findings(
    session: Session, run: ResearchRun
) -> tuple[list[ResearchFinding], list[ResearchFinding]]:
    policy = refresh_policy()
    accepted: list[ResearchFinding] = []
    rejected: list[ResearchFinding] = []
    rows = session.scalars(
        select(ResearchFinding)
        .where(ResearchFinding.research_run_id == run.id)
        .order_by(ResearchFinding.event_date.desc().nullslast(), ResearchFinding.created_at.desc())
    ).all()
    for row in rows:
        quality, source_freshness, _ = _finding_source_context(session, row.id)
        mapping = mapping_for(row)
        valid = (
            mapping is not None
            and row.status in cast(list[str], policy["eligible_finding_statuses"])
            and row.status != "CONFLICTING"
            and row.confidence >= _policy_number("minimum_finding_confidence")
            and quality >= _policy_number("minimum_source_quality")
            and source_freshness in cast(list[str], policy["eligible_freshness"])
        )
        (accepted if valid else rejected).append(row)
    latest_rating: dict[tuple[str, str], ResearchFinding] = {}
    retained: list[ResearchFinding] = []
    for row in accepted:
        if row.category != "RATINGS":
            retained.append(row)
            continue
        _, _, evidence_id = _finding_source_context(session, row.id)
        evidence = session.get(ResearchEvidence, evidence_id) if evidence_id else None
        attributes = evidence.attributes_json if evidence else {}
        agency = str(attributes.get("agency") or row.entity_name).casefold()
        instrument = str(attributes.get("instrument") or "entity_rating").casefold()
        key = (agency, instrument)
        if key not in latest_rating:
            latest_rating[key] = row
        else:
            rejected.append(row)
    accepted = retained + list(latest_rating.values())
    return accepted, rejected


class FiveCsResearchRefreshService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def refresh(self, base_assessment_id: UUID, research_run_id: UUID) -> dict[str, object]:
        base = self.session.get(FiveCsAssessment, base_assessment_id)
        if base is None:
            raise ValueError("FIVE_CS_ASSESSMENT_NOT_FOUND")
        if base.engine_version != "five_cs_engine_v1":
            raise ValueError("FIVE_CS_BASE_ASSESSMENT_REQUIRED")
        research_run = self.session.get(ResearchRun, research_run_id)
        if research_run is None:
            raise ValueError("RESEARCH_RUN_NOT_FOUND")
        if research_run.company_id != base.company_id:
            raise ValueError("RESEARCH_COMPANY_MISMATCH")
        accepted, rejected = eligible_findings(self.session, research_run)
        input_hash = _digest(
            {
                "base": [str(base.id), base.input_hash],
                "research_run": [str(research_run.id), research_run.input_hash],
                "findings": [
                    (str(row.id), row.status, row.confidence, row.event_date) for row in accepted
                ],
                "policy": refresh_policy(),
                "engine": REFRESH_ENGINE_VERSION,
            }
        )
        existing = self.session.scalar(
            select(FiveCsRefreshRun).where(
                FiveCsRefreshRun.base_five_cs_assessment_id == base.id,
                FiveCsRefreshRun.research_run_id == research_run.id,
                FiveCsRefreshRun.input_hash == input_hash,
            )
        )
        if existing:
            return refresh_payload(self.session, existing, idempotent=True)
        self._audit(
            base,
            "FIVE_CS_RESEARCH_REFRESH_STARTED",
            {"base_assessment_id": str(base.id), "research_run_id": str(research_run.id)},
        )
        row = FiveCsAssessment(
            analysis_job_id=base.analysis_job_id,
            company_id=base.company_id,
            document_id=base.document_id,
            company_profile_id=base.company_profile_id,
            financial_analysis_run_id=base.financial_analysis_run_id,
            financial_trend_run_id=base.financial_trend_run_id,
            credit_assessment_id=base.credit_assessment_id,
            domain_classification_id=base.domain_classification_id,
            statement_scope=base.statement_scope,
            overall_completeness=base.overall_completeness,
            overall_confidence=base.overall_confidence,
            status=base.status,
            policy_version=REFRESH_POLICY_VERSION,
            engine_version=REFRESH_ENGINE_VERSION,
            summary_version=REFRESH_SUMMARY_VERSION,
            input_hash=input_hash,
        )
        self.session.add(row)
        self.session.flush()
        mapped_by_section: dict[str, list[ResearchFinding]] = {"CHARACTER": [], "CONDITIONS": []}
        for finding in accepted:
            mapping = mapping_for(finding)
            if mapping:
                mapped_by_section[mapping[0]].append(finding)
        new_reviews = 0
        resolved_reviews = 0
        updated_sections: list[str] = []
        base_sections = self.session.scalars(
            select(FiveCsSection).where(FiveCsSection.five_cs_assessment_id == base.id)
        ).all()
        for base_section in base_sections:
            findings = mapped_by_section.get(base_section.section, [])
            section = self._copy_section(row, base_section, findings)
            if findings:
                updated_sections.append(base_section.section)
            if base_section.section in {"CHARACTER", "CONDITIONS"}:
                created, resolved = self._copy_reviews(
                    base, row, base_section.section, bool(findings)
                )
                new_reviews += created
                resolved_reviews += resolved
            else:
                created, _ = self._copy_reviews(base, row, base_section.section, False)
                new_reviews += created
            for finding in findings:
                new_reviews += self._add_research_evidence(row, section, finding)
        sections = self.session.scalars(
            select(FiveCsSection).where(FiveCsSection.five_cs_assessment_id == row.id)
        ).all()
        row.overall_completeness = round(sum(item.completeness_score for item in sections) / 5, 4)
        weighted = [item.confidence_score for item in sections if item.completeness_score > 0]
        row.overall_confidence = round(sum(weighted) / len(weighted), 4) if weighted else 0.0
        row.status = (
            "CONFLICTING"
            if any(item.status == "CONFLICTING" for item in sections)
            else "NEEDS_REVIEW"
            if any(item.status == "NEEDS_REVIEW" for item in sections)
            else "PARTIAL"
            if any(item.status == "PARTIAL" for item in sections)
            else "VERIFIED"
        )
        refresh = FiveCsRefreshRun(
            base_five_cs_assessment_id=base.id,
            refreshed_five_cs_assessment_id=row.id,
            research_run_id=research_run.id,
            refresh_policy_version=REFRESH_POLICY_VERSION,
            refresh_engine_version=REFRESH_ENGINE_VERSION,
            input_hash=input_hash,
            status="NEEDS_REVIEW"
            if rejected or row.status in {"NEEDS_REVIEW", "CONFLICTING"}
            else "COMPLETED",
            updated_sections=",".join(updated_sections),
            new_review_item_count=new_reviews,
            resolved_review_item_count=resolved_reviews,
        )
        self.session.add(refresh)
        self.session.flush()
        self._audit(
            base,
            "FIVE_CS_RESEARCH_REFRESH_COMPLETED",
            {
                "refreshed_assessment_id": str(row.id),
                "research_run_id": str(research_run.id),
                "updated_sections": updated_sections,
            },
        )
        return refresh_payload(self.session, refresh)

    def _copy_section(
        self, assessment: FiveCsAssessment, base: FiveCsSection, findings: list[ResearchFinding]
    ) -> FiveCsSection:
        evidence_rows = self.session.scalars(
            select(FiveCsEvidence).where(FiveCsEvidence.five_cs_section_id == base.id)
        ).all()
        confidence = base.confidence_score
        completeness = base.completeness_score
        status = base.status
        if findings:
            external_confidence = sum(
                _effective_finding_confidence(self.session, row) for row in findings
            ) / len(findings)
            weight = _policy_number("confidence_external_weight")
            confidence = round(
                base.confidence_score * (1 - weight) + external_confidence * weight, 4
            )
            if base.section == "CHARACTER":
                completeness = min(
                    1.0,
                    base.completeness_score + _policy_number("character_completeness_increment"),
                )
            else:
                categories = {row.category for row in findings}
                key = (
                    "conditions_multi_category_increment"
                    if len(categories) > 1
                    else "conditions_single_category_increment"
                )
                completeness = min(1.0, base.completeness_score + _policy_number(key))
            if any(
                row.status == "NEEDS_REVIEW" or row.impact in {"NEGATIVE", "REVIEW"}
                for row in findings
            ):
                status = "NEEDS_REVIEW"
            elif completeness >= _policy_number(
                "verified_completeness_min"
            ) and confidence >= _policy_number("verified_confidence_min"):
                status = "VERIFIED"
            else:
                status = "PARTIAL"
        summary = base.summary_text
        if findings:
            summary += f" External research added {len(findings)} eligible {base.section.title()} finding(s). Reported legal and rating actions retain their exact source status; no broader borrower or management conclusion is inferred."
        section = FiveCsSection(
            five_cs_assessment_id=assessment.id,
            section=base.section,
            status=status,
            confidence_score=confidence,
            completeness_score=completeness,
            positive_count=base.positive_count + sum(row.impact == "POSITIVE" for row in findings),
            negative_count=base.negative_count + sum(row.impact == "NEGATIVE" for row in findings),
            review_count=base.review_count
            + sum(
                row.impact in {"REVIEW", "MIXED"} or row.status == "NEEDS_REVIEW"
                for row in findings
            ),
            summary_text=summary,
            summary_version=REFRESH_SUMMARY_VERSION,
        )
        self.session.add(section)
        self.session.flush()
        for source in evidence_rows:
            self.session.add(
                FiveCsEvidence(
                    five_cs_section_id=section.id,
                    evidence_type=source.evidence_type,
                    observation_code=source.observation_code,
                    title=source.title,
                    description=source.description,
                    impact=source.impact,
                    source_type=source.source_type,
                    source_reference_id=source.source_reference_id,
                    document_page_id=source.document_page_id,
                    page_number=source.page_number,
                    raw_value=source.raw_value,
                    normalized_value=source.normalized_value,
                    confidence_score=source.confidence_score,
                    status=source.status,
                    created_at=datetime.now(UTC),
                )
            )
        self.session.flush()
        return section

    def _copy_reviews(
        self, base: FiveCsAssessment, target: FiveCsAssessment, section: str, has_external: bool
    ) -> tuple[int, int]:
        rows = self.session.scalars(
            select(FiveCsReviewItem).where(
                FiveCsReviewItem.five_cs_assessment_id == base.id,
                FiveCsReviewItem.section == section,
            )
        ).all()
        created = 0
        resolved = 0
        for source in rows:
            if has_external and source.reason_code == "CONDITIONS_EXTERNAL_RESEARCH_REQUIRED":
                resolved += 1
                continue
            self.session.add(
                FiveCsReviewItem(
                    five_cs_assessment_id=target.id,
                    five_cs_evidence_id=None,
                    section=section,
                    reason_code=source.reason_code,
                    message=source.message,
                    priority=source.priority,
                    status="OPEN",
                )
            )
            created += 1
        return created, resolved

    def _add_research_evidence(
        self, assessment: FiveCsAssessment, section: FiveCsSection, finding: ResearchFinding
    ) -> int:
        mapping = mapping_for(finding)
        if mapping is None:
            return 0
        impact = "REVIEW" if finding.impact == "MIXED" else finding.impact
        _, freshness, research_evidence_id = _finding_source_context(self.session, finding.id)
        effective_confidence = _effective_finding_confidence(self.session, finding)
        evidence = FiveCsEvidence(
            five_cs_section_id=section.id,
            evidence_type="EXTERNAL_RESEARCH",
            observation_code=mapping[1],
            title=finding.finding_code.replace("_", " ").title(),
            description=finding.summary,
            impact=impact,
            source_type="RESEARCH_FINDING",
            source_reference_id=finding.id,
            document_page_id=None,
            page_number=None,
            raw_value=None,
            normalized_value=finding.status,
            confidence_score=effective_confidence,
            status="NEEDS_REVIEW"
            if finding.status == "NEEDS_REVIEW" or freshness == "HISTORICAL"
            else "VERIFIED",
            created_at=datetime.now(UTC),
        )
        self.session.add(evidence)
        self.session.flush()
        self.session.add(
            FiveCsResearchEvidenceLink(
                five_cs_assessment_id=assessment.id,
                five_cs_section_id=section.id,
                five_cs_evidence_id=evidence.id,
                research_finding_id=finding.id,
                research_evidence_id=research_evidence_id,
                mapping_code=mapping[1],
                impact=impact,
                status=evidence.status,
            )
        )
        if (
            finding.status == "NEEDS_REVIEW"
            or freshness == "HISTORICAL"
            or finding.impact in {"NEGATIVE", "REVIEW"}
        ):
            code = f"{mapping[1]}_REVIEW_REQUIRED"
            exists = self.session.scalar(
                select(func.count())
                .select_from(FiveCsReviewItem)
                .where(
                    FiveCsReviewItem.five_cs_assessment_id == assessment.id,
                    FiveCsReviewItem.reason_code == code,
                )
            )
            if not exists:
                self.session.add(
                    FiveCsReviewItem(
                        five_cs_assessment_id=assessment.id,
                        five_cs_evidence_id=evidence.id,
                        section=section.section,
                        reason_code=code,
                        message=finding.summary,
                        priority="HIGH" if finding.impact == "NEGATIVE" else "MEDIUM",
                        status="OPEN",
                    )
                )
                return 1
        return 0

    def _audit(self, base: FiveCsAssessment, event: str, metadata: dict[str, object]) -> None:
        write_audit_log(
            self.session,
            entity_type="five_cs_refresh",
            entity_id=base.id,
            action=event,
            event_type=event,
            company_id=base.company_id,
            analysis_job_id=base.analysis_job_id,
            metadata_json=metadata,
        )


def refresh_payload(
    session: Session, row: FiveCsRefreshRun, *, idempotent: bool = False
) -> dict[str, object]:
    assessment = session.get(FiveCsAssessment, row.refreshed_five_cs_assessment_id)
    if assessment is None:
        raise ValueError("REFRESHED_FIVE_CS_NOT_FOUND")
    return {
        "refresh_run_id": row.id,
        "base_assessment_id": row.base_five_cs_assessment_id,
        "refreshed_assessment_id": row.refreshed_five_cs_assessment_id,
        "research_run_id": row.research_run_id,
        "updated_sections": row.updated_sections.split(",") if row.updated_sections else [],
        "new_review_items": row.new_review_item_count,
        "resolved_review_items": row.resolved_review_item_count,
        "status": row.status,
        "policy_version": row.refresh_policy_version,
        "engine_version": row.refresh_engine_version,
        "assessment": assessment_payload(session, assessment, idempotent=idempotent),
        "idempotent": idempotent,
    }
