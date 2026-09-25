from __future__ import annotations

# ruff: noqa: E501
from uuid import UUID

from app.models.company_profile import CompanyProfile
from app.models.domain_classification import DomainClassification
from app.models.financial_trend import FinancialAnomaly, FinancialTrend
from app.services.five_cs.evidence import draft, unavailable
from app.services.five_cs.schemas import EvidenceDraft


def build_conditions(
    profile: CompanyProfile,
    domain: DomainClassification | None,
    trends: dict[str, FinancialTrend],
    anomalies: dict[str, FinancialAnomaly],
    lineage: dict[UUID, tuple[UUID, int]],
) -> list[EvidenceDraft]:
    rows: list[EvidenceDraft] = []
    if profile.business_description:
        rows.append(
            draft(
                "CONDITIONS",
                "business_profile",
                "CONDITIONS_BUSINESS_PROFILE_AVAILABLE",
                "Internal business context",
                "A source-backed company business description is available.",
                "NEUTRAL",
                profile.overall_confidence,
                "VERIFIED" if profile.status.value == "VERIFIED" else "NEEDS_REVIEW",
                source_type="COMPANY_PROFILE",
                source_id=profile.id,
                normalized_value=profile.business_description,
            )
        )
    if domain and domain.status.value == "VERIFIED":
        rows.append(
            draft(
                "CONDITIONS",
                "domain",
                "CONDITIONS_BUSINESS_DOMAIN_IDENTIFIED",
                "Verified development domain context",
                f"Internal classification identifies {domain.sector} / {domain.industry} / {domain.domain}.",
                "NEUTRAL",
                domain.overall_confidence,
                "VERIFIED",
                source_type="DOMAIN_CLASSIFICATION",
                source_id=domain.id,
                lineage=lineage.get(domain.id),
                normalized_value=domain.domain,
            )
        )
    else:
        rows.append(
            unavailable(
                "CONDITIONS",
                "domain",
                "CONDITIONS_DOMAIN_UNVERIFIED",
                "Domain context requires review",
                "No verified domain classification is available.",
            )
        )
    revenue = trends.get("revenue") or trends.get("revenue_from_operations")
    if revenue:
        declining = revenue.trend_direction.value == "DECREASING"
        rows.append(
            draft(
                "CONDITIONS",
                "revenue_trend",
                "CONDITIONS_REVENUE_DECLINE"
                if declining
                else "CONDITIONS_REVENUE_TREND_POSITIVE"
                if revenue.trend_direction.value == "INCREASING"
                else "CONDITIONS_REVENUE_TREND_AVAILABLE",
                "Company revenue trend",
                f"The company-specific revenue trend is {revenue.trend_direction.value.lower()}.",
                "NEGATIVE"
                if declining
                else "POSITIVE"
                if revenue.trend_direction.value == "INCREASING"
                else "NEUTRAL",
                revenue.confidence_score,
                revenue.status.value,
                source_type="FINANCIAL_TREND",
                source_id=revenue.id,
                lineage=lineage.get(revenue.id),
                normalized_value=revenue.trend_direction.value,
            )
        )
    if margin := anomalies.get("NET_MARGIN_COMPRESSION") or anomalies.get(
        "EBITDA_MARGIN_COMPRESSION"
    ):
        rows.append(
            draft(
                "CONDITIONS",
                "margin_trend",
                "CONDITIONS_MARGIN_COMPRESSION",
                "Company margin compression",
                margin.description,
                "NEGATIVE",
                margin.confidence_score,
                margin.status.value,
                source_type="FINANCIAL_ANOMALY",
                source_id=margin.id,
                lineage=lineage.get(margin.id),
            )
        )
    rows.extend(
        (
            unavailable(
                "CONDITIONS",
                "external_outlook",
                "CONDITIONS_EXTERNAL_SECTOR_OUTLOOK_UNAVAILABLE",
                "External sector outlook unavailable",
                "No external industry or sector outlook has been collected.",
            ),
            unavailable(
                "CONDITIONS",
                "regulatory_research",
                "CONDITIONS_REGULATORY_RESEARCH_UNAVAILABLE",
                "Regulatory research unavailable",
                "No external regulatory research has been collected.",
            ),
            unavailable(
                "CONDITIONS",
                "macro_research",
                "CONDITIONS_MACRO_RESEARCH_UNAVAILABLE",
                "Macroeconomic research unavailable",
                "No external macroeconomic research has been collected.",
            ),
        )
    )
    return rows
