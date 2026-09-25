from __future__ import annotations

# ruff: noqa: E501
from app.services.five_cs.schemas import EvidenceDraft


def _values(evidence: list[EvidenceDraft]) -> dict[str, str]:
    return {
        item.availability_key: item.normalized_value
        for item in evidence
        if item.normalized_value is not None and item.status != "UNAVAILABLE"
    }


def summary(section: str, evidence: list[EvidenceDraft]) -> str:
    values = _values(evidence)
    codes = {item.observation_code for item in evidence}
    if section == "CHARACTER":
        identity = "consistent" if "CHARACTER_IDENTITY_MATCHED" in codes else "requires review"
        return (
            f"Internal document identity evidence is {identity}. External promoter, legal, bureau, "
            "and repayment-history evidence is unavailable; Character remains incomplete."
        )
    if section == "CAPACITY":
        details = []
        for key, label in (
            ("interest_coverage", "Interest coverage"),
            ("debt_to_ebitda", "Debt/EBITDA"),
            ("ocf_to_debt", "Operating cash flow/debt"),
        ):
            if key in values:
                details.append(f"{label} is {values[key]}")
        suffix = (
            " Review observations are present."
            if any(item.impact in {"NEGATIVE", "REVIEW"} for item in evidence)
            else ""
        )
        return (
            ". ".join(details) + "."
            if details
            else "Critical repayment indicators are unavailable."
        ) + suffix
    if section == "CAPITAL":
        details = []
        for key, label in (
            ("total_equity", "Total equity"),
            ("debt_to_equity", "Debt/equity"),
            ("debt_to_assets", "Debt/assets"),
        ):
            if key in values:
                details.append(f"{label} is {values[key]}")
        return (
            ". ".join(details)
            + ". Capital observations use persisted balance-sheet analytics only."
            if details
            else "Capital evidence is incomplete; unavailable values were not derived."
        )
    if section == "COLLATERAL":
        if (
            "COLLATERAL_SECURITY_MENTIONED" in codes
            or "COLLATERAL_SECURED_BORROWINGS_MENTIONED" in codes
        ):
            return "Explicit security wording appears in the stored document text, but collateral value, coverage, LTV, and independent valuation are unavailable."
        return "No explicit collateral or security evidence was identified. Generic assets and PPE were not treated as collateral."
    return "Internal business and company-specific financial context is available where verified. External sector, regulatory, and macroeconomic research is unavailable."
