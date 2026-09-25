from __future__ import annotations

# ruff: noqa: E501, E701, E702
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.audit_log import AuditLog
from app.models.decision import (
    CreditDecisionReviewItem,
    CreditDecisionSupport,
    CreditLimitPreparation,
    CreditPolicyException,
)
from app.models.review import (
    CreditCommitteePackage,
    CreditCommitteePackageSection,
    CreditDecisionOverride,
    CreditHumanDecision,
    CreditInformationRequest,
    CreditPolicyExceptionAction,
    CreditReviewAssignment,
    CreditReviewCase,
    CreditReviewChecklistAction,
    CreditReviewComment,
    CreditReviewEvidenceAcknowledgement,
)
from app.models.user import User
from app.services.credit_review.policy import (
    AUTHORITY_POLICY_VERSION,
    COMMITTEE_SUMMARY_VERSION,
    authority_policy,
)

WORKFLOW_TRANSITIONS = {
    "PENDING_REVIEW": {"ASSIGNED", "CANCELLED"},
    "ASSIGNED": {"IN_REVIEW", "CANCELLED"},
    "IN_REVIEW": {
        "AWAITING_INFORMATION",
        "AWAITING_EXCEPTION_APPROVAL",
        "READY_FOR_DECISION",
        "REFERRED_TO_COMMITTEE",
        "CANCELLED",
    },
    "AWAITING_INFORMATION": {"IN_REVIEW", "READY_FOR_DECISION", "CANCELLED"},
    "AWAITING_EXCEPTION_APPROVAL": {"IN_REVIEW", "READY_FOR_DECISION", "REFERRED_TO_COMMITTEE"},
    "READY_FOR_DECISION": {"AWAITING_INFORMATION", "REFERRED_TO_COMMITTEE", "DECIDED"},
    "REFERRED_TO_COMMITTEE": {"READY_FOR_DECISION", "DECIDED"},
    "DECIDED": {"CLOSED"},
}
RFI_TRANSITIONS = {
    "OPEN": {"RECEIVED", "PARTIALLY_RECEIVED", "CANCELLED"},
    "PARTIALLY_RECEIVED": {"RECEIVED", "CLOSED", "CANCELLED"},
    "RECEIVED": {"CLOSED", "PARTIALLY_RECEIVED"},
}


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class CreditReviewService:
    def __init__(self, session: Session):
        self.session = session

    def _user(self, user_id: UUID) -> User:
        user = self.session.get(User, user_id)
        if user is None or not user.is_active:
            raise AppError("REVIEWER_NOT_AUTHORIZED", "Active reviewer not found", 403)
        return user

    def _case(self, case_id: UUID) -> CreditReviewCase:
        row = self.session.get(CreditReviewCase, case_id)
        if row is None:
            raise AppError("CREDIT_REVIEW_CASE_NOT_FOUND", "Credit review case not found", 404)
        return row

    def _role(self, user: User) -> dict[str, Any]:
        role = authority_policy()["roles"].get(user.reviewer_role)
        if role is None:
            raise AppError("REVIEWER_ROLE_NOT_AUTHORIZED", "Reviewer role is not configured", 403)
        return role

    def _require_action(self, user: User, action: str) -> None:
        if action not in self._role(user)["actions"]:
            raise AppError(
                "REVIEW_ACTION_FORBIDDEN", f"{user.reviewer_role} cannot perform {action}", 403
            )

    def _audit(
        self,
        case: CreditReviewCase,
        user: User,
        event: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        write_audit_log(
            self.session,
            entity_type="credit_review_case",
            entity_id=case.id,
            action=event,
            event_type=event,
            company_id=case.company_id,
            analysis_job_id=case.analysis_job_id,
            user_id=user.id,
            metadata_json=metadata,
        )

    def create_case(
        self, decision_id: UUID, actor_id: UUID, priority: str = "NORMAL"
    ) -> CreditReviewCase:
        actor = self._user(actor_id)
        decision = self.session.get(CreditDecisionSupport, decision_id)
        if decision is None:
            raise AppError(
                "CREDIT_DECISION_SUPPORT_NOT_FOUND", "Credit decision support record not found", 404
            )
        value = _hash({"decision_support_id": str(decision.id), "policy": AUTHORITY_POLICY_VERSION})
        existing = self.session.scalar(
            select(CreditReviewCase).where(
                CreditReviewCase.decision_support_id == decision.id,
                CreditReviewCase.input_hash == value,
            )
        )
        if existing:
            return existing
        case = CreditReviewCase(
            decision_support_id=decision.id,
            company_id=decision.company_id,
            document_id=decision.document_id,
            analysis_job_id=decision.analysis_job_id,
            workflow_status="PENDING_REVIEW",
            priority=priority,
            case_version=1,
            input_hash=value,
        )
        self.session.add(case)
        self.session.flush()
        self._audit(case, actor, "CREDIT_REVIEW_CASE_CREATED")
        return case

    def assign(
        self, case_id: UUID, reviewer_id: UUID, actor_id: UUID, rationale: str | None = None
    ) -> CreditReviewCase:
        case = self._case(case_id)
        actor = self._user(actor_id)
        reviewer = self._user(reviewer_id)
        if actor.reviewer_role not in authority_policy()["assignment_roles"]:
            raise AppError("ASSIGNMENT_FORBIDDEN", "Reviewer role cannot assign cases", 403)
        previous = case.primary_reviewer_id
        case.primary_reviewer_id = reviewer.id
        case.assigned_at = _now()
        case.workflow_status = "ASSIGNED"
        self.session.add(
            CreditReviewAssignment(
                review_case_id=case.id,
                reviewer_user_id=reviewer.id,
                assigned_by_user_id=actor.id,
                rationale=rationale,
                created_at=_now(),
            )
        )
        self._audit(
            case,
            actor,
            "CREDIT_REVIEW_ASSIGNED",
            {
                "previous_reviewer_id": str(previous) if previous else None,
                "reviewer_id": str(reviewer.id),
                "rationale": rationale,
            },
        )
        return case

    def start(self, case_id: UUID, actor_id: UUID) -> CreditReviewCase:
        case = self._case(case_id)
        actor = self._user(actor_id)
        self._require_owner(case, actor)
        self._transition(case, "IN_REVIEW")
        case.review_started_at = _now()
        self._audit(case, actor, "CREDIT_REVIEW_STARTED")
        return case

    def transition(self, case_id: UUID, status: str, actor_id: UUID) -> CreditReviewCase:
        case = self._case(case_id)
        actor = self._user(actor_id)
        self._require_owner(case, actor)
        if status == "READY_FOR_DECISION":
            self._ready_checks(case)
        self._transition(case, status)
        if status == "REFERRED_TO_COMMITTEE":
            self._audit(case, actor, "CREDIT_REVIEW_REFERRED_TO_COMMITTEE")
        return case

    def _transition(self, case: CreditReviewCase, status: str) -> None:
        if status not in WORKFLOW_TRANSITIONS.get(case.workflow_status, set()):
            raise AppError(
                "INVALID_WORKFLOW_TRANSITION",
                f"Cannot move from {case.workflow_status} to {status}",
                409,
            )
        case.workflow_status = status

    def _require_owner(self, case: CreditReviewCase, user: User) -> None:
        if case.primary_reviewer_id != user.id and user.reviewer_role not in {
            "CREDIT_MANAGER",
            "ADMIN",
            "CREDIT_COMMITTEE_MEMBER",
        }:
            raise AppError("REVIEW_CASE_OWNERSHIP_REQUIRED", "Reviewer does not own this case", 403)

    def comment(
        self,
        case_id: UUID,
        actor_id: UUID,
        comment_type: str,
        text: str,
        visibility: str = "INTERNAL",
        source_type: str | None = None,
        source_id: UUID | None = None,
    ) -> CreditReviewComment:
        case = self._case(case_id)
        actor = self._user(actor_id)
        self._require_action(actor, "COMMENT")
        if not text.strip():
            raise AppError("COMMENT_REQUIRED", "Comment text is required", 422)
        row = CreditReviewComment(
            review_case_id=case.id,
            author_user_id=actor.id,
            comment_type=comment_type,
            comment_text=text.strip(),
            visibility=visibility,
            source_reference_type=source_type,
            source_reference_id=source_id,
            created_at=_now(),
        )
        self.session.add(row)
        self.session.flush()
        self._audit(case, actor, "CREDIT_REVIEW_COMMENT_ADDED", {"comment_id": str(row.id)})
        return row

    def acknowledge(
        self,
        case_id: UUID,
        actor_id: UUID,
        source_type: str,
        source_id: UUID,
        status: str,
        note: str | None = None,
    ) -> CreditReviewEvidenceAcknowledgement:
        case = self._case(case_id)
        actor = self._user(actor_id)
        self._require_owner(case, actor)
        row = CreditReviewEvidenceAcknowledgement(
            review_case_id=case.id,
            reviewer_user_id=actor.id,
            source_type=source_type,
            source_reference_id=source_id,
            acknowledgement_status=status,
            note=note,
            created_at=_now(),
        )
        self.session.add(row)
        self.session.flush()
        self._audit(
            case,
            actor,
            "CREDIT_EVIDENCE_ACKNOWLEDGED",
            {"acknowledgement_id": str(row.id), "status": status},
        )
        return row

    def checklist(
        self, case_id: UUID, item_id: UUID, actor_id: UUID, action: str, note: str | None = None
    ) -> CreditReviewChecklistAction:
        case = self._case(case_id)
        actor = self._user(actor_id)
        self._require_owner(case, actor)
        item = self.session.get(CreditDecisionReviewItem, item_id)
        if item is None or item.credit_decision_support_id != case.decision_support_id:
            raise AppError("REVIEW_ITEM_NOT_FOUND", "Review item does not belong to this case", 404)
        row = CreditReviewChecklistAction(
            review_case_id=case.id,
            decision_review_item_id=item.id,
            reviewer_user_id=actor.id,
            action=action,
            note=note,
            created_at=_now(),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def create_rfi(
        self,
        case_id: UUID,
        actor_id: UUID,
        code: str,
        title: str,
        description: str,
        blocking: bool = True,
        due_at: datetime | None = None,
    ) -> CreditInformationRequest:
        case = self._case(case_id)
        actor = self._user(actor_id)
        self._require_owner(case, actor)
        row = CreditInformationRequest(
            review_case_id=case.id,
            request_code=code,
            title=title,
            description=description,
            status="OPEN",
            blocking=blocking,
            requested_by=actor.id,
            requested_at=_now(),
            due_at=due_at,
        )
        self.session.add(row)
        self.session.flush()
        case.workflow_status = "AWAITING_INFORMATION"
        self._audit(case, actor, "CREDIT_INFORMATION_REQUEST_CREATED", {"request_id": str(row.id)})
        return row

    def update_rfi(
        self, case_id: UUID, request_id: UUID, actor_id: UUID, status: str, note: str | None = None
    ) -> CreditInformationRequest:
        case = self._case(case_id)
        actor = self._user(actor_id)
        self._require_owner(case, actor)
        row = self.session.get(CreditInformationRequest, request_id)
        if row is None or row.review_case_id != case.id:
            raise AppError("INFORMATION_REQUEST_NOT_FOUND", "Information request not found", 404)
        if status not in RFI_TRANSITIONS.get(row.status, set()):
            raise AppError(
                "INVALID_RFI_TRANSITION", f"Cannot move RFI from {row.status} to {status}", 409
            )
        row.status = status
        row.resolution_note = note
        if status in {"CLOSED", "CANCELLED"}:
            row.resolved_at = _now()
        self._audit(
            case,
            actor,
            "CREDIT_INFORMATION_REQUEST_UPDATED",
            {"request_id": str(row.id), "status": status},
        )
        return row

    def exception_action(
        self, case_id: UUID, exception_id: UUID, actor_id: UUID, action: str, rationale: str
    ) -> CreditPolicyExceptionAction:
        case = self._case(case_id)
        actor = self._user(actor_id)
        exc = self.session.get(CreditPolicyException, exception_id)
        if exc is None or exc.credit_decision_support_id != case.decision_support_id:
            raise AppError("POLICY_EXCEPTION_NOT_FOUND", "Policy exception not found", 404)
        if action not in self._role(actor)["exception_actions"]:
            raise AppError("EXCEPTION_ACTION_FORBIDDEN", "Reviewer lacks exception authority", 403)
        if not rationale.strip():
            raise AppError("EXCEPTION_RATIONALE_REQUIRED", "Exception rationale is required", 422)
        if (
            authority_policy()["require_distinct_exception_approver"]
            and action in {"APPROVE_EXCEPTION", "REJECT_EXCEPTION"}
            and case.primary_reviewer_id == actor.id
        ):
            raise AppError(
                "SELF_REVIEW_RESTRICTED",
                "Assigned reviewer cannot approve or reject this exception",
                403,
            )
        statuses = {
            "APPROVE_EXCEPTION": ("APPROVED_BY_HUMAN", True),
            "REJECT_EXCEPTION": ("REJECTED_BY_HUMAN", True),
            "REQUEST_INFORMATION": ("MORE_INFORMATION_REQUIRED", False),
            "REFER_HIGHER": ("REFERRED_TO_HIGHER_AUTHORITY", False),
        }
        exc.status, exc.resolved = statuses[action]
        row = CreditPolicyExceptionAction(
            policy_exception_id=exc.id,
            review_case_id=case.id,
            actor_user_id=actor.id,
            action=action,
            rationale=rationale.strip(),
            authority_role=actor.reviewer_role,
            created_at=_now(),
        )
        self.session.add(row)
        self.session.flush()
        self._audit(
            case,
            actor,
            "CREDIT_EXCEPTION_ACTION_RECORDED",
            {"exception_id": str(exc.id), "action": action},
        )
        return row

    def _ready_checks(self, case: CreditReviewCase) -> None:
        open_rfi = self.session.scalar(
            select(CreditInformationRequest.id).where(
                CreditInformationRequest.review_case_id == case.id,
                CreditInformationRequest.blocking.is_(True),
                CreditInformationRequest.status.in_(authority_policy()["blocking_rfi_statuses"]),
            )
        )
        if open_rfi:
            raise AppError(
                "BLOCKING_INFORMATION_REQUEST_OPEN",
                "A blocking information request remains open",
                409,
            )
        items = list(
            self.session.scalars(
                select(CreditDecisionReviewItem).where(
                    CreditDecisionReviewItem.credit_decision_support_id == case.decision_support_id,
                    CreditDecisionReviewItem.blocking.is_(True),
                )
            )
        )
        for item in items:
            latest = self.session.scalar(
                select(CreditReviewChecklistAction)
                .where(
                    CreditReviewChecklistAction.review_case_id == case.id,
                    CreditReviewChecklistAction.decision_review_item_id == item.id,
                )
                .order_by(desc(CreditReviewChecklistAction.created_at))
                .limit(1)
            )
            if latest is None or latest.action not in {"RESOLVED", "NOT_APPLICABLE"}:
                raise AppError(
                    "BLOCKING_REVIEW_ITEM_OPEN", "A blocking review item remains unresolved", 409
                )

    def decision(
        self,
        case_id: UUID,
        actor_id: UUID,
        decision: str,
        rationale: str,
        approved_limit: Decimal | None = None,
        currency: str | None = None,
        conditions: list[dict[str, object]] | None = None,
        override_rationale: str | None = None,
    ) -> CreditHumanDecision:
        case = self._case(case_id)
        actor = self._user(actor_id)
        role = self._role(actor)
        self._require_owner(case, actor)
        if decision not in role["decisions"]:
            raise AppError("DECISION_FORBIDDEN", "Reviewer lacks decision authority", 403)
        if not rationale.strip():
            raise AppError("DECISION_RATIONALE_REQUIRED", "Decision rationale is required", 422)
        if decision in {"APPROVED", "DECLINED"}:
            self._ready_checks(case)
        unresolved = self.session.scalar(
            select(CreditPolicyException.id).where(
                CreditPolicyException.credit_decision_support_id == case.decision_support_id,
                CreditPolicyException.resolved.is_(False),
            )
        )
        if decision == "APPROVED" and unresolved:
            raise AppError(
                "UNRESOLVED_POLICY_EXCEPTION",
                "Approval requires all blocking exceptions to be resolved",
                409,
            )
        limit = self.session.scalar(
            select(CreditLimitPreparation).where(
                CreditLimitPreparation.credit_decision_support_id == case.decision_support_id
            )
        )
        maximum = role["approved_limit_max"]
        if approved_limit is not None and (currency is None or approved_limit < 0):
            raise AppError(
                "INVALID_APPROVED_LIMIT",
                "Approved limit requires currency and a non-negative value",
                422,
            )
        if maximum is not None and approved_limit is not None and approved_limit > Decimal(maximum):
            raise AppError(
                "LIMIT_AUTHORITY_EXCEEDED", "Approved limit exceeds reviewer authority", 403
            )
        limit_override = bool(
            approved_limit is not None
            and limit
            and limit.analytical_ceiling is not None
            and approved_limit > limit.analytical_ceiling
        )
        if limit_override and not override_rationale:
            raise AppError(
                "LIMIT_OVERRIDE_RATIONALE_REQUIRED", "Limit override rationale is required", 422
            )
        support = self.session.get(CreditDecisionSupport, case.decision_support_id)
        assert support is not None
        system_override = (
            support.system_recommendation == "ADVERSE_REVIEW" and decision == "APPROVED"
        ) or (support.system_recommendation == "FAVORABLE_REVIEW" and decision == "DECLINED")
        if system_override and not override_rationale:
            raise AppError(
                "SYSTEM_OVERRIDE_RATIONALE_REQUIRED",
                "System recommendation override rationale is required",
                422,
            )
        current = self.session.scalar(
            select(CreditHumanDecision).where(
                CreditHumanDecision.review_case_id == case.id,
                CreditHumanDecision.is_current.is_(True),
            )
        )
        version = 1 if current is None else current.decision_version + 1
        if current:
            current.is_current = False
            self.session.flush()
        row = CreditHumanDecision(
            review_case_id=case.id,
            decision_support_id=case.decision_support_id,
            decided_by_user_id=actor.id,
            decision=decision,
            decision_rationale=rationale.strip(),
            decision_authority_role=actor.reviewer_role,
            approved_limit=approved_limit,
            currency=currency,
            conditions_json=conditions,
            override_rationale=override_rationale,
            decision_timestamp=_now(),
            policy_version=AUTHORITY_POLICY_VERSION,
            decision_version=version,
            is_current=True,
            created_at=_now(),
        )
        self.session.add(row)
        self.session.flush()
        if current:
            current.superseded_decision_id = row.id
            self._audit(
                case,
                actor,
                "CREDIT_DECISION_SUPERSEDED",
                {"prior_decision_id": str(current.id), "decision_id": str(row.id)},
            )
        if limit_override:
            assert limit is not None
            self.session.add(
                CreditDecisionOverride(
                    human_decision_id=row.id,
                    override_type="LIMIT_OVERRIDE",
                    system_value=str(limit.analytical_ceiling),
                    human_value=str(approved_limit),
                    rationale=override_rationale or "",
                    created_at=_now(),
                )
            )
        if system_override:
            self.session.add(
                CreditDecisionOverride(
                    human_decision_id=row.id,
                    override_type="SYSTEM_RECOMMENDATION_OVERRIDE",
                    system_value=support.system_recommendation,
                    human_value=decision,
                    rationale=override_rationale or "",
                    created_at=_now(),
                )
            )
        case.decision_recorded_at = _now()
        case.workflow_status = (
            "AWAITING_INFORMATION"
            if decision == "RETURNED_FOR_INFORMATION"
            else "REFERRED_TO_COMMITTEE"
            if decision == "REFERRED_TO_COMMITTEE"
            else "DECIDED"
        )
        self._audit(
            case,
            actor,
            "CREDIT_HUMAN_DECISION_RECORDED",
            {"decision_id": str(row.id), "decision": decision},
        )
        return row

    def committee_package(self, case_id: UUID, actor_id: UUID) -> CreditCommitteePackage:
        case = self._case(case_id)
        actor = self._user(actor_id)
        self._require_action(actor, "PREPARE_COMMITTEE")
        exceptions = list(
            self.session.scalars(
                select(CreditPolicyException).where(
                    CreditPolicyException.credit_decision_support_id == case.decision_support_id
                )
            )
        )
        rfis = list(
            self.session.scalars(
                select(CreditInformationRequest).where(
                    CreditInformationRequest.review_case_id == case.id
                )
            )
        )
        comments = list(
            self.session.scalars(
                select(CreditReviewComment).where(CreditReviewComment.review_case_id == case.id)
            )
        )
        decisions = list(
            self.session.scalars(
                select(CreditHumanDecision).where(CreditHumanDecision.review_case_id == case.id)
            )
        )
        value = _hash(
            {
                "case": str(case.id),
                "case_updated": case.updated_at,
                "decision": str(case.decision_support_id),
                "exceptions": [(str(x.id), x.status) for x in exceptions],
                "rfis": [(str(x.id), x.status) for x in rfis],
                "comments": [str(x.id) for x in comments],
                "decisions": [str(x.id) for x in decisions],
            }
        )
        existing = self.session.scalar(
            select(CreditCommitteePackage).where(
                CreditCommitteePackage.review_case_id == case.id,
                CreditCommitteePackage.input_hash == value,
            )
        )
        if existing:
            return existing
        version = (
            self.session.scalar(
                select(CreditCommitteePackage.package_version)
                .where(CreditCommitteePackage.review_case_id == case.id)
                .order_by(desc(CreditCommitteePackage.package_version))
                .limit(1)
            )
            or 0
        ) + 1
        support = self.session.get(CreditDecisionSupport, case.decision_support_id)
        assert support is not None
        summary = f"Case prepared for committee with system recommendation {support.system_recommendation}, {sum(not x.resolved for x in exceptions)} open policy exceptions, and {sum(x.status not in {'CLOSED', 'CANCELLED'} for x in rfis)} open information requests. Human committee review remains required."
        package = CreditCommitteePackage(
            review_case_id=case.id,
            decision_support_id=case.decision_support_id,
            package_version=version,
            status="DRAFT",
            prepared_by_user_id=actor.id,
            prepared_at=_now(),
            input_hash=value,
            summary_version=COMMITTEE_SUMMARY_VERSION,
            summary_text=summary,
            created_at=_now(),
        )
        self.session.add(package)
        self.session.flush()
        sections = {
            "EXECUTIVE_SUMMARY": {"summary": summary},
            "CREDIT_RISK": {
                "credit_assessment_id": str(support.credit_assessment_id),
                "system_recommendation": support.system_recommendation,
            },
            "FIVE_CS": {"five_cs_assessment_id": str(support.five_cs_assessment_id)},
            "EXTERNAL_RESEARCH": {
                "research_run_id": str(support.research_run_id) if support.research_run_id else None
            },
            "POLICY_GATES": {"decision_support_id": str(support.id)},
            "POLICY_EXCEPTIONS": {
                "items": [
                    {"id": str(x.id), "code": x.exception_code, "status": x.status}
                    for x in exceptions
                ]
            },
            "LIMIT_PREPARATION": {"decision_support_id": str(support.id)},
            "REVIEWER_NOTES": {"comment_ids": [str(x.id) for x in comments]},
            "OPEN_ITEMS": {
                "information_requests": [{"id": str(x.id), "status": x.status} for x in rfis]
            },
            "DECISION_HISTORY": {"decision_ids": [str(x.id) for x in decisions]},
        }
        for code, payload in sections.items():
            self.session.add(
                CreditCommitteePackageSection(
                    package_id=package.id,
                    section_code=code,
                    title=code.replace("_", " ").title(),
                    structured_payload_json=payload,
                    source_count=1,
                    created_at=_now(),
                )
            )
        self._audit(
            case,
            actor,
            "CREDIT_COMMITTEE_PACKAGE_CREATED",
            {"package_id": str(package.id), "version": version},
        )
        return package

    def mark_ready(self, package_id: UUID, actor_id: UUID) -> CreditCommitteePackage:
        package = self.session.get(CreditCommitteePackage, package_id)
        if package is None:
            raise AppError("COMMITTEE_PACKAGE_NOT_FOUND", "Committee package not found", 404)
        case = self._case(package.review_case_id)
        actor = self._user(actor_id)
        self._require_action(actor, "MARK_COMMITTEE_READY")
        if package.status != "DRAFT":
            raise AppError(
                "COMMITTEE_PACKAGE_IMMUTABLE", "Only a draft package can be marked ready", 409
            )
        package.status = "READY"
        package.ready_at = _now()
        self._audit(case, actor, "CREDIT_COMMITTEE_PACKAGE_READY", {"package_id": str(package.id)})
        return package


def case_payload(session: Session, case: CreditReviewCase) -> dict[str, object]:
    basis = session.get(CreditDecisionSupport, case.decision_support_id)
    assert basis is not None
    newer = session.scalar(
        select(CreditDecisionSupport.id)
        .where(
            CreditDecisionSupport.document_id == case.document_id,
            CreditDecisionSupport.created_at > basis.created_at,
        )
        .limit(1)
    )
    current = session.scalar(
        select(CreditHumanDecision).where(
            CreditHumanDecision.review_case_id == case.id, CreditHumanDecision.is_current.is_(True)
        )
    )
    return {
        "id": case.id,
        "decision_support_id": case.decision_support_id,
        "company_id": case.company_id,
        "document_id": case.document_id,
        "workflow_status": "UPDATED_ANALYSIS_AVAILABLE"
        if newer and case.workflow_status not in {"DECIDED", "CLOSED", "CANCELLED"}
        else case.workflow_status,
        "stored_workflow_status": case.workflow_status,
        "primary_reviewer_id": case.primary_reviewer_id,
        "priority": case.priority,
        "sla_due_at": case.sla_due_at,
        "case_version": case.case_version,
        "human_decision": decision_payload(current) if current else None,
        "updated_analysis_available": bool(newer),
        "created_at": case.created_at,
        "updated_at": case.updated_at,
    }


def decision_payload(row: CreditHumanDecision) -> dict[str, object]:
    return {
        "id": row.id,
        "decision": row.decision,
        "rationale": row.decision_rationale,
        "decided_by_user_id": row.decided_by_user_id,
        "authority_role": row.decision_authority_role,
        "approved_limit": row.approved_limit,
        "currency": row.currency,
        "conditions": row.conditions_json,
        "decision_version": row.decision_version,
        "is_current": row.is_current,
        "superseded_decision_id": row.superseded_decision_id,
        "decision_timestamp": row.decision_timestamp,
    }


def package_payload(session: Session, row: CreditCommitteePackage) -> dict[str, object]:
    sections = list(
        session.scalars(
            select(CreditCommitteePackageSection)
            .where(CreditCommitteePackageSection.package_id == row.id)
            .order_by(CreditCommitteePackageSection.section_code)
        )
    )
    return {
        "id": row.id,
        "review_case_id": row.review_case_id,
        "decision_support_id": row.decision_support_id,
        "package_version": row.package_version,
        "status": row.status,
        "summary": row.summary_text,
        "summary_version": row.summary_version,
        "prepared_by_user_id": row.prepared_by_user_id,
        "prepared_at": row.prepared_at,
        "ready_at": row.ready_at,
        "sections": [
            {
                "id": x.id,
                "section_code": x.section_code,
                "title": x.title,
                "payload": x.structured_payload_json,
                "source_count": x.source_count,
            }
            for x in sections
        ],
    }


def timeline(session: Session, case: CreditReviewCase) -> list[dict[str, object]]:
    rows: list[tuple[datetime, str, UUID, UUID | None, dict[str, object]]] = []
    for x in session.scalars(
        select(AuditLog).where(
            AuditLog.entity_type == "credit_review_case", AuditLog.entity_id == case.id
        )
    ):
        rows.append((x.created_at, x.event_type, x.id, x.user_id, x.metadata_json or {}))
    return [
        {
            "timestamp": x[0],
            "event_type": x[1],
            "record_id": x[2],
            "actor_user_id": x[3],
            "details": x[4],
        }
        for x in sorted(rows, key=lambda x: x[0])
    ]
