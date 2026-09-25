from __future__ import annotations

# ruff: noqa: E501
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.credit_recommendation import (
    get_credit_recommendation,
    get_recommendation_evidence,
    get_recommendation_factors,
    get_recommendation_review_items,
    list_credit_recommendations,
)
from app.models.five_cs import FiveCsAssessment, FiveCsEvidence, FiveCsSection
from app.models.recommendation import (
    CreditRecommendationFactor,
    CreditRecommendationPreparation,
    FiveCsRefreshRun,
    FiveCsResearchEvidenceLink,
)
from app.models.research import ResearchFinding
from app.services.credit_recommendation.policy import (
    ENGINE_VERSION,
    POLICY_VERSION,
    policy,
    recommendation_status,
)
from app.services.credit_recommendation.service import CreditRecommendationService
from app.services.external_research.service import ExternalResearchService
from app.services.five_cs.refresh import (
    REFRESH_ENGINE_VERSION,
    REFRESH_POLICY_VERSION,
    FiveCsResearchRefreshService,
    eligible_findings,
    refresh_policy,
)
from app.services.five_cs.research_mapping import mapping_for
from app.services.five_cs.service import FiveCsAssessmentService
from tests.test_five_cs import _context


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (
            {
                "inputs_ready": True,
                "conflict": False,
                "critical_count": 0,
                "sufficient": True,
                "review_count": 0,
                "missing_count": 0,
            },
            "READY_FOR_DECISION_REVIEW",
        ),
        (
            {
                "inputs_ready": True,
                "conflict": False,
                "critical_count": 0,
                "sufficient": True,
                "review_count": 1,
                "missing_count": 0,
            },
            "CONDITIONAL_REVIEW_REQUIRED",
        ),
        (
            {
                "inputs_ready": True,
                "conflict": False,
                "critical_count": 0,
                "sufficient": False,
                "review_count": 0,
                "missing_count": 0,
            },
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            {
                "inputs_ready": True,
                "conflict": False,
                "critical_count": 1,
                "sufficient": True,
                "review_count": 0,
                "missing_count": 0,
            },
            "CRITICAL_RISK_REVIEW",
        ),
        (
            {
                "inputs_ready": True,
                "conflict": True,
                "critical_count": 0,
                "sufficient": True,
                "review_count": 0,
                "missing_count": 0,
            },
            "DATA_CONFLICT_REVIEW",
        ),
        (
            {
                "inputs_ready": False,
                "conflict": False,
                "critical_count": 0,
                "sufficient": True,
                "review_count": 0,
                "missing_count": 0,
            },
            "NOT_READY",
        ),
    ],
)
def test_all_neutral_recommendation_statuses(arguments: dict[str, object], expected: str) -> None:
    assert recommendation_status(**arguments) == expected  # type: ignore[arg-type]


def test_policies_are_versioned_and_have_no_decision_verbs() -> None:
    assert policy()["version"] == POLICY_VERSION
    assert policy()["engine_version"] == ENGINE_VERSION
    assert refresh_policy()["version"] == REFRESH_POLICY_VERSION
    assert refresh_policy()["engine_version"] == REFRESH_ENGINE_VERSION
    states = set(policy()["readiness_states"])  # type: ignore[arg-type]
    assert states == {
        "READY_FOR_DECISION_REVIEW",
        "CONDITIONAL_REVIEW_REQUIRED",
        "INSUFFICIENT_EVIDENCE",
        "CRITICAL_RISK_REVIEW",
        "DATA_CONFLICT_REVIEW",
        "NOT_READY",
    }
    assert states.isdisjoint({"APPROVE", "REJECT", "LEND", "DECLINE"})


@pytest.mark.parametrize(
    ("code", "section", "mapped"),
    [
        ("REGULATORY_PENALTY_ORDER", "CHARACTER", "CHARACTER_REGULATORY_ACTION_REPORTED"),
        (
            "DIRECTOR_DISQUALIFICATION_REPORTED",
            "CHARACTER",
            "CHARACTER_DIRECTOR_DISQUALIFICATION_REPORTED",
        ),
        (
            "REGULATORY_INVESTIGATION_REPORTED",
            "CHARACTER",
            "CHARACTER_REGULATORY_INVESTIGATION_REPORTED",
        ),
        ("CREDIT_RATING_DOWNGRADED", "CONDITIONS", "CONDITIONS_RATING_DOWNGRADE"),
        ("INDUSTRY_OUTLOOK_NEGATIVE", "CONDITIONS", "CONDITIONS_NEGATIVE_SECTOR_OUTLOOK"),
    ],
)
def test_research_mapping(code: str, section: str, mapped: str) -> None:
    finding = ResearchFinding(
        research_run_id=uuid4(),
        finding_code=code,
        category="LEGAL",
        summary="reported",
        entity_type="COMPANY",
        entity_name="Example",
        impact="NEGATIVE",
        status="VERIFIED",
        confidence=0.9,
        source_count=1,
    )
    assert mapping_for(finding) == (section, mapped)


def test_dismissed_case_is_not_active_adverse_mapping() -> None:
    finding = ResearchFinding(
        research_run_id=uuid4(),
        finding_code="LEGAL_CASE_DISMISSED",
        category="LEGAL",
        summary="dismissed",
        entity_type="COMPANY",
        entity_name="Example",
        impact="NEUTRAL",
        status="VERIFIED",
        confidence=0.9,
        source_count=1,
    )
    assert mapping_for(finding) is None


def test_refresh_and_recommendation_are_immutable_traceable_and_idempotent(
    db_session: Session,
) -> None:
    document, credit = _context(db_session)
    base_payload = FiveCsAssessmentService(db_session).analyze(document.id, credit.statement_scope)[
        0
    ]
    base_id = base_payload["assessment_id"]
    base = db_session.get(FiveCsAssessment, base_id)
    assert base is not None
    base_hash = base.input_hash
    base_sections = {
        row.section: (row.status, row.confidence_score, row.completeness_score)
        for row in db_session.scalars(
            select(FiveCsSection).where(FiveCsSection.five_cs_assessment_id == base.id)
        )
    }
    research = ExternalResearchService(db_session).research_company(
        document.company_id, ["LEGAL", "RATINGS"], False
    )
    accepted, rejected = eligible_findings(db_session, research)
    assert {row.finding_code for row in accepted} >= {
        "REGULATORY_PENALTY_ORDER",
        "CREDIT_RATING_DOWNGRADED",
    }
    assert all(row.status != "STALE" for row in accepted)
    refreshed = FiveCsResearchRefreshService(db_session).refresh(base.id, research.id)
    repeated = FiveCsResearchRefreshService(db_session).refresh(base.id, research.id)
    assert refreshed["refreshed_assessment_id"] == repeated["refreshed_assessment_id"]
    assert repeated["idempotent"] is True
    assert refreshed["refreshed_assessment_id"] != base.id
    assert db_session.get(FiveCsAssessment, base.id).input_hash == base_hash  # type: ignore[union-attr]
    refresh_row = db_session.scalar(
        select(FiveCsRefreshRun).where(
            FiveCsRefreshRun.refreshed_five_cs_assessment_id == refreshed["refreshed_assessment_id"]
        )
    )
    assert refresh_row is not None and refresh_row.base_five_cs_assessment_id == base.id
    links = list(
        db_session.scalars(
            select(FiveCsResearchEvidenceLink).where(
                FiveCsResearchEvidenceLink.five_cs_assessment_id
                == refreshed["refreshed_assessment_id"]
            )
        )
    )
    assert links and all(row.research_finding_id for row in links)
    updated_sections = {
        row.section: row
        for row in db_session.scalars(
            select(FiveCsSection).where(
                FiveCsSection.five_cs_assessment_id == refreshed["refreshed_assessment_id"]
            )
        )
    }
    for section in ("CAPACITY", "CAPITAL", "COLLATERAL"):
        assert (
            updated_sections[section].status,
            updated_sections[section].confidence_score,
            updated_sections[section].completeness_score,
        ) == base_sections[section]
    assert {
        row.source_type
        for row in db_session.scalars(
            select(FiveCsEvidence)
            .join(FiveCsSection)
            .where(FiveCsSection.five_cs_assessment_id == refreshed["refreshed_assessment_id"])
        )
    } >= {"RESEARCH_FINDING"}

    prepared = CreditRecommendationService(db_session).prepare(
        document.id,
        five_cs_assessment_id=refreshed["refreshed_assessment_id"],
        research_run_id=research.id,
    )
    repeated_preparation = CreditRecommendationService(db_session).prepare(
        document.id,
        five_cs_assessment_id=refreshed["refreshed_assessment_id"],
        research_run_id=research.id,
    )
    assert prepared["preparation_id"] == repeated_preparation["preparation_id"]
    assert repeated_preparation["idempotent"] is True
    assert prepared["status"] in {
        "CONDITIONAL_REVIEW_REQUIRED",
        "CRITICAL_RISK_REVIEW",
        "INSUFFICIENT_EVIDENCE",
    }
    assert prepared["lineage"] == {
        "credit_assessment_id": credit.id,
        "five_cs_assessment_id": refreshed["refreshed_assessment_id"],
        "research_run_id": research.id,
        "fusion_experiment_id": None,
    }
    assert prepared["final_lending_decision"] is None
    assert prepared["proposed_credit_limit"] is None
    assert prepared["pricing"] is None
    factors = list(
        db_session.scalars(
            select(CreditRecommendationFactor).where(
                CreditRecommendationFactor.recommendation_preparation_id
                == prepared["preparation_id"]
            )
        )
    )
    assert any(row.factor_code == "CRITICAL_RECENT_RATING_DOWNGRADE" for row in factors)
    assert all(row.category != "EXPERIMENTAL_CONTEXT" for row in factors)
    assert db_session.scalar(select(func.count()).select_from(CreditRecommendationPreparation)) >= 1
    preparation_id = prepared["preparation_id"]
    assert get_credit_recommendation(preparation_id, db_session)["status"] == prepared["status"]
    assert (
        list_credit_recommendations(document.id, None, True, db_session)[0]["preparation_id"]
        == preparation_id
    )
    assert get_recommendation_factors(preparation_id, None, None, db_session)
    assert get_recommendation_review_items(preparation_id, db_session)
    evidence_payload = get_recommendation_evidence(preparation_id, db_session)
    assert evidence_payload["external_sources"]
    assert all(item["url"].startswith("https://") for item in evidence_payload["external_sources"])


def test_recommendation_requires_refreshed_five_cs(db_session: Session) -> None:
    document, credit = _context(db_session)
    base = FiveCsAssessmentService(db_session).analyze(document.id, credit.statement_scope)[0]
    with pytest.raises(ValueError, match="REFRESHED_FIVE_CS_REQUIRED"):
        CreditRecommendationService(db_session).prepare(
            document.id, five_cs_assessment_id=base["assessment_id"]
        )
