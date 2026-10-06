from __future__ import annotations

# ruff: noqa: E501
from datetime import UTC, datetime, timedelta

from app.runtime.provider_safety import reject_development_provider
from app.services.external_research.providers.base import ResearchProvider
from app.services.external_research.schemas import ProviderResult, QueryDraft


class FixtureResearchProvider(ResearchProvider):
    name = "deterministic_fixture"
    version = "fixture_research_provider_v1"

    def search(self, query: QueryDraft, legal_name: str) -> list[ProviderResult]:
        reject_development_provider()
        today = datetime.now(UTC).date()
        recent = today - timedelta(days=45)
        events: dict[str, list[ProviderResult]] = {
            "COMPANY": [
                ProviderResult(
                    "COMPANY",
                    f"{legal_name} commissions expanded plant",
                    "Company Exchange Filings",
                    "OFFICIAL",
                    "https://exchange.example.test/filings/expansion?utm_source=feed",
                    f"{legal_name} commissioned an expanded manufacturing plant. Commercial production has begun.",
                    legal_name,
                    "COMPANY_CAPACITY_EXPANSION_REPORTED",
                    "POSITIVE",
                    recent,
                    recent,
                ),
                ProviderResult(
                    "COMPANY",
                    "ABC Power LLC opens Texas office",
                    "Regional Wire",
                    "REPUTABLE_NEWS",
                    "https://news.example.test/texas/abc-power",
                    "ABC Power LLC of Texas opened an office in Austin, Texas.",
                    "ABC Power LLC",
                    "COMPANY_EXPANSION_REPORTED",
                    "POSITIVE",
                    recent,
                    recent,
                ),
            ],
            "LEGAL": [
                ProviderResult(
                    "LEGAL",
                    f"Regulatory penalty order concerning {legal_name}",
                    "Securities Regulator",
                    "REGULATOR",
                    "https://regulator.example.test/orders/penalty-2026",
                    f"The regulator imposed an administrative monetary penalty on {legal_name} for a reporting breach. The order does not allege fraud or record a criminal conviction.",
                    legal_name,
                    "REGULATORY_PENALTY_ORDER",
                    "NEGATIVE",
                    recent,
                    recent,
                    {"legal_status": "PENALTY_ORDERED"},
                ),
                ProviderResult(
                    "LEGAL",
                    f"Regulator issues penalty order to {legal_name}",
                    "Financial Daily",
                    "REPUTABLE_NEWS",
                    "https://wire.example.test/story/penalty-2026?utm_medium=syndication",
                    f"The regulator imposed an administrative monetary penalty on {legal_name} for a reporting breach. The order does not allege fraud or record a criminal conviction.",
                    legal_name,
                    "REGULATORY_PENALTY_ORDER",
                    "NEGATIVE",
                    recent,
                    recent,
                    {"legal_status": "PENALTY_ORDERED", "syndicated": True},
                ),
                ProviderResult(
                    "LEGAL",
                    f"Reporting breach penalty recorded for {legal_name}",
                    "National Business News",
                    "REPUTABLE_NEWS",
                    "https://business.example.test/regulation/penalty-analysis-2026",
                    f"A securities authority ordered {legal_name} to pay a monetary fine after a reporting-compliance breach. No criminal conviction was reported.",
                    legal_name,
                    "REGULATORY_PENALTY_ORDER",
                    "NEGATIVE",
                    recent,
                    recent,
                    {"legal_status": "PENALTY_ORDERED"},
                ),
                ProviderResult(
                    "LEGAL",
                    f"Investigation reported concerning {legal_name}",
                    "Business Journal",
                    "REPUTABLE_NEWS",
                    "https://journal.example.test/legal/investigation-2026",
                    f"{legal_name} is reported to be under regulatory investigation. The report describes an allegation and no finding or conviction.",
                    legal_name,
                    "REGULATORY_INVESTIGATION_REPORTED",
                    "REVIEW",
                    recent,
                    recent,
                    {"legal_status": "ALLEGATION_UNPROVEN"},
                ),
            ],
            "RATINGS": [
                ProviderResult(
                    "RATINGS",
                    f"Rating action for {legal_name}",
                    "CARE Ratings",
                    "RATING_AGENCY",
                    "https://ratings.example.test/releases/company-2026",
                    f"CARE Ratings downgraded {legal_name} from BBB+ to BBB and revised the outlook to Negative.",
                    legal_name,
                    "CREDIT_RATING_DOWNGRADED",
                    "NEGATIVE",
                    recent,
                    recent,
                    {
                        "agency": "CARE Ratings",
                        "action": "DOWNGRADE",
                        "rating_from": "BBB+",
                        "rating_to": "BBB",
                        "outlook": "Negative",
                    },
                ),
            ],
            "PROMOTER": [
                ProviderResult(
                    "PROMOTER",
                    f"Director disqualification record linked to {legal_name}",
                    "Corporate Affairs Registry",
                    "GOVERNMENT",
                    "https://registry.example.test/directors/disqualification",
                    f"A director associated with {legal_name} appears in a disqualification record and requires identity review.",
                    legal_name,
                    "DIRECTOR_DISQUALIFICATION_REPORTED",
                    "REVIEW",
                    recent,
                    recent,
                ),
            ],
            "INDUSTRY": [
                ProviderResult(
                    "INDUSTRY",
                    "Industry demand outlook remains mixed",
                    "Industry Association",
                    "INDUSTRY_BODY",
                    "https://industry.example.test/outlook/2026",
                    "The Indian industry outlook is mixed: order growth is offset by higher input costs and weaker export demand.",
                    legal_name,
                    "INDUSTRY_DEMAND_OUTLOOK_MIXED",
                    "MIXED",
                    recent,
                    recent,
                ),
                ProviderResult(
                    "INDUSTRY",
                    "Industry demand outlook copy",
                    "Market Syndication Network",
                    "REPUTABLE_NEWS",
                    "https://syndicate.example.test/outlook/2026?utm_campaign=copy",
                    "The Indian industry outlook is mixed: order growth is offset by higher input costs and weaker export demand.",
                    legal_name,
                    "INDUSTRY_DEMAND_OUTLOOK_MIXED",
                    "MIXED",
                    recent,
                    recent,
                    {"syndicated": True},
                ),
            ],
            "SECTOR": [
                ProviderResult(
                    "SECTOR",
                    "Sector capital expenditure outlook",
                    "Economic Ministry",
                    "GOVERNMENT",
                    "https://government.example.test/sector/outlook-2026",
                    "The sector outlook indicates stable domestic demand with uneven capital expenditure growth.",
                    legal_name,
                    "SECTOR_OUTLOOK_MIXED",
                    "MIXED",
                    recent,
                    recent,
                ),
                ProviderResult(
                    "SECTOR",
                    "Provider timeout fixture",
                    "Unavailable Source",
                    "OTHER",
                    "https://unavailable.example.test/source",
                    "",
                    legal_name,
                    "SOURCE_UNAVAILABLE",
                    "REVIEW",
                    recent,
                    recent,
                    failure_code="SOURCE_TIMEOUT",
                ),
            ],
        }
        return events.get(query.scope, [])
