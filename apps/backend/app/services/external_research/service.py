from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.repositories.audit_log import write_audit_log
from app.models.company import Company
from app.models.company_profile import CompanyProfile
from app.models.domain_classification import DomainClassification
from app.models.extracted_field import ExtractedField
from app.models.research import (
    ResearchEvidence,
    ResearchFinding,
    ResearchFindingSource,
    ResearchQuery,
    ResearchRun,
    ResearchSource,
)
from app.services.external_research.deduplication import near_duplicate_title
from app.services.external_research.entity import entity_match
from app.services.external_research.policy import (
    ENGINE_VERSION,
    EVIDENCE_EXTRACTOR_VERSION,
    FINDING_VERSION,
    FRESHNESS_POLICY_VERSION,
    QUERY_BUILDER_VERSION,
    SOURCE_POLICY_VERSION,
    freshness,
    source_quality,
)
from app.services.external_research.providers.base import ResearchProvider
from app.services.external_research.providers.fixture import FixtureResearchProvider
from app.services.external_research.query_builder import build_queries, verified_context
from app.services.external_research.schemas import ProviderResult
from app.services.external_research.security import normalize_url


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _candidate(scope: str) -> str | None:
    if scope in {"LEGAL", "PROMOTER"}:
        return "CHARACTER"
    if scope in {"RATINGS", "INDUSTRY", "SECTOR"}:
        return "CONDITIONS"
    return None


class ExternalResearchService:
    def __init__(self, session: Session, provider: ResearchProvider | None = None) -> None:
        self.session = session
        self.provider = provider or FixtureResearchProvider()

    def research_company(
        self, company_id: UUID, scopes: list[str], refresh: bool = False
    ) -> ResearchRun:
        company = self.session.get(Company, company_id)
        if company is None:
            raise ValueError("COMPANY_NOT_FOUND")
        profile = self.session.scalar(
            select(CompanyProfile)
            .where(CompanyProfile.company_id == company_id)
            .order_by(CompanyProfile.created_at.desc())
        )
        if profile is None:
            raise ValueError("COMPANY_PROFILE_REQUIRED")
        fields = list(
            self.session.scalars(
                select(ExtractedField).where(ExtractedField.company_profile_id == profile.id)
            )
        )
        domain = self.session.scalar(
            select(DomainClassification)
            .where(DomainClassification.company_profile_id == profile.id)
            .order_by(DomainClassification.created_at.desc())
        )
        context = verified_context(profile, fields, domain)
        normalized_scopes = list(dict.fromkeys(item.upper() for item in scopes))
        queries = build_queries(context, normalized_scopes)
        identity = {
            "profile_id": str(profile.id),
            "profile_version": profile.extractor_version,
            "legal_name": context.legal_name,
            "aliases": context.aliases,
            "promoters": context.promoters,
            "domain_id": str(domain.id) if domain else None,
            "domain_status": domain.status.value if domain else None,
            "domain_version": domain.model_version if domain else None,
            "scopes": normalized_scopes,
            "queries": [(item.scope, item.text) for item in queries],
            "query_builder": QUERY_BUILDER_VERSION,
            "provider": [self.provider.name, self.provider.version],
            "policies": [SOURCE_POLICY_VERSION, FRESHNESS_POLICY_VERSION],
        }
        input_hash = _digest(identity)
        recent = self.session.scalar(
            select(ResearchRun)
            .where(
                ResearchRun.company_id == company_id,
                ResearchRun.input_hash == input_hash,
                ResearchRun.status.in_(("COMPLETED", "PARTIAL", "NEEDS_REVIEW")),
            )
            .order_by(ResearchRun.created_at.desc())
        )
        if not refresh and recent and recent.created_at >= datetime.now(UTC) - timedelta(hours=24):
            return recent
        prior_refresh = self.session.scalar(
            select(func.max(ResearchRun.refresh_number)).where(
                ResearchRun.company_id == company_id, ResearchRun.input_hash == input_hash
            )
        )
        refresh_number = (int(prior_refresh) if prior_refresh is not None else -1) + 1
        now = datetime.now(UTC)
        run = ResearchRun(
            company_id=company_id,
            company_profile_id=profile.id,
            domain_classification_id=domain.id if domain else None,
            status="SEARCHING",
            scopes=normalized_scopes,
            provider_name=self.provider.name,
            provider_version=self.provider.version,
            engine_version=ENGINE_VERSION,
            query_builder_version=QUERY_BUILDER_VERSION,
            source_policy_version=SOURCE_POLICY_VERSION,
            freshness_policy_version=FRESHNESS_POLICY_VERSION,
            evidence_extractor_version=EVIDENCE_EXTRACTOR_VERSION,
            finding_version=FINDING_VERSION,
            input_hash=input_hash,
            refresh_number=refresh_number,
            started_at=now,
            coverage_json={},
        )
        self.session.add(run)
        self.session.flush()
        self._audit(run, "RESEARCH_RUN_STARTED", {"scopes": normalized_scopes})
        failures = 0
        rejected = 0
        duplicate_hashes: dict[str, UUID] = {}
        evidence_rows: list[ResearchEvidence] = []
        coverage: dict[str, object] = {
            scope: {"queried": False, "verified_findings": 0} for scope in normalized_scopes
        }
        for draft in queries:
            query = ResearchQuery(
                research_run_id=run.id,
                scope=draft.scope,
                query_text=draft.text,
                query_hash=_digest(draft.text.casefold()),
                status="PENDING",
                result_count=0,
            )
            self.session.add(query)
            self.session.flush()
            cast(dict[str, object], coverage[draft.scope])["queried"] = True
            try:
                results = self.provider.search(draft, context.legal_name)
            except Exception as exc:
                query.status = "FAILED"
                query.error_code = type(exc).__name__
                failures += 1
                self._audit(
                    run,
                    "RESEARCH_SOURCE_FAILED",
                    {"scope": draft.scope, "error_code": type(exc).__name__},
                )
                continue
            query.result_count = len(results)
            query.status = "COMPLETED"
            self._audit(
                run, "RESEARCH_QUERY_EXECUTED", {"scope": draft.scope, "result_count": len(results)}
            )
            for result in results:
                source, evidence = self._persist_result(
                    run, query, result, context.legal_name, context.aliases, duplicate_hashes
                )
                if source.status == "FAILED":
                    failures += 1
                elif source.status in {"REJECTED", "NEEDS_REVIEW"}:
                    rejected += 1
                if evidence:
                    evidence_rows.append(evidence)
        findings = self._create_findings(run, evidence_rows)
        for finding in findings:
            cast(dict[str, object], coverage[finding.category])["verified_findings"] = (
                cast(int, cast(dict[str, object], coverage[finding.category])["verified_findings"])
                + 1
            )
        run.coverage_json = coverage
        run.completed_at = datetime.now(UTC)
        run.status = (
            "PARTIAL"
            if failures
            else "NEEDS_REVIEW"
            if rejected or any(row.status in {"NEEDS_REVIEW", "CONFLICTING"} for row in findings)
            else "COMPLETED"
        )
        self._audit(
            run,
            "RESEARCH_RUN_COMPLETED",
            {"status": run.status, "finding_count": len(findings), "failure_count": failures},
        )
        self.session.flush()
        return run

    def _persist_result(
        self,
        run: ResearchRun,
        query: ResearchQuery,
        result: ProviderResult,
        legal_name: str,
        aliases: tuple[str, ...],
        duplicate_hashes: dict[str, UUID],
    ) -> tuple[ResearchSource, ResearchEvidence | None]:
        canonical = normalize_url(result.url)
        same_url = self.session.scalar(
            select(ResearchSource).where(
                ResearchSource.research_run_id == run.id,
                ResearchSource.canonical_url == canonical,
            )
        )
        if same_url is not None:
            return same_url, None
        tier, quality = source_quality(result.source_type)
        content_hash = _digest(" ".join(result.text.split()).casefold()) if result.text else None
        match_status, match_score = entity_match(legal_name, result.entity_name, aliases)
        duplicate_id = duplicate_hashes.get(content_hash or "")
        if duplicate_id is None:
            previous_sources = self.session.scalars(
                select(ResearchSource).where(ResearchSource.research_run_id == run.id)
            ).all()
            title_match = next(
                (
                    row
                    for row in previous_sources
                    if row.status in {"RETRIEVED", "DUPLICATE"}
                    and near_duplicate_title(row.title, result.title)
                ),
                None,
            )
            duplicate_id = title_match.id if title_match else None
        status = (
            "FAILED"
            if result.failure_code
            else "REJECTED"
            if match_status == "MISMATCH"
            else "NEEDS_REVIEW"
            if match_status == "AMBIGUOUS"
            else "DUPLICATE"
            if duplicate_id
            else "RETRIEVED"
        )
        source = ResearchSource(
            research_run_id=run.id,
            research_query_id=query.id,
            title=result.title,
            publisher=result.publisher,
            source_type=result.source_type,
            source_tier=tier,
            quality_score=quality,
            original_url=result.url,
            canonical_url=canonical,
            content_hash=content_hash,
            normalized_text=result.text or None,
            mime_type=result.mime_type,
            publication_date=result.publication_date,
            event_date=result.event_date,
            retrieved_at=datetime.now(UTC),
            freshness_status=freshness(result.publication_date, result.scope),
            entity_match_status=match_status,
            entity_match_score=match_score,
            status=status,
            duplicate_of_source_id=duplicate_id,
            error_code=result.failure_code,
            error_message="Fixture source retrieval timed out" if result.failure_code else None,
        )
        self.session.add(source)
        self.session.flush()
        if content_hash and not duplicate_id and status == "RETRIEVED":
            duplicate_hashes[content_hash] = source.id
        self._audit(
            run,
            "RESEARCH_SOURCE_FAILED" if status == "FAILED" else "RESEARCH_SOURCE_RETRIEVED",
            {"source_id": str(source.id), "status": status, "publisher": result.publisher},
        )
        if status != "RETRIEVED" or not result.text:
            return source, None
        evidence_text = " ".join(result.text.split())[:2000]
        stale = source.freshness_status == "STALE"
        review = result.impact == "REVIEW" or quality < 0.7 or match_score < 0.8
        confidence = round(min(0.99, quality * match_score * (0.75 if stale else 1.0)), 4)
        evidence = ResearchEvidence(
            research_run_id=run.id,
            research_source_id=source.id,
            category=result.scope,
            event_code=result.event_code,
            evidence_text=evidence_text,
            evidence_hash=_digest(evidence_text.casefold()),
            entity_type="PROMOTER" if result.scope == "PROMOTER" else "COMPANY",
            entity_name=result.entity_name,
            impact=result.impact,
            confidence=confidence,
            status="STALE" if stale else "NEEDS_REVIEW" if review else "VERIFIED",
            candidate_section=_candidate(result.scope),
            event_date=result.event_date,
            attributes_json=result.attributes,
        )
        self.session.add(evidence)
        self.session.flush()
        self._audit(
            run,
            "RESEARCH_EVIDENCE_EXTRACTED",
            {"evidence_id": str(evidence.id), "event_code": result.event_code},
        )
        return source, evidence

    def _create_findings(
        self, run: ResearchRun, evidence_rows: list[ResearchEvidence]
    ) -> list[ResearchFinding]:
        groups: dict[tuple[str, str, object], list[ResearchEvidence]] = defaultdict(list)
        for evidence in evidence_rows:
            groups[(evidence.event_code, evidence.entity_name, evidence.event_date)].append(
                evidence
            )
        findings: list[ResearchFinding] = []
        for (code, entity_name, event_date), rows in groups.items():
            loaded_sources = [
                self.session.get(ResearchSource, row.research_source_id) for row in rows
            ]
            sources: list[ResearchSource] = [
                cast(ResearchSource, source) for source in loaded_sources if source is not None
            ]
            impacts = {row.impact for row in rows}
            independent = len({(row.publisher, row.content_hash) for row in sources})
            conflicting = len(impacts - {"REVIEW"}) > 1
            status = (
                "CONFLICTING"
                if conflicting
                else "NEEDS_REVIEW"
                if any(row.status == "NEEDS_REVIEW" for row in rows)
                else "STALE"
                if all(row.status == "STALE" for row in rows)
                else "CORROBORATED"
                if independent > 1
                else "VERIFIED"
                if any(
                    row.source_type in {"OFFICIAL", "REGULATOR", "GOVERNMENT", "RATING_AGENCY"}
                    for row in sources
                )
                else "SINGLE_SOURCE"
            )
            confidence = sum(row.confidence for row in rows) / len(rows)
            if independent > 1:
                confidence = min(0.99, confidence + 0.05)
            if conflicting:
                confidence *= 0.65
            finding = ResearchFinding(
                research_run_id=run.id,
                finding_code=code,
                category=rows[0].category,
                summary=rows[0].evidence_text,
                entity_type=rows[0].entity_type,
                entity_name=entity_name,
                impact="REVIEW" if conflicting else rows[0].impact,
                status=status,
                confidence=round(confidence, 4),
                candidate_section=rows[0].candidate_section,
                event_date=event_date,
                first_published_at=min(
                    (row.publication_date for row in sources if row.publication_date), default=None
                ),
                latest_published_at=max(
                    (row.publication_date for row in sources if row.publication_date), default=None
                ),
                contradiction_code="CONFLICTING_SOURCE_IMPACTS" if conflicting else None,
                source_count=independent,
            )
            self.session.add(finding)
            self.session.flush()
            for evidence, source in zip(rows, sources, strict=True):
                self.session.add(
                    ResearchFindingSource(
                        research_finding_id=finding.id,
                        research_source_id=source.id,
                        research_evidence_id=evidence.id,
                        is_independent=True,
                    )
                )
            self._audit(
                run,
                "RESEARCH_CONTRADICTION_DETECTED" if conflicting else "RESEARCH_FINDING_CREATED",
                {"finding_id": str(finding.id), "finding_code": code, "status": status},
            )
            if status in {"NEEDS_REVIEW", "CONFLICTING"}:
                self._audit(
                    run,
                    "RESEARCH_REVIEW_REQUIRED",
                    {"finding_id": str(finding.id), "status": status},
                )
            findings.append(finding)
        return findings

    def _audit(self, run: ResearchRun, event: str, metadata: dict[str, object]) -> None:
        write_audit_log(
            self.session,
            entity_type="research_run",
            entity_id=run.id,
            action=event,
            event_type=event,
            company_id=run.company_id,
            metadata_json=metadata,
        )


def run_payload(session: Session, run: ResearchRun) -> dict[str, object]:
    counts = {}
    for name, model in (
        ("query_count", ResearchQuery),
        ("source_count", ResearchSource),
        ("evidence_count", ResearchEvidence),
        ("finding_count", ResearchFinding),
    ):
        counts[name] = (
            session.scalar(
                select(func.count()).select_from(model).where(model.research_run_id == run.id)
            )
            or 0
        )
    counts["review_count"] = (
        session.scalar(
            select(func.count())
            .select_from(ResearchFinding)
            .where(
                ResearchFinding.research_run_id == run.id,
                ResearchFinding.status.in_(("NEEDS_REVIEW", "CONFLICTING")),
            )
        )
        or 0
    )
    return {
        "research_run_id": run.id,
        "company_id": run.company_id,
        "company_profile_id": run.company_profile_id,
        "status": run.status,
        "scopes": run.scopes,
        "provider": {"name": run.provider_name, "version": run.provider_version},
        "versions": {
            "engine": run.engine_version,
            "query_builder": run.query_builder_version,
            "source_policy": run.source_policy_version,
            "freshness_policy": run.freshness_policy_version,
            "evidence_extractor": run.evidence_extractor_version,
            "finding": run.finding_version,
        },
        "input_hash": run.input_hash,
        "refresh_number": run.refresh_number,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "coverage": run.coverage_json,
        **counts,
        "day15_automatically_modified": False,
        "final_lending_decision": "NOT_GENERATED",
    }
