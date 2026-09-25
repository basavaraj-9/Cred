from __future__ import annotations

# ruff: noqa: E501, E701, E702
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.review import (
    CreditCommitteePackage,
    CreditHumanDecision,
    CreditInformationRequest,
    CreditReviewCase,
    CreditReviewComment,
    CreditReviewEvidenceAcknowledgement,
)
from app.services.credit_review.service import (
    CreditReviewService,
    case_payload,
    decision_payload,
    package_payload,
    timeline,
)

router = APIRouter(tags=["human credit review"])


class ActorRequest(BaseModel):
    actor_user_id: UUID


class CreateCaseRequest(ActorRequest):
    priority: str = "NORMAL"


class AssignRequest(ActorRequest):
    reviewer_user_id: UUID
    rationale: str | None = None


class TransitionRequest(ActorRequest):
    workflow_status: str


class CommentRequest(ActorRequest):
    comment_type: str = "GENERAL"
    comment_text: str = Field(min_length=1)
    visibility: str = "INTERNAL"
    source_reference_type: str | None = None
    source_reference_id: UUID | None = None


class AckRequest(ActorRequest):
    source_type: str
    source_reference_id: UUID
    acknowledgement_status: str
    note: str | None = None


class ChecklistRequest(ActorRequest):
    action: str
    note: str | None = None


class RFIRequest(ActorRequest):
    request_code: str
    title: str
    description: str
    blocking: bool = True
    due_at: datetime | None = None


class RFIActionRequest(ActorRequest):
    status: str
    resolution_note: str | None = None


class ExceptionActionRequest(ActorRequest):
    action: str
    rationale: str = Field(min_length=1)


class DecisionRequest(ActorRequest):
    decision: str
    decision_rationale: str = Field(min_length=1)
    approved_limit: Decimal | None = None
    currency: str | None = None
    conditions: list[dict[str, object]] | None = None
    override_rationale: str | None = None


def _case(session: Session, case_id: UUID) -> CreditReviewCase:
    row = session.get(CreditReviewCase, case_id)
    if row is None:
        raise AppError("CREDIT_REVIEW_CASE_NOT_FOUND", "Credit review case not found", 404)
    return row


@router.post("/credit-decisions/{decision_support_id}/review-case")
def create_review_case(
    decision_support_id: UUID, body: CreateCaseRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        row = CreditReviewService(session).create_case(
            decision_support_id, body.actor_user_id, body.priority
        )
    return case_payload(session, row)


@router.post("/credit-review-cases/{review_case_id}/assign")
def assign_review_case(
    review_case_id: UUID, body: AssignRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        row = CreditReviewService(session).assign(
            review_case_id, body.reviewer_user_id, body.actor_user_id, body.rationale
        )
    return case_payload(session, row)


@router.post("/credit-review-cases/{review_case_id}/start")
def start_review(
    review_case_id: UUID, body: ActorRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        row = CreditReviewService(session).start(review_case_id, body.actor_user_id)
    return case_payload(session, row)


@router.post("/credit-review-cases/{review_case_id}/transition")
def transition_review(
    review_case_id: UUID, body: TransitionRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        row = CreditReviewService(session).transition(
            review_case_id, body.workflow_status, body.actor_user_id
        )
    return case_payload(session, row)


@router.get("/credit-review-cases/{review_case_id}")
def get_review_case(review_case_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    return case_payload(session, _case(session, review_case_id))


@router.get("/credit-review-cases")
def list_review_cases(
    workflow_status: str | None = None,
    reviewer: UUID | None = None,
    company: UUID | None = None,
    priority: str | None = None,
    updated_since: datetime | None = None,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    query = select(CreditReviewCase)
    if workflow_status:
        query = query.where(CreditReviewCase.workflow_status == workflow_status)
    if reviewer:
        query = query.where(CreditReviewCase.primary_reviewer_id == reviewer)
    if company:
        query = query.where(CreditReviewCase.company_id == company)
    if priority:
        query = query.where(CreditReviewCase.priority == priority)
    if updated_since:
        query = query.where(CreditReviewCase.updated_at >= updated_since)
    return [
        case_payload(session, x)
        for x in session.scalars(query.order_by(CreditReviewCase.updated_at.desc()).limit(200))
    ]


@router.post("/credit-review-cases/{review_case_id}/comments")
def add_comment(
    review_case_id: UUID, body: CommentRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        row = CreditReviewService(session).comment(
            review_case_id,
            body.actor_user_id,
            body.comment_type,
            body.comment_text,
            body.visibility,
            body.source_reference_type,
            body.source_reference_id,
        )
    return {
        "id": row.id,
        "author_user_id": row.author_user_id,
        "comment_type": row.comment_type,
        "comment_text": row.comment_text,
        "visibility": row.visibility,
        "source_reference_type": row.source_reference_type,
        "source_reference_id": row.source_reference_id,
        "created_at": row.created_at,
    }


@router.get("/credit-review-cases/{review_case_id}/comments")
def get_comments(
    review_case_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _case(session, review_case_id)
    return [
        {
            "id": x.id,
            "author_user_id": x.author_user_id,
            "comment_type": x.comment_type,
            "comment_text": x.comment_text,
            "visibility": x.visibility,
            "source_reference_type": x.source_reference_type,
            "source_reference_id": x.source_reference_id,
            "created_at": x.created_at,
        }
        for x in session.scalars(
            select(CreditReviewComment)
            .where(CreditReviewComment.review_case_id == review_case_id)
            .order_by(CreditReviewComment.created_at)
        )
    ]


@router.post("/credit-review-cases/{review_case_id}/evidence-acknowledgements")
def acknowledge_evidence(
    review_case_id: UUID, body: AckRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        x = CreditReviewService(session).acknowledge(
            review_case_id,
            body.actor_user_id,
            body.source_type,
            body.source_reference_id,
            body.acknowledgement_status,
            body.note,
        )
    return {
        "id": x.id,
        "reviewer_user_id": x.reviewer_user_id,
        "source_type": x.source_type,
        "source_reference_id": x.source_reference_id,
        "status": x.acknowledgement_status,
        "note": x.note,
        "created_at": x.created_at,
    }


@router.get("/credit-review-cases/{review_case_id}/evidence-acknowledgements")
def get_acknowledgements(
    review_case_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _case(session, review_case_id)
    return [
        {
            "id": x.id,
            "reviewer_user_id": x.reviewer_user_id,
            "source_type": x.source_type,
            "source_reference_id": x.source_reference_id,
            "status": x.acknowledgement_status,
            "note": x.note,
            "created_at": x.created_at,
        }
        for x in session.scalars(
            select(CreditReviewEvidenceAcknowledgement)
            .where(CreditReviewEvidenceAcknowledgement.review_case_id == review_case_id)
            .order_by(CreditReviewEvidenceAcknowledgement.created_at)
        )
    ]


@router.post("/credit-review-cases/{review_case_id}/review-items/{review_item_id}/action")
def checklist_action(
    review_case_id: UUID,
    review_item_id: UUID,
    body: ChecklistRequest,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    with session.begin():
        x = CreditReviewService(session).checklist(
            review_case_id, review_item_id, body.actor_user_id, body.action, body.note
        )
    return {
        "id": x.id,
        "review_item_id": x.decision_review_item_id,
        "action": x.action,
        "note": x.note,
        "reviewer_user_id": x.reviewer_user_id,
        "created_at": x.created_at,
    }


@router.post("/credit-review-cases/{review_case_id}/information-requests")
def create_information_request(
    review_case_id: UUID, body: RFIRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        x = CreditReviewService(session).create_rfi(
            review_case_id,
            body.actor_user_id,
            body.request_code,
            body.title,
            body.description,
            body.blocking,
            body.due_at,
        )
    return _rfi(x)


@router.get("/credit-review-cases/{review_case_id}/information-requests")
def get_information_requests(
    review_case_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _case(session, review_case_id)
    return [
        _rfi(x)
        for x in session.scalars(
            select(CreditInformationRequest)
            .where(CreditInformationRequest.review_case_id == review_case_id)
            .order_by(CreditInformationRequest.created_at)
        )
    ]


@router.post("/credit-review-cases/{review_case_id}/information-requests/{request_id}/action")
def update_information_request(
    review_case_id: UUID,
    request_id: UUID,
    body: RFIActionRequest,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    with session.begin():
        x = CreditReviewService(session).update_rfi(
            review_case_id, request_id, body.actor_user_id, body.status, body.resolution_note
        )
    return _rfi(x)


def _rfi(x: CreditInformationRequest) -> dict[str, object]:
    return {
        "id": x.id,
        "request_code": x.request_code,
        "title": x.title,
        "description": x.description,
        "status": x.status,
        "blocking": x.blocking,
        "requested_by": x.requested_by,
        "requested_at": x.requested_at,
        "due_at": x.due_at,
        "resolved_at": x.resolved_at,
        "resolution_note": x.resolution_note,
    }


@router.post("/credit-review-cases/{review_case_id}/exceptions/{exception_id}/action")
def exception_action(
    review_case_id: UUID,
    exception_id: UUID,
    body: ExceptionActionRequest,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    with session.begin():
        x = CreditReviewService(session).exception_action(
            review_case_id, exception_id, body.actor_user_id, body.action, body.rationale
        )
    return {
        "id": x.id,
        "policy_exception_id": x.policy_exception_id,
        "action": x.action,
        "rationale": x.rationale,
        "actor_user_id": x.actor_user_id,
        "authority_role": x.authority_role,
        "created_at": x.created_at,
    }


@router.post("/credit-review-cases/{review_case_id}/decision")
def record_decision(
    review_case_id: UUID, body: DecisionRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        x = CreditReviewService(session).decision(
            review_case_id,
            body.actor_user_id,
            body.decision,
            body.decision_rationale,
            body.approved_limit,
            body.currency,
            body.conditions,
            body.override_rationale,
        )
    return decision_payload(x)


@router.get("/credit-review-cases/{review_case_id}/decisions")
def decision_history(
    review_case_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _case(session, review_case_id)
    return [
        decision_payload(x)
        for x in session.scalars(
            select(CreditHumanDecision)
            .where(CreditHumanDecision.review_case_id == review_case_id)
            .order_by(CreditHumanDecision.decision_version)
        )
    ]


@router.post("/credit-review-cases/{review_case_id}/committee-package")
def create_committee_package(
    review_case_id: UUID, body: ActorRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        x = CreditReviewService(session).committee_package(review_case_id, body.actor_user_id)
    return package_payload(session, x)


@router.get("/credit-review-cases/{review_case_id}/committee-packages")
def list_committee_packages(
    review_case_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    _case(session, review_case_id)
    return [
        package_payload(session, x)
        for x in session.scalars(
            select(CreditCommitteePackage)
            .where(CreditCommitteePackage.review_case_id == review_case_id)
            .order_by(CreditCommitteePackage.package_version)
        )
    ]


@router.get("/credit-committee-packages/{package_id}")
def get_committee_package(
    package_id: UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    x = session.get(CreditCommitteePackage, package_id)
    if x is None:
        raise AppError("COMMITTEE_PACKAGE_NOT_FOUND", "Committee package not found", 404)
    return package_payload(session, x)


@router.post("/credit-committee-packages/{package_id}/mark-ready")
def mark_committee_package_ready(
    package_id: UUID, body: ActorRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    with session.begin():
        x = CreditReviewService(session).mark_ready(package_id, body.actor_user_id)
    return package_payload(session, x)


@router.get("/credit-review-cases/{review_case_id}/timeline")
def get_timeline(
    review_case_id: UUID, session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    return timeline(session, _case(session, review_case_id))
