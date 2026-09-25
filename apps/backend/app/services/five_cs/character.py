from __future__ import annotations

from app.models.company_profile import CompanyProfile
from app.models.document_page import DocumentPage
from app.services.five_cs.evidence import draft, unavailable
from app.services.five_cs.schemas import EvidenceDraft


def build_character(
    profile: CompanyProfile, pages: list[DocumentPage], financial_conflict: bool
) -> list[EvidenceDraft]:
    rows: list[EvidenceDraft] = []
    matched = profile.identity_match_status.value == "MATCHED"
    rows.append(
        draft(
            "CHARACTER",
            "identity",
            "CHARACTER_IDENTITY_MATCHED" if matched else "CHARACTER_IDENTITY_CONFLICT",
            "Company identity",
            "Company identity matches stored document evidence."
            if matched
            else "Company identity requires review against document evidence.",
            "POSITIVE" if matched else "REVIEW",
            profile.overall_confidence,
            "VERIFIED" if matched else "NEEDS_REVIEW",
            source_type="COMPANY_PROFILE",
            source_id=profile.id,
        )
    )
    audited = next(
        (
            page
            for page in pages
            if "independent auditor" in page.text_content.lower()
            or "audited financial" in page.text_content.lower()
        ),
        None,
    )
    if audited:
        rows.append(
            draft(
                "CHARACTER",
                "reporting",
                "CHARACTER_AUDITED_STATEMENTS_PRESENT",
                "Audited reporting evidence",
                "Stored page text explicitly identifies audited financial reporting.",
                "POSITIVE",
                audited.text_quality_score,
                "VERIFIED",
                evidence_type="DOCUMENT_EVIDENCE",
                source_type="DOCUMENT_PAGE",
                source_id=audited.id,
                lineage=(audited.id, audited.page_number),
                raw_value=audited.text_content[:500],
            )
        )
    else:
        rows.append(
            draft(
                "CHARACTER",
                "reporting",
                "CHARACTER_REPORTING_CONSISTENT",
                "Internal reporting context",
                "No explicit audited-statement phrase was identified in stored pages.",
                "REVIEW",
                profile.overall_confidence,
                "NEEDS_REVIEW",
                source_type="COMPANY_PROFILE",
                source_id=profile.id,
            )
        )
    if financial_conflict:
        rows.append(
            draft(
                "CHARACTER",
                "reporting",
                "CHARACTER_FINANCIAL_CONFLICTS_PRESENT",
                "Financial reporting conflict",
                "Persisted financial inputs contain a conflict requiring review.",
                "REVIEW",
                0.5,
                "CONFLICTING",
                source_type="COMPANY_PROFILE",
                source_id=profile.id,
            )
        )
    rows.extend(
        (
            unavailable(
                "CHARACTER",
                "promoter_background",
                "CHARACTER_PROMOTER_RESEARCH_UNAVAILABLE",
                "Promoter background unavailable",
                "No external promoter research has been collected.",
            ),
            unavailable(
                "CHARACTER",
                "repayment_history",
                "CHARACTER_REPAYMENT_HISTORY_UNAVAILABLE",
                "Repayment history unavailable",
                "No bureau or verified repayment-history evidence has been collected.",
            ),
            unavailable(
                "CHARACTER",
                "legal_background",
                "CHARACTER_EXTERNAL_BACKGROUND_UNAVAILABLE",
                "Legal and background evidence unavailable",
                "No external legal-case or background research has been collected.",
            ),
        )
    )
    return rows
