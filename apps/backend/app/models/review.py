from __future__ import annotations

# ruff: noqa: E501
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CreditReviewCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_review_cases"
    __table_args__ = (
        CheckConstraint(
            "workflow_status IN ('PENDING_REVIEW','ASSIGNED','IN_REVIEW','AWAITING_INFORMATION','AWAITING_EXCEPTION_APPROVAL','READY_FOR_DECISION','REFERRED_TO_COMMITTEE','DECIDED','CLOSED','CANCELLED','STALE','UPDATED_ANALYSIS_AVAILABLE')",
            name="workflow_status_valid",
        ),
        CheckConstraint("priority IN ('LOW','NORMAL','HIGH','URGENT')", name="priority_valid"),
        UniqueConstraint("decision_support_id", "input_hash", name="uq_credit_review_case_input"),
        Index("ix_credit_review_cases_workflow", "workflow_status", "updated_at"),
        Index("ix_credit_review_cases_reviewer", "primary_reviewer_id", "workflow_status"),
    )
    decision_support_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_decision_support.id"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    analysis_job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=False)
    workflow_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="PENDING_REVIEW"
    )
    primary_reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="NORMAL")
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    case_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class CreditReviewAssignment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_review_assignments"
    review_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_review_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditReviewComment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_review_comments"
    __table_args__ = (
        CheckConstraint(
            "comment_type IN ('GENERAL','RISK_NOTE','EVIDENCE_NOTE','INFORMATION_REQUEST','EXCEPTION_NOTE','COMMITTEE_NOTE','DECISION_RATIONALE')",
            name="comment_type_valid",
        ),
    )
    review_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_review_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    comment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, default="INTERNAL")
    source_reference_type: Mapped[str | None] = mapped_column(String(80))
    source_reference_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditReviewEvidenceAcknowledgement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_review_evidence_acknowledgements"
    __table_args__ = (
        CheckConstraint(
            "acknowledgement_status IN ('REVIEWED','ACCEPTED_FOR_REVIEW','QUESTIONED','CONFLICT_NOTED','NOT_APPLICABLE')",
            name="ack_status_valid",
        ),
    )
    review_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_review_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(nullable=False)
    acknowledgement_status: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditReviewChecklistAction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_review_checklist_actions"
    __table_args__ = (
        CheckConstraint(
            "action IN ('ACKNOWLEDGED','RESOLVED','NEEDS_INFORMATION','ESCALATED','NOT_APPLICABLE')",
            name="action_valid",
        ),
    )
    review_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_review_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision_review_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_decision_review_items.id"), nullable=False
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditInformationRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_information_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN','RECEIVED','PARTIALLY_RECEIVED','CLOSED','CANCELLED')",
            name="status_valid",
        ),
    )
    review_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_review_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN")
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)


class CreditPolicyExceptionAction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_policy_exception_actions"
    __table_args__ = (
        CheckConstraint(
            "action IN ('APPROVE_EXCEPTION','REJECT_EXCEPTION','REQUEST_INFORMATION','REFER_HIGHER')",
            name="action_valid",
        ),
    )
    policy_exception_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_policy_exceptions.id"), nullable=False, index=True
    )
    review_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_review_cases.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    authority_role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditHumanDecision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_human_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('APPROVED','DECLINED','RETURNED_FOR_INFORMATION','REFERRED_TO_COMMITTEE')",
            name="decision_valid",
        ),
        CheckConstraint(
            "approved_limit IS NULL OR approved_limit >= 0", name="approved_limit_nonnegative"
        ),
        CheckConstraint(
            "approved_limit IS NULL OR currency IS NOT NULL", name="approved_limit_currency"
        ),
        UniqueConstraint(
            "review_case_id", "decision_version", name="uq_credit_human_decision_version"
        ),
        Index(
            "uq_credit_human_decision_current",
            "review_case_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )
    review_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_review_cases.id", ondelete="CASCADE"), nullable=False
    )
    decision_support_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_decision_support.id"), nullable=False
    )
    decided_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    decision_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    decision_authority_role: Mapped[str] = mapped_column(String(50), nullable=False)
    approved_limit: Mapped[Decimal | None] = mapped_column(Numeric(38, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    conditions_json: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    override_rationale: Mapped[str | None] = mapped_column(Text)
    decision_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    decision_version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    superseded_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_human_decisions.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditDecisionOverride(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_decision_overrides"
    __table_args__ = (
        CheckConstraint(
            "override_type IN ('SYSTEM_RECOMMENDATION_OVERRIDE','LIMIT_OVERRIDE','POLICY_EXCEPTION_OVERRIDE')",
            name="override_type_valid",
        ),
    )
    human_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_human_decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    override_type: Mapped[str] = mapped_column(String(50), nullable=False)
    system_value: Mapped[str] = mapped_column(Text, nullable=False)
    human_value: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditCommitteePackage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_committee_packages"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','READY','SUPERSEDED')", name="status_valid"),
        CheckConstraint("package_version > 0", name="version_positive"),
        UniqueConstraint(
            "review_case_id", "package_version", name="uq_credit_committee_package_version"
        ),
        UniqueConstraint("review_case_id", "input_hash", name="uq_credit_committee_package_input"),
    )
    review_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_review_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision_support_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_decision_support.id"), nullable=False
    )
    package_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    prepared_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    prepared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary_version: Mapped[str] = mapped_column(String(100), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreditCommitteePackageSection(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_committee_package_sections"
    __table_args__ = (
        UniqueConstraint("package_id", "section_code", name="uq_credit_committee_section"),
    )
    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_committee_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    structured_payload_json: Mapped[dict[str, object] | list[object]] = mapped_column(
        JSON, nullable=False
    )
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
