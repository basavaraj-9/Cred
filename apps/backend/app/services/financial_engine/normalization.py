from decimal import Decimal

# ruff: noqa: E501
from app.models.enums import FinancialStatus, NormalizationStatus
from app.models.financial import FinancialLineItem

SUPPORTED_CURRENCIES = {"INR", "USD", "EUR", "GBP"}


def normalize_line_item(item: FinancialLineItem) -> tuple[Decimal | None, str, NormalizationStatus]:
    if item.numeric_value is None:
        return (
            None,
            "BASE_CURRENCY" if item.measurement_type == "MONETARY" else item.measurement_type,
            NormalizationStatus.UNAVAILABLE,
        )
    if item.status == FinancialStatus.CONFLICTING:
        return None, "BASE_CURRENCY", NormalizationStatus.CONFLICTING
    if item.measurement_type != "MONETARY":
        status = (
            NormalizationStatus.NEEDS_REVIEW
            if item.status != FinancialStatus.VERIFIED
            else NormalizationStatus.NORMALIZED
        )
        return item.numeric_value, item.measurement_type, status
    if not item.currency or item.currency not in SUPPORTED_CURRENCIES or item.unit_multiplier <= 0:
        return None, "BASE_CURRENCY", NormalizationStatus.INVALID_VALUE
    status = (
        NormalizationStatus.NEEDS_REVIEW
        if item.status != FinancialStatus.VERIFIED
        else NormalizationStatus.NORMALIZED
    )
    return item.numeric_value * item.unit_multiplier, "BASE_CURRENCY", status
