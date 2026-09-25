from __future__ import annotations

# ruff: noqa: E501
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.credit_decision import (
    get_credit_decision,
    get_decision_evidence,
    get_decision_gates,
    get_decision_review_items,
    get_limit_preparation,
    get_policy_exceptions,
    list_credit_decisions,
)
from app.models.credit import CreditAssessment
from app.models.decision import CreditDecisionSupport, CreditLimitMethod
from app.models.enums import FinancialScope
from app.models.five_cs import FiveCsAssessment
from app.models.recommendation import CreditRecommendationPreparation
from app.models.research import ResearchRun
from app.services.credit_decision.policy import (
    ENGINE_VERSION,
    LIMIT_POLICY_VERSION,
    POLICY_VERSION,
    decision_policy,
    limit_policy,
    system_recommendation,
)
from app.services.credit_decision.service import CreditDecisionSupportService
from app.services.credit_recommendation.service import CreditRecommendationService
from app.services.external_research.service import ExternalResearchService
from app.services.five_cs.refresh import FiveCsResearchRefreshService
from app.services.five_cs.service import FiveCsAssessmentService
from tests.test_five_cs import _context


def test_credit_decision_policy_loads() -> None:
    assert decision_policy()["version"] == POLICY_VERSION
    assert decision_policy()["engine_version"] == ENGINE_VERSION
    assert decision_policy()["human_review_required"] is True
    assert decision_policy()["protected_attributes"] == []


def test_limit_policy_loads() -> None:
    assert limit_policy()["version"] == LIMIT_POLICY_VERSION
    assert limit_policy()["aggregation"] == "MINIMUM_ELIGIBLE_CAP"
    assert limit_policy()["synthetic_ml_weight"] == 0.0


def test_valid_recommendation_states_and_no_automation() -> None:
    states = set(decision_policy()["recommendation_states"])  # type: ignore[arg-type]
    assert states == {
        "FAVORABLE_REVIEW",
        "CONDITIONAL_REVIEW",
        "MANUAL_REVIEW_REQUIRED",
        "ADVERSE_REVIEW",
        "INSUFFICIENT_EVIDENCE",
        "POLICY_EXCEPTION_REVIEW",
    }
    assert states.isdisjoint({"AUTO_APPROVE", "AUTO_REJECT", "APPROVED", "DECLINED", "SANCTIONED"})


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {
                "insufficient": True,
                "exceptions": 1,
                "adverse": True,
                "manual": True,
                "conditional": True,
            },
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            {
                "insufficient": False,
                "exceptions": 1,
                "adverse": True,
                "manual": True,
                "conditional": True,
            },
            "POLICY_EXCEPTION_REVIEW",
        ),
        (
            {
                "insufficient": False,
                "exceptions": 0,
                "adverse": True,
                "manual": True,
                "conditional": True,
            },
            "ADVERSE_REVIEW",
        ),
        (
            {
                "insufficient": False,
                "exceptions": 0,
                "adverse": False,
                "manual": True,
                "conditional": True,
            },
            "MANUAL_REVIEW_REQUIRED",
        ),
        (
            {
                "insufficient": False,
                "exceptions": 0,
                "adverse": False,
                "manual": False,
                "conditional": True,
            },
            "CONDITIONAL_REVIEW",
        ),
        (
            {
                "insufficient": False,
                "exceptions": 0,
                "adverse": False,
                "manual": False,
                "conditional": False,
            },
            "FAVORABLE_REVIEW",
        ),
    ],
)
def test_gate_precedence(kwargs: dict[str, object], expected: str) -> None:
    assert system_recommendation(**kwargs) == expected  # type: ignore[arg-type]


def _day17(session: Session) -> tuple[object, CreditAssessment, dict[str, object]]:
    document, credit = _context(session)
    base = FiveCsAssessmentService(session).analyze(document.id, FinancialScope.CONSOLIDATED)[0]
    research = ExternalResearchService(session).research_company(
        document.company_id, ["LEGAL", "RATINGS"], False
    )
    refreshed = FiveCsResearchRefreshService(session).refresh(base["assessment_id"], research.id)
    recommendation = CreditRecommendationService(session).prepare(
        document.id,
        five_cs_assessment_id=refreshed["refreshed_assessment_id"],
        research_run_id=research.id,
    )
    return document, credit, recommendation


def test_complete_decision_support_gates_exceptions_limit_lineage_and_immutability(
    db_session: Session,
) -> None:
    document, credit, recommendation = _day17(db_session)
    original_credit_hash = credit.input_hash
    source_recommendation = db_session.get(
        CreditRecommendationPreparation, recommendation["preparation_id"]
    )
    assert source_recommendation is not None
    source_five_cs = db_session.get(FiveCsAssessment, source_recommendation.five_cs_assessment_id)
    source_research = db_session.get(ResearchRun, source_recommendation.research_run_id)
    hashes = (
        source_recommendation.input_hash,
        source_five_cs.input_hash,
        source_research.input_hash,
    )  # type: ignore[union-attr]

    result = CreditDecisionSupportService(db_session).prepare(
        document.id, recommendation_preparation_id=recommendation["preparation_id"]
    )
    repeated = CreditDecisionSupportService(db_session).prepare(
        document.id, recommendation_preparation_id=recommendation["preparation_id"]
    )
    assert result["decision_support_id"] == repeated["decision_support_id"]
    assert repeated["idempotent"] is True
    assert result["system_recommendation"] == "POLICY_EXCEPTION_REVIEW"
    assert result["human_decision"] is None and result["human_decision_status"] == "NOT_RECORDED"
    assert result["production_ml_used"] is False and result["experimental_ml_decision_weight"] == 0
    assert (
        result["final_lending_decision"] is None
        and result["sanctioned_limit"] is None
        and result["pricing"] is None
    )
    assert result["gates"] and {g["category"] for g in result["gates"]} >= {
        "FINANCIAL",
        "REPAYMENT_CAPACITY",
        "CAPITAL",
        "COLLATERAL",
        "CHARACTER_RESEARCH",
        "CONDITIONS",
        "LEGAL_REGULATORY",
        "DATA_QUALITY",
        "RESEARCH_COVERAGE",
    }
    assert result["exceptions"] and all(
        e["status"] == "OPEN" and e["resolved"] is False for e in result["exceptions"]
    )
    assert {e["exception_code"] for e in result["exceptions"]} >= {
        "COLLATERAL_COVERAGE_EXCEPTION",
        "RATING_DOWNGRADE_EXCEPTION",
        "LEGAL_RISK_EXCEPTION",
    }
    limit = result["limit_preparation"]
    assert limit["status"] == "PARTIAL" and limit["currency"] == "INR"
    assert limit["analytical_ceiling"] == Decimal("300.00")
    assert limit["lower_bound"] == Decimal("240.00")
    assert limit["existing_exposure_status"] == "EXISTING_EXPOSURE_INCOMPLETE"
    methods = {m["method_code"]: m for m in limit["methods"]}
    assert methods["CASH_FLOW_CAPACITY"]["calculated_limit"] == Decimal("300.00")
    assert methods["REVENUE_CAP"]["status"] == "UNAVAILABLE"
    assert methods["LEVERAGE_CAP"]["status"] == "UNAVAILABLE"
    assert methods["WORKING_CAPITAL_NEED"]["status"] == "UNAVAILABLE"
    assert methods["COLLATERAL_CAP"]["status"] == "UNAVAILABLE"
    assert limit["projected_ratios"]["projected_interest_coverage"] is None
    assert limit["projected_ratios"]["interest_rate_assumed"] is False

    row_id = result["decision_support_id"]
    assert get_credit_decision(row_id, db_session)["human_decision"] is None
    assert (
        list_credit_decisions(document.id, None, None, True, db_session)[0]["decision_support_id"]
        == row_id
    )
    assert get_decision_gates(row_id, db_session)
    assert get_policy_exceptions(row_id, db_session)
    assert get_decision_review_items(row_id, db_session)
    assert get_limit_preparation(row_id, db_session)["sanctioned"] is False
    evidence = get_decision_evidence(row_id, db_session)
    assert evidence["recommendation_preparation"]["id"] == recommendation["preparation_id"]
    assert evidence["experimental_ml_decision_weight"] == 0
    assert db_session.get(CreditAssessment, credit.id).input_hash == original_credit_hash  # type: ignore[union-attr]
    assert (
        source_recommendation.input_hash,
        source_five_cs.input_hash,
        source_research.input_hash,
    ) == hashes  # type: ignore[union-attr]


def test_limit_decimal_precision_and_method_rows(db_session: Session) -> None:
    document, _, recommendation = _day17(db_session)
    result = CreditDecisionSupportService(db_session).prepare(
        document.id, recommendation_preparation_id=recommendation["preparation_id"]
    )
    rows = list(
        db_session.scalars(
            select(CreditLimitMethod).where(
                CreditLimitMethod.credit_decision_support_id == result["decision_support_id"]
            )
        )
    )
    assert len(rows) == 5
    cash = next(row for row in rows if row.method_code == "CASH_FLOW_CAPACITY")
    assert cash.calculated_limit == Decimal("300.00")


def test_human_decision_is_nullable_and_unset_in_model(db_session: Session) -> None:
    document, _, recommendation = _day17(db_session)
    result = CreditDecisionSupportService(db_session).prepare(
        document.id, recommendation_preparation_id=recommendation["preparation_id"]
    )
    row = db_session.get(CreditDecisionSupport, result["decision_support_id"])
    assert row is not None and row.human_decision is None
