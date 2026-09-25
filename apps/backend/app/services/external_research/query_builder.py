from __future__ import annotations

# ruff: noqa: E501
import hashlib
from dataclasses import dataclass

from app.models.company_profile import CompanyProfile
from app.models.domain_classification import DomainClassification
from app.models.enums import ClassificationStatus, FieldStatus, IdentityMatchStatus, ProfileStatus
from app.models.extracted_field import ExtractedField
from app.services.external_research.policy import VALID_SCOPES
from app.services.external_research.schemas import QueryDraft

PROMOTER_FIELDS = {"promoter_name", "director_name", "managing_director", "chairperson"}


@dataclass(frozen=True)
class QueryContext:
    legal_name: str
    aliases: tuple[str, ...]
    promoters: tuple[str, ...]
    industry: str | None
    sector: str | None


def verified_context(
    profile: CompanyProfile,
    fields: list[ExtractedField],
    domain: DomainClassification | None,
) -> QueryContext:
    if (
        profile.status != ProfileStatus.VERIFIED
        or profile.identity_match_status != IdentityMatchStatus.MATCHED
        or not profile.legal_name
    ):
        raise ValueError("VERIFIED_COMPANY_IDENTITY_REQUIRED")
    promoters = tuple(
        sorted(
            {
                row.normalized_value.strip()
                for row in fields
                if row.field_name in PROMOTER_FIELDS
                and row.status == FieldStatus.VERIFIED
                and row.normalized_value.strip()
            }
        )
    )
    verified_domain = domain is not None and domain.status == ClassificationStatus.VERIFIED
    return QueryContext(
        legal_name=profile.legal_name.strip(),
        aliases=(),
        promoters=promoters,
        industry=domain.industry if verified_domain and domain else None,
        sector=domain.sector if verified_domain and domain else None,
    )


def build_queries(context: QueryContext, scopes: list[str]) -> list[QueryDraft]:
    requested = list(dict.fromkeys(item.upper() for item in scopes))
    unknown = set(requested) - set(VALID_SCOPES)
    if unknown:
        raise ValueError("RESEARCH_SCOPE_INVALID")
    drafts: list[QueryDraft] = []
    name = f'"{context.legal_name}"'
    for scope in requested:
        if scope == "PROMOTER":
            drafts.extend(
                QueryDraft(scope, f'"{person}" {name} regulatory legal')
                for person in context.promoters
            )
        elif scope == "INDUSTRY" and context.industry:
            drafts.append(QueryDraft(scope, f'"{context.industry}" India demand outlook'))
        elif scope == "SECTOR" and context.sector:
            drafts.append(QueryDraft(scope, f'"{context.sector}" India sector outlook'))
        elif scope in {"INDUSTRY", "SECTOR"}:
            continue
        else:
            suffix = {
                "COMPANY": "company expansion shutdown material event",
                "LEGAL": "regulatory order investigation penalty court case",
                "RATINGS": "credit rating upgrade downgrade outlook withdrawal",
            }[scope]
            drafts.append(QueryDraft(scope, f"{name} {suffix}"))
    unique: dict[str, QueryDraft] = {}
    for draft in drafts:
        unique.setdefault(hashlib.sha256(draft.text.casefold().encode()).hexdigest(), draft)
    return list(unique.values())
