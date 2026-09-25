from __future__ import annotations

# ruff: noqa: E501
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.analysis_job import AnalysisJob
from app.models.company import Company
from app.models.company_profile import CompanyProfile
from app.models.document import Document
from app.models.enums import IdentityMatchStatus, ProfileStatus
from app.models.five_cs import FiveCsAssessment
from app.models.research import (
    ResearchEvidence,
    ResearchFinding,
    ResearchQuery,
    ResearchRun,
    ResearchSource,
)
from app.services.external_research.classification import (
    classify_legal_event,
    classify_outlook,
    classify_rating_action,
)
from app.services.external_research.deduplication import near_duplicate_title, title_similarity
from app.services.external_research.entity import entity_match
from app.services.external_research.policy import (
    FRESHNESS_POLICY_VERSION,
    QUERY_BUILDER_VERSION,
    freshness,
    source_quality,
)
from app.services.external_research.providers.base import ResearchProvider
from app.services.external_research.providers.fixture import FixtureResearchProvider
from app.services.external_research.query_builder import (
    QueryContext,
    build_queries,
    verified_context,
)
from app.services.external_research.schemas import ProviderResult, QueryDraft
from app.services.external_research.security import (
    MAX_FETCH_BYTES,
    normalize_url,
    validate_content,
    validate_public_url,
)
from app.services.external_research.service import ExternalResearchService


def test_company_queries_use_verified_name() -> None:
    rows = build_queries(
        QueryContext("Example Industries Limited", (), (), None, None), ["COMPANY", "LEGAL"]
    )
    assert len(rows) == 2
    assert all('"Example Industries Limited"' in row.text for row in rows)


def test_low_confidence_domain_not_used_and_promoter_requires_identity() -> None:
    rows = build_queries(
        QueryContext("Example Ltd", (), (), None, None), ["PROMOTER", "INDUSTRY", "SECTOR"]
    )
    assert rows == []


def test_query_builder_version_and_deduplication() -> None:
    assert QUERY_BUILDER_VERSION == "research_query_builder_v1"
    rows = build_queries(QueryContext("Example Ltd", (), (), None, None), ["LEGAL", "LEGAL"])
    assert len(rows) == 1


def test_unverified_company_identity_rejected() -> None:
    profile = CompanyProfile(
        legal_name="Example Ltd",
        overall_confidence=0.7,
        status=ProfileStatus.NEEDS_REVIEW,
        identity_match_status=IdentityMatchStatus.POSSIBLE_MATCH,
        extractor_version="test",
    )
    with pytest.raises(ValueError, match="VERIFIED_COMPANY_IDENTITY_REQUIRED"):
        verified_context(profile, [], None)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "https://Example.com/story/?utm_source=x&b=2&a=1#part",
            "https://example.com/story?a=1&b=2",
        ),
        ("http://example.com", "http://example.com/"),
    ],
)
def test_source_url_normalization(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


def test_ssrf_controls() -> None:
    for url in (
        "http://localhost/a",
        "http://127.0.0.1/a",
        "file:///etc/passwd",
        "http://169.254.169.254/latest",
    ):
        with pytest.raises(ValueError):
            validate_public_url(url, resolve_dns=False)
    assert (
        validate_public_url("https://8.8.8.8/source", resolve_dns=False) == "https://8.8.8.8/source"
    )


def test_content_type_and_size_limits() -> None:
    validate_content("text/html; charset=utf-8", 100)
    with pytest.raises(ValueError, match="CONTENT_TYPE"):
        validate_content("application/x-msdownload", 10)
    with pytest.raises(ValueError, match="TOO_LARGE"):
        validate_content("text/plain", MAX_FETCH_BYTES + 1)


def test_source_quality_tiers() -> None:
    assert source_quality("REGULATOR") == (1, 0.98)
    assert source_quality("REPUTABLE_NEWS")[0] == 2
    assert source_quality("unknown")[0] == 3


def test_freshness_policy_current_stale_and_historical() -> None:
    today = date(2026, 9, 25)
    assert freshness(today - timedelta(days=20), "RATINGS", today) == "CURRENT"
    assert freshness(today - timedelta(days=500), "RATINGS", today) == "STALE"
    assert freshness(today - timedelta(days=900), "LEGAL", today) == "HISTORICAL"
    assert FRESHNESS_POLICY_VERSION == "research_freshness_policy_v1"


def test_exact_alias_ambiguous_and_wrong_company_matching() -> None:
    assert entity_match("ABC Power Limited", "ABC Power Ltd") == ("MATCHED", 1.0)
    assert entity_match("ABC Power Limited", "AP Energy", ("AP Energy Limited",))[0] == "MATCHED"
    assert entity_match("ABC Power Holdings Limited", "ABC Power Limited")[0] == "AMBIGUOUS"
    status, score = entity_match("Example Industries Limited", "ABC Power LLC")
    assert status == "MISMATCH" and score == 0


def test_fixture_rating_legal_industry_and_partial_failure() -> None:
    provider = FixtureResearchProvider()
    rating = provider.search(QueryDraft("RATINGS", "x"), "Example Ltd")[0]
    assert (
        rating.event_code == "CREDIT_RATING_DOWNGRADED"
        and rating.attributes["action"] == "DOWNGRADE"
    )
    legal = provider.search(QueryDraft("LEGAL", "x"), "Example Ltd")
    assert {row.attributes.get("legal_status") for row in legal} >= {
        "PENALTY_ORDERED",
        "ALLEGATION_UNPROVEN",
    }
    industry = provider.search(QueryDraft("INDUSTRY", "x"), "Example Ltd")
    assert all(row.event_code == "INDUSTRY_DEMAND_OUTLOOK_MIXED" for row in industry)
    assert (
        provider.search(QueryDraft("SECTOR", "x"), "Example Ltd")[-1].failure_code
        == "SOURCE_TIMEOUT"
    )


def test_fixture_wrong_company_and_duplicate_content() -> None:
    provider = FixtureResearchProvider()
    company = provider.search(QueryDraft("COMPANY", "x"), "Example Industries Limited")
    assert company[1].entity_name == "ABC Power LLC"
    industry = provider.search(QueryDraft("INDUSTRY", "x"), "Example Industries Limited")
    assert industry[0].text == industry[1].text


@pytest.mark.parametrize(
    ("text", "code", "impact"),
    [
        ("The case was dismissed by the court", "LEGAL_CASE_DISMISSED", "NEUTRAL"),
        ("The regulator imposed a monetary penalty", "REGULATORY_PENALTY_ORDER", "NEGATIVE"),
        ("The company is under investigation", "REGULATORY_INVESTIGATION_REPORTED", "REVIEW"),
        ("Fraud was alleged in a complaint", "LEGAL_ALLEGATION_REPORTED", "REVIEW"),
        ("The director was convicted", "LEGAL_CONVICTION_REPORTED", "NEGATIVE"),
    ],
)
def test_legal_statuses_remain_precise(text: str, code: str, impact: str) -> None:
    assert classify_legal_event(text) == (code, impact)


@pytest.mark.parametrize(
    ("text", "action"),
    [
        ("Rating upgraded from BBB to A", "UPGRADE"),
        ("Rating downgraded to BBB", "DOWNGRADE"),
        ("Rating affirmed at A", "AFFIRMED"),
        ("Rating withdrawn", "WITHDRAWN"),
        ("Outlook changed from stable to negative", "OUTLOOK_CHANGE"),
    ],
)
def test_rating_actions(text: str, action: str) -> None:
    assert classify_rating_action(text) == action


def test_outlook_classification_uses_explicit_event_language() -> None:
    assert classify_outlook("Strong demand growth, but cost pressure and weak demand overseas") == (
        "OUTLOOK_MIXED",
        "MIXED",
    )
    assert classify_outlook("Company revenue declined 20%") == ("OUTLOOK_NEGATIVE", "NEGATIVE")


def test_near_duplicate_titles() -> None:
    assert near_duplicate_title(
        "Regulator issues penalty order for Example Limited",
        "Regulator issues penalty order for Example Ltd",
    )
    assert title_similarity("Rating upgrade", "Factory shutdown") == 0


def _seed_company(session: Session) -> tuple[Company, Document, CompanyProfile]:
    company = Company(legal_name="Day 16 Example Industries Limited", country="India")
    session.add(company)
    session.flush()
    job = AnalysisJob(company_id=company.id)
    session.add(job)
    session.flush()
    document = Document(
        analysis_job_id=job.id, company_id=company.id, original_filename="day16.pdf"
    )
    session.add(document)
    session.flush()
    profile = CompanyProfile(
        analysis_job_id=job.id,
        company_id=company.id,
        document_id=document.id,
        legal_name=company.legal_name,
        business_description="Manufactures industrial equipment.",
        overall_confidence=0.95,
        status=ProfileStatus.VERIFIED,
        identity_match_status=IdentityMatchStatus.MATCHED,
        extractor_version="company_profile_v1",
    )
    session.add(profile)
    session.flush()
    return company, document, profile


class ContradictingProvider(ResearchProvider):
    name = "contradiction_fixture"
    version = "v1"

    def search(self, query: QueryDraft, legal_name: str) -> list[ProviderResult]:
        event_date = date(2026, 8, 1)
        return [
            ProviderResult(
                query.scope,
                "Order remains effective",
                "Regulator A",
                "REGULATOR",
                "https://reg-a.example.test/order",
                f"The order concerning {legal_name} remains effective.",
                legal_name,
                "REGULATORY_ORDER_STATUS",
                "NEGATIVE",
                event_date,
                event_date,
            ),
            ProviderResult(
                query.scope,
                "Order has been set aside",
                "Court Registry",
                "GOVERNMENT",
                "https://court.example.test/order",
                f"The order concerning {legal_name} has been set aside.",
                legal_name,
                "REGULATORY_ORDER_STATUS",
                "POSITIVE",
                event_date,
                event_date,
            ),
        ]


class PartialProvider(ResearchProvider):
    name = "partial_fixture"
    version = "v1"

    def search(self, query: QueryDraft, legal_name: str) -> list[ProviderResult]:
        event_date = date(2026, 8, 2)
        return [
            ProviderResult(
                query.scope,
                "Unavailable source",
                "Source A",
                "OTHER",
                "https://a.example.test/item",
                "",
                legal_name,
                "SOURCE_UNAVAILABLE",
                "REVIEW",
                event_date,
                event_date,
                failure_code="SOURCE_TIMEOUT",
            ),
            ProviderResult(
                query.scope,
                "Case dismissed",
                "Court Registry",
                "GOVERNMENT",
                "https://court.example.test/dismissed",
                f"A proceeding concerning {legal_name} was dismissed.",
                legal_name,
                "LEGAL_CASE_DISMISSED",
                "NEUTRAL",
                event_date,
                event_date,
            ),
        ]


def test_conflicting_sources_require_review(db_session: Session) -> None:
    company, _, _ = _seed_company(db_session)
    run = ExternalResearchService(db_session, ContradictingProvider()).research_company(
        company.id, ["LEGAL"]
    )
    finding = db_session.scalar(
        select(ResearchFinding).where(ResearchFinding.research_run_id == run.id)
    )
    assert finding is not None
    assert finding.status == "CONFLICTING"
    assert finding.contradiction_code == "CONFLICTING_SOURCE_IMPACTS"
    assert finding.confidence < 0.8


def test_single_source_failure_produces_partial_run_and_keeps_good_finding(
    db_session: Session,
) -> None:
    company, _, _ = _seed_company(db_session)
    run = ExternalResearchService(db_session, PartialProvider()).research_company(
        company.id, ["LEGAL"]
    )
    assert run.status == "PARTIAL"
    sources = list(
        db_session.scalars(select(ResearchSource).where(ResearchSource.research_run_id == run.id))
    )
    assert {row.status for row in sources} == {"FAILED", "RETRIEVED"}
    finding = db_session.scalar(
        select(ResearchFinding).where(ResearchFinding.research_run_id == run.id)
    )
    assert finding is not None and finding.finding_code == "LEGAL_CASE_DISMISSED"


def test_research_persistence_lineage_idempotency_refresh_and_day15_unchanged(
    db_session: Session,
) -> None:
    company, _, _ = _seed_company(db_session)
    before_five_cs = db_session.scalar(select(func.count()).select_from(FiveCsAssessment))
    service = ExternalResearchService(db_session)
    first = service.research_company(company.id, ["COMPANY", "LEGAL", "RATINGS"], False)
    same = service.research_company(company.id, ["COMPANY", "LEGAL", "RATINGS"], False)
    refreshed = service.research_company(company.id, ["COMPANY", "LEGAL", "RATINGS"], True)
    assert first.id == same.id
    assert refreshed.id != first.id and refreshed.refresh_number == 1
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(ResearchQuery)
            .where(ResearchQuery.research_run_id == first.id)
        )
        == 3
    )
    sources = list(
        db_session.scalars(select(ResearchSource).where(ResearchSource.research_run_id == first.id))
    )
    assert any(
        row.status == "REJECTED" and row.entity_match_status == "MISMATCH" for row in sources
    )
    assert all(row.retrieved_at <= datetime.now(UTC) for row in sources)
    evidence = list(
        db_session.scalars(
            select(ResearchEvidence).where(ResearchEvidence.research_run_id == first.id)
        )
    )
    assert evidence and all(
        row.research_source_id and len(row.evidence_hash) == 64 and len(row.evidence_text) <= 2000
        for row in evidence
    )
    findings = list(
        db_session.scalars(
            select(ResearchFinding).where(ResearchFinding.research_run_id == first.id)
        )
    )
    assert {row.candidate_section for row in findings} >= {"CHARACTER", "CONDITIONS"}
    allegation = next(
        row for row in findings if row.finding_code == "REGULATORY_INVESTIGATION_REPORTED"
    )
    assert "investigation" in allegation.summary.lower() and allegation.status == "NEEDS_REVIEW"
    rating = next(row for row in findings if row.finding_code == "CREDIT_RATING_DOWNGRADED")
    assert rating.candidate_section == "CONDITIONS"
    assert db_session.scalar(select(func.count()).select_from(FiveCsAssessment)) == before_five_cs
    assert first.status == "NEEDS_REVIEW"


def test_research_model_versions_are_persisted(db_session: Session) -> None:
    company, _, _ = _seed_company(db_session)
    row = ExternalResearchService(db_session).research_company(company.id, ["LEGAL"], False)
    assert row.engine_version == "external_research_engine_v1"
    assert row.query_builder_version == QUERY_BUILDER_VERSION
    assert row.source_policy_version == "research_source_quality_v1"


def test_unknown_scope_is_controlled(db_session: Session) -> None:
    company, _, _ = _seed_company(db_session)
    with pytest.raises(ValueError, match="RESEARCH_SCOPE_INVALID"):
        ExternalResearchService(db_session).research_company(company.id, ["STOCK"], False)


def test_database_constraints_registered() -> None:
    assert {table.name for table in ResearchRun.metadata.sorted_tables} >= {
        "research_runs",
        "research_queries",
        "research_sources",
        "research_evidence",
        "research_findings",
        "research_finding_sources",
    }
