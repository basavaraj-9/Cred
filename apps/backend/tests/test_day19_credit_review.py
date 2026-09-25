from __future__ import annotations

# ruff: noqa: E501
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.decision import CreditDecisionReviewItem, CreditDecisionSupport, CreditPolicyException
from app.models.review import CreditDecisionOverride, CreditHumanDecision, CreditReviewComment
from app.models.user import User
from app.services.credit_decision.service import CreditDecisionSupportService
from app.services.credit_review.policy import AUTHORITY_POLICY_VERSION, COMMITTEE_SUMMARY_VERSION, authority_policy
from app.services.credit_review.service import CreditReviewService, case_payload, package_payload, timeline
from tests.test_day18_credit_decision import _day17


def _user(session: Session, role: str) -> User:
    user = User(email=f"{uuid4()}@review.test", display_name=role, reviewer_role=role)
    session.add(user); session.flush(); return user


def _context(session: Session) -> tuple[CreditReviewService, CreditDecisionSupport, User, User, User]:
    document, _, recommendation = _day17(session)
    result = CreditDecisionSupportService(session).prepare(document.id, recommendation_preparation_id=recommendation["preparation_id"])
    decision = session.get(CreditDecisionSupport, result["decision_support_id"]); assert decision is not None
    return CreditReviewService(session), decision, _user(session, "ADMIN"), _user(session, "CREDIT_MANAGER"), _user(session, "CREDIT_MANAGER")


def test_authority_policy_loads_and_excludes_protected_attributes() -> None:
    policy = authority_policy()
    assert policy["version"] == AUTHORITY_POLICY_VERSION
    assert policy["protected_attributes"] == []
    assert policy["require_distinct_exception_approver"] is True
    assert "APPROVED" not in policy["roles"]["CREDIT_ANALYST"]["decisions"]


def test_complete_human_review_workflow_authorization_rfi_decision_and_lineage(db_session: Session) -> None:
    service, support, admin, reviewer, checker = _context(db_session)
    original_recommendation = support.system_recommendation
    original_hash = support.input_hash
    case = service.create_case(support.id, admin.id)
    assert service.create_case(support.id, admin.id).id == case.id
    service.assign(case.id, reviewer.id, admin.id, "Work allocation")
    service.start(case.id, reviewer.id)
    comment = service.comment(case.id, reviewer.id, "RISK_NOTE", "Reviewed material risks", source_type="credit_decision_support", source_id=support.id)
    service.acknowledge(case.id, reviewer.id, "credit_decision_support", support.id, "REVIEWED")
    for item in db_session.scalars(select(CreditDecisionReviewItem).where(CreditDecisionReviewItem.credit_decision_support_id == support.id)):
        service.checklist(case.id, item.id, reviewer.id, "RESOLVED", "Reviewed")
    rfi = service.create_rfi(case.id, reviewer.id, "BANKING_EXPOSURE", "Latest exposure statement", "Provide latest banking exposure", True)
    with pytest.raises(AppError, match="blocking information request"):
        service.transition(case.id, "READY_FOR_DECISION", reviewer.id)
    service.update_rfi(case.id, rfi.id, reviewer.id, "RECEIVED", "Received")
    service.update_rfi(case.id, rfi.id, reviewer.id, "CLOSED", "Validated")
    service.transition(case.id, "IN_REVIEW", reviewer.id)
    exceptions = list(db_session.scalars(select(CreditPolicyException).where(CreditPolicyException.credit_decision_support_id == support.id)))
    for exception in exceptions:
        service.exception_action(case.id, exception.id, checker.id, "APPROVE_EXCEPTION", "Accepted for review under development policy")
    service.transition(case.id, "READY_FOR_DECISION", reviewer.id)
    decision = service.decision(case.id, reviewer.id, "APPROVED", "Human review supports approval within authority", Decimal("250.00"), "INR", [{"condition": "Updated financials annually"}])
    assert decision.decision == "APPROVED" and decision.decided_by_user_id == reviewer.id
    assert decision.approved_limit == Decimal("250.00")
    assert support.system_recommendation == original_recommendation and support.input_hash == original_hash
    assert support.human_decision is None
    assert case_payload(db_session, case)["human_decision"] is not None
    assert len(timeline(db_session, case)) >= 8
    persisted = db_session.get(CreditReviewComment, comment.id)
    assert persisted is not None and persisted.comment_text == "Reviewed material risks"


def test_backend_authority_and_self_approval_enforced(db_session: Session) -> None:
    service, support, admin, reviewer, _ = _context(db_session)
    analyst = _user(db_session, "CREDIT_ANALYST")
    case = service.create_case(support.id, admin.id); service.assign(case.id, reviewer.id, admin.id); service.start(case.id, reviewer.id)
    exception = db_session.scalar(select(CreditPolicyException).where(CreditPolicyException.credit_decision_support_id == support.id)); assert exception is not None
    with pytest.raises(AppError) as denied:
        service.exception_action(case.id, exception.id, analyst.id, "APPROVE_EXCEPTION", "Attempt")
    assert denied.value.status_code == 403
    with pytest.raises(AppError, match="Assigned reviewer"):
        service.exception_action(case.id, exception.id, reviewer.id, "APPROVE_EXCEPTION", "Attempt")


def test_human_decision_requires_explicit_actor_rationale_and_preserves_versions(db_session: Session) -> None:
    service, support, admin, reviewer, checker = _context(db_session)
    case = service.create_case(support.id, admin.id); service.assign(case.id, reviewer.id, admin.id); service.start(case.id, reviewer.id)
    for item in db_session.scalars(select(CreditDecisionReviewItem).where(CreditDecisionReviewItem.credit_decision_support_id == support.id)):
        service.checklist(case.id, item.id, reviewer.id, "RESOLVED")
    for exception in db_session.scalars(select(CreditPolicyException).where(CreditPolicyException.credit_decision_support_id == support.id)):
        service.exception_action(case.id, exception.id, checker.id, "APPROVE_EXCEPTION", "Accepted")
    service.transition(case.id, "READY_FOR_DECISION", reviewer.id)
    with pytest.raises(AppError, match="rationale"):
        service.decision(case.id, reviewer.id, "APPROVED", "")
    first = service.decision(case.id, reviewer.id, "APPROVED", "Explicit human decision", Decimal("200"), "INR")
    second = service.decision(case.id, reviewer.id, "DECLINED", "Superseding human decision")
    assert first.is_current is False and first.superseded_decision_id == second.id
    assert second.is_current is True and second.decision_version == 2
    assert len(list(db_session.scalars(select(CreditHumanDecision).where(CreditHumanDecision.review_case_id == case.id)))) == 2


def test_limit_and_system_overrides_require_rationale_and_are_auditable(db_session: Session) -> None:
    service, support, admin, reviewer, checker = _context(db_session)
    case = service.create_case(support.id, admin.id); service.assign(case.id, reviewer.id, admin.id); service.start(case.id, reviewer.id)
    for item in db_session.scalars(select(CreditDecisionReviewItem).where(CreditDecisionReviewItem.credit_decision_support_id == support.id)):
        service.checklist(case.id, item.id, reviewer.id, "RESOLVED")
    for exception in db_session.scalars(select(CreditPolicyException).where(CreditPolicyException.credit_decision_support_id == support.id)):
        service.exception_action(case.id, exception.id, checker.id, "APPROVE_EXCEPTION", "Accepted")
    service.transition(case.id, "READY_FOR_DECISION", reviewer.id)
    with pytest.raises(AppError, match="override rationale"):
        service.decision(case.id, reviewer.id, "APPROVED", "Decision", Decimal("500"), "INR")
    decision = service.decision(case.id, reviewer.id, "APPROVED", "Decision", Decimal("500"), "INR", override_rationale="Manager accepts analytical ceiling variance")
    overrides = list(db_session.scalars(select(CreditDecisionOverride).where(CreditDecisionOverride.human_decision_id == decision.id)))
    assert {x.override_type for x in overrides} == {"LIMIT_OVERRIDE"}


def test_committee_package_version_hash_ready_and_immutable(db_session: Session) -> None:
    service, support, admin, reviewer, _ = _context(db_session)
    case = service.create_case(support.id, admin.id); service.assign(case.id, reviewer.id, admin.id); service.start(case.id, reviewer.id)
    package = service.committee_package(case.id, reviewer.id)
    assert service.committee_package(case.id, reviewer.id).id == package.id
    payload = package_payload(db_session, package)
    assert package.summary_version == COMMITTEE_SUMMARY_VERSION and len(payload["sections"]) >= 10
    service.mark_ready(package.id, reviewer.id)
    with pytest.raises(AppError, match="draft package"):
        service.mark_ready(package.id, reviewer.id)
    service.comment(case.id, reviewer.id, "COMMITTEE_NOTE", "Additional committee note")
    new_package = service.committee_package(case.id, reviewer.id)
    assert new_package.id != package.id and new_package.package_version == 2


def test_no_automatic_human_decision_on_case_or_committee_creation(db_session: Session) -> None:
    service, support, admin, reviewer, _ = _context(db_session)
    case = service.create_case(support.id, admin.id); service.assign(case.id, reviewer.id, admin.id); service.start(case.id, reviewer.id); service.committee_package(case.id, reviewer.id)
    assert db_session.scalar(select(CreditHumanDecision).where(CreditHumanDecision.review_case_id == case.id)) is None
    assert db_session.get(CreditDecisionSupport, support.id).human_decision is None  # type: ignore[union-attr]
