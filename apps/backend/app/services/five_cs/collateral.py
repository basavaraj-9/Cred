from __future__ import annotations

# ruff: noqa: E501
import re

from app.models.document_page import DocumentPage
from app.services.five_cs.evidence import draft, unavailable
from app.services.five_cs.schemas import EvidenceDraft

SECURITY_PATTERN = re.compile(
    r"\b(secured\s+(?:by|borrowings?|loans?)|first\s+charge|second\s+charge|mortgage|hypothecation|pledged|security\s+created|collateral\s+security|charge\s+on)\b",
    re.I,
)
ASSET_TYPE_PATTERN = re.compile(
    r"\b(plant and machinery|land|building|property|inventory|receivables|current assets)\b", re.I
)


def build_collateral(pages: list[DocumentPage]) -> list[EvidenceDraft]:
    rows: list[EvidenceDraft] = []
    for page in pages:
        match = SECURITY_PATTERN.search(page.text_content)
        if not match:
            continue
        start, end = max(0, match.start() - 120), min(len(page.text_content), match.end() + 220)
        snippet = " ".join(page.text_content[start:end].split())
        secured = "secured" in match.group(0).lower()
        rows.append(
            draft(
                "COLLATERAL",
                "security_description",
                "COLLATERAL_SECURED_BORROWINGS_MENTIONED"
                if secured
                else "COLLATERAL_SECURITY_MENTIONED",
                "Explicit security mention",
                "Stored page text contains explicit security wording; this does not establish collateral value.",
                "REVIEW",
                page.text_quality_score,
                "NEEDS_REVIEW",
                evidence_type="DOCUMENT_EVIDENCE",
                source_type="DOCUMENT_PAGE",
                source_id=page.id,
                lineage=(page.id, page.page_number),
                raw_value=snippet,
            )
        )
        asset = ASSET_TYPE_PATTERN.search(snippet)
        if asset:
            rows.append(
                draft(
                    "COLLATERAL",
                    "asset_type",
                    "COLLATERAL_ASSET_CHARGE_MENTIONED",
                    "Charged asset type mentioned",
                    "An asset type occurs within explicit security wording and requires human confirmation.",
                    "REVIEW",
                    page.text_quality_score,
                    "NEEDS_REVIEW",
                    evidence_type="DOCUMENT_EVIDENCE",
                    source_type="DOCUMENT_PAGE",
                    source_id=page.id,
                    lineage=(page.id, page.page_number),
                    raw_value=snippet,
                    normalized_value=asset.group(0).lower(),
                )
            )
        break
    if not rows:
        rows.append(
            unavailable(
                "COLLATERAL",
                "security_description",
                "COLLATERAL_SECURITY_DETAILS_INCOMPLETE",
                "Security evidence unavailable",
                "No explicit security phrase was identified in stored document pages.",
            )
        )
    rows.extend(
        (
            unavailable(
                "COLLATERAL",
                "collateral_value",
                "COLLATERAL_VALUE_UNAVAILABLE",
                "Collateral value unavailable",
                "No reliable collateral valuation is available.",
            ),
            unavailable(
                "COLLATERAL",
                "external_valuation",
                "COLLATERAL_EXTERNAL_VALUATION_UNAVAILABLE",
                "Independent valuation unavailable",
                "No independent external collateral valuation has been collected.",
            ),
            unavailable(
                "COLLATERAL",
                "ltv",
                "COLLATERAL_LTV_UNAVAILABLE",
                "Loan-to-value unavailable",
                "Loan-to-value is not calculated without compatible exposure and valuation evidence.",
            ),
        )
    )
    return rows
