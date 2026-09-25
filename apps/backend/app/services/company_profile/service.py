import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.company_profile import CompanyProfile
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.enums import (
    AnalysisStage,
    FieldStatus,
    IdentityMatchStatus,
    ParserStatus,
    ProfileStatus,
)
from app.models.extracted_field import ExtractedField
from app.schemas.company_profile import EvidenceResponse, FieldSummary, ProfileResponse
from app.services.company_profile.extractor import (
    EXTRACTOR_VERSION,
    Candidate,
    compare_identity,
    extract_candidates,
)

logger = logging.getLogger(__name__)
FIELD_NAMES = (
    "legal_name",
    "reporting_period",
    "business_description",
    "headquarters",
    "registered_office",
    "country",
    "website",
    "product",
    "service",
    "operating_segment",
)


def _response(session: Session, profile: CompanyProfile, uploaded_name: str) -> ProfileResponse:
    rows = session.scalars(
        select(ExtractedField)
        .where(ExtractedField.company_profile_id == profile.id)
        .order_by(ExtractedField.page_number, ExtractedField.field_name)
    ).all()
    fields: dict[str, list[FieldSummary]] = {name: [] for name in FIELD_NAMES}
    for row in rows:
        fields.setdefault(row.field_name, []).append(
            FieldSummary(
                id=row.id,
                field_name=row.field_name,
                value=row.normalized_value,
                confidence=row.confidence_score,
                status=row.status,
                page_number=row.page_number,
            )
        )
    return ProfileResponse(
        profile_id=profile.id,
        document_id=profile.document_id,
        company_id=profile.company_id,
        analysis_job_id=profile.analysis_job_id,
        uploaded_company_name=uploaded_name,
        status=profile.status,
        identity_match_status=profile.identity_match_status,
        overall_confidence=profile.overall_confidence,
        extractor_version=profile.extractor_version,
        fields=fields,
    )


def _best(candidates: list[Candidate], field: str) -> Candidate | None:
    choices = [candidate for candidate in candidates if candidate.field_name == field]
    return max(choices, key=lambda item: (item.confidence, -item.page.page_number), default=None)


def _profile_status(
    candidates: list[Candidate], identity: IdentityMatchStatus, parser: ParserStatus
) -> ProfileStatus:
    legal = _best(candidates, "legal_name")
    if legal and legal.status == FieldStatus.CONFLICTING:
        return ProfileStatus.CONFLICTING
    if (
        legal is None
        or legal.status != FieldStatus.VERIFIED
        or identity != IdentityMatchStatus.MATCHED
    ):
        return ProfileStatus.NEEDS_REVIEW
    if parser == ParserStatus.PARTIAL:
        return ProfileStatus.NEEDS_REVIEW
    critical = (_best(candidates, "reporting_period"), _best(candidates, "business_description"))
    if all(item is not None and item.status == FieldStatus.VERIFIED for item in critical):
        return ProfileStatus.VERIFIED
    return ProfileStatus.PARTIAL


def _extract_profile(session: Session, document_id: UUID) -> ProfileResponse:
    with session.begin():
        document = session.get(Document, document_id, with_for_update=True)
        if document is None:
            raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
        if document.parser_status not in {
            ParserStatus.PARSED,
            ParserStatus.PARTIAL,
            ParserStatus.REVIEW_REQUIRED,
        }:
            raise AppError(
                "DOCUMENT_NOT_PARSED", "Document must be parsed before profile extraction", 409
            )
        existing = session.scalar(
            select(CompanyProfile).where(
                CompanyProfile.document_id == document_id,
                CompanyProfile.extractor_version == EXTRACTOR_VERSION,
            )
        )
        if existing is not None:
            return _response(session, existing, document.company.legal_name)
        pages = session.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        ).all()
        if not pages:
            raise AppError("DOCUMENT_NOT_PARSED", "No parsed pages are available", 409)
        logger.info("Company profile extraction started: %s pages=%s", document_id, len(pages))
        write_audit_log(
            session,
            entity_type="document",
            entity_id=document.id,
            action="COMPANY_PROFILE_EXTRACTION_STARTED",
            event_type="COMPANY_PROFILE_EXTRACTION_STARTED",
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            metadata_json={"extractor_version": EXTRACTOR_VERSION},
        )
        candidates = extract_candidates(pages, document.company.legal_name)
        legal = _best(candidates, "legal_name")
        identity = compare_identity(
            document.company.legal_name, legal.normalized_value if legal else None
        )
        # A mismatched upload label never promotes document evidence into a trusted identity.
        if identity != IdentityMatchStatus.MATCHED:
            candidates = [
                Candidate(
                    item.field_group,
                    item.field_name,
                    item.raw_value,
                    item.normalized_value,
                    item.page,
                    item.evidence_text,
                    item.confidence,
                    FieldStatus.NEEDS_REVIEW
                    if item.field_name == "legal_name" and item.status == FieldStatus.VERIFIED
                    else item.status,
                )
                for item in candidates
            ]
        status = _profile_status(candidates, identity, document.parser_status)
        verified_scores = [
            item.confidence for item in candidates if item.status == FieldStatus.VERIFIED
        ]
        profile = CompanyProfile(
            analysis_job_id=document.analysis_job_id,
            company_id=document.company_id,
            document_id=document.id,
            status=status,
            identity_match_status=identity,
            overall_confidence=round(sum(verified_scores) / len(verified_scores), 2)
            if verified_scores
            else 0.0,
            extractor_version=EXTRACTOR_VERSION,
        )
        session.add(profile)
        session.flush()
        for candidate in candidates:
            session.add(
                ExtractedField(
                    analysis_job_id=document.analysis_job_id,
                    document_id=document.id,
                    document_page_id=candidate.page.id,
                    company_profile_id=profile.id,
                    field_group=candidate.field_group,
                    field_name=candidate.field_name,
                    raw_value=candidate.raw_value,
                    normalized_value=candidate.normalized_value,
                    page_number=candidate.page.page_number,
                    evidence_text=candidate.evidence_text,
                    confidence_score=candidate.confidence,
                    status=candidate.status,
                    extractor_version=EXTRACTOR_VERSION,
                )
            )
        session.flush()
        for field in (
            "legal_name",
            "reporting_period",
            "business_description",
            "headquarters",
            "country",
            "website",
        ):
            selected = _best(candidates, field)
            if selected and selected.status == FieldStatus.VERIFIED:
                setattr(profile, field, selected.normalized_value)
        document.analysis_job.current_stage = AnalysisStage.COMPANY_EXTRACTION
        event = (
            "COMPANY_PROFILE_EXTRACTED"
            if status == ProfileStatus.VERIFIED
            else "COMPANY_PROFILE_REVIEW_REQUIRED"
        )
        write_audit_log(
            session,
            entity_type="company_profile",
            entity_id=profile.id,
            action=event,
            event_type=event,
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            metadata_json={
                "extractor_version": EXTRACTOR_VERSION,
                "field_count": len(candidates),
                "verified_count": sum(item.status == FieldStatus.VERIFIED for item in candidates),
                "conflict_count": sum(
                    item.status == FieldStatus.CONFLICTING for item in candidates
                ),
            },
        )
        if status == ProfileStatus.CONFLICTING:
            write_audit_log(
                session,
                entity_type="company_profile",
                entity_id=profile.id,
                action="COMPANY_IDENTITY_CONFLICT",
                event_type="COMPANY_IDENTITY_CONFLICT",
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
            )
        if identity == IdentityMatchStatus.MISMATCH:
            write_audit_log(
                session,
                entity_type="company_profile",
                entity_id=profile.id,
                action="COMPANY_IDENTITY_MISMATCH",
                event_type="COMPANY_IDENTITY_MISMATCH",
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
            )
        logger.info(
            "Company profile extraction finished: %s fields=%s status=%s",
            document_id,
            len(candidates),
            status,
        )
        return _response(session, profile, document.company.legal_name)


def extract_profile(session: Session, document_id: UUID) -> ProfileResponse:
    try:
        return _extract_profile(session, document_id)
    except AppError:
        raise
    except Exception as exc:
        session.rollback()
        logger.error(
            "Company profile extraction failed: %s error=%s", document_id, type(exc).__name__
        )
        try:
            with session.begin():
                document = session.get(Document, document_id)
                if document is not None:
                    write_audit_log(
                        session,
                        entity_type="document",
                        entity_id=document_id,
                        action="COMPANY_PROFILE_EXTRACTION_FAILED",
                        event_type="COMPANY_PROFILE_EXTRACTION_FAILED",
                        company_id=document.company_id,
                        analysis_job_id=document.analysis_job_id,
                        metadata_json={"extractor_version": EXTRACTOR_VERSION},
                    )
        except Exception:
            logger.error("Could not record profile extraction failure: %s", document_id)
        raise AppError(
            "PROFILE_EXTRACTION_FAILED", "Company profile extraction failed", 500
        ) from None


def get_profile(session: Session, document_id: UUID) -> ProfileResponse:
    with session.begin():
        profile = session.scalar(
            select(CompanyProfile)
            .where(CompanyProfile.document_id == document_id)
            .order_by(CompanyProfile.created_at.desc())
        )
        if profile is None:
            raise AppError("PROFILE_NOT_FOUND", "Company profile not found", 404)
        document = session.get(Document, document_id)
        assert document is not None
        return _response(session, profile, document.company.legal_name)


def get_evidence(session: Session, profile_id: UUID) -> list[EvidenceResponse]:
    with session.begin():
        if session.get(CompanyProfile, profile_id) is None:
            raise AppError("PROFILE_NOT_FOUND", "Company profile not found", 404)
        rows = session.scalars(
            select(ExtractedField)
            .where(ExtractedField.company_profile_id == profile_id)
            .order_by(ExtractedField.page_number, ExtractedField.field_name)
        ).all()
        return [EvidenceResponse.model_validate(row) for row in rows]
