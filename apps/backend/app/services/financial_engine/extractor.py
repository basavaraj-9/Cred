from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from app.models.document_page import DocumentPage
from app.models.enums import (
    FinancialScope,
    FinancialStatementType,
    FinancialStatus,
    PageExtractionMethod,
)
from app.services.financial_engine.parsing import (
    Period,
    currency,
    date_periods,
    heading,
    parse_number,
    row,
    scope,
    unit,
)
from app.services.financial_engine.taxonomy import map_label

EXTRACTOR_VERSION = "financial_extractor_v1"


@dataclass
class Candidate:
    page: DocumentPage
    raw_label: str
    raw_value: str
    canonical_name: str | None
    measurement_type: str
    numeric_value: Decimal | None
    period: Period | None
    currency: str | None
    raw_unit: str | None
    normalized_unit: str | None
    unit_multiplier: Decimal
    evidence_text: str
    confidence: float
    status: FinancialStatus
    source_priority: int


@dataclass
class StatementDraft:
    statement_type: FinancialStatementType
    statement_scope: FinancialScope
    start_page: int
    end_page: int
    currency: str | None = None
    raw_unit: str | None = None
    normalized_unit: str | None = None
    unit_multiplier: Decimal = Decimal(1)
    periods: list[Period] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)


def _confidence(
    page: DocumentPage, *, mapped: bool, period: bool, scope_known: bool, numeric: bool
) -> float:
    # Deterministic rules: heading .35, mapped label .25, period .14,
    # numeric parse .12, scope .04, page quality up to .10; OCR loses .16.
    score = 0.35 + (0.25 if mapped else 0) + (0.14 if period else 0) + (0.12 if numeric else 0)
    score += 0.04 if scope_known else 0
    score += 0.10 * max(0, min(1, page.text_quality_score))
    if page.extraction_method == PageExtractionMethod.OCR:
        score -= 0.16
    return round(max(0, min(1, score)), 2)


def extract(pages: Sequence[DocumentPage]) -> list[StatementDraft]:
    drafts: list[StatementDraft] = []
    current: StatementDraft | None = None
    for page in pages:
        lines = page.text_content.splitlines()
        note_page = any("notes to financial statements" in line.casefold() for line in lines[:12])
        note_periods: list[Period] = []
        note_currency: str | None = None
        note_raw_unit: str | None = None
        note_unit: str | None = None
        note_multiplier = Decimal(1)
        page_has_heading = any(heading(line) for line in lines)
        if current and page.page_number != current.end_page + 1:
            current = None
        if current and not page_has_heading:
            # A continuation requires a nearby table row; unrelated narrative stops it.
            if not any(row(line) for line in lines[:35]):
                current = None
        page_scope = scope(" ".join(lines[:12]))
        page_priority = 2 if note_page else 1
        for index, line in enumerate(lines):
            if note_page and "notes to financial statements" in line.casefold():
                current = None
                continue
            detected = heading(line)
            if detected:
                local_scope = scope(" ".join(lines[max(0, index - 2) : index + 2]))
                if local_scope == FinancialScope.UNKNOWN:
                    local_scope = page_scope
                current = StatementDraft(detected, local_scope, page.page_number, page.page_number)
                drafts.append(current)
                continue
            if current is None and note_page:
                note_currency = currency(line) or note_currency
                found_unit = unit(line)
                if found_unit[1]:
                    note_raw_unit, note_unit, note_multiplier = found_unit
                if "particulars" in line.casefold() and date_periods(line):
                    note_periods = date_periods(line)
                note_row = row(line)
                if note_row:
                    matches = [
                        statement_type
                        for statement_type in FinancialStatementType
                        if map_label(statement_type, note_row[0])
                    ]
                    if len(matches) == 1:
                        current = StatementDraft(
                            matches[0],
                            page_scope,
                            page.page_number,
                            page.page_number,
                            note_currency,
                            note_raw_unit,
                            note_unit,
                            note_multiplier,
                            note_periods,
                        )
                        drafts.append(current)
            if current is None:
                continue
            current.end_page = page.page_number
            explicit_currency = currency(line)
            if explicit_currency:
                current.currency = explicit_currency
            raw_unit, normalized_unit, multiplier = unit(line)
            if normalized_unit:
                current.raw_unit, current.normalized_unit, current.unit_multiplier = (
                    raw_unit,
                    normalized_unit,
                    multiplier,
                )
            if (
                "particulars" in line.casefold()
                or "year ended" in line.casefold()
                or "as at" in line.casefold()
            ) and date_periods(line):
                current.periods = date_periods(line)
                continue
            parsed_row = row(line)
            if parsed_row is None:
                continue
            label, values = parsed_row
            # Year-only rows and page furniture are never candidates.
            if label.casefold() in {"particulars", "notes", "note", "page"}:
                continue
            mapping = map_label(current.statement_type, label)
            if not mapping and len(label.split()) > 8:
                continue
            periods = current.periods
            for column, raw_value in enumerate(values):
                if periods and column >= len(periods):
                    break
                period = periods[column] if column < len(periods) else None
                numeric = parse_number(raw_value)
                confidence = _confidence(
                    page,
                    mapped=bool(mapping),
                    period=period is not None,
                    scope_known=current.statement_scope != FinancialScope.UNKNOWN,
                    numeric=numeric is not None,
                )
                status = (
                    FinancialStatus.UNMAPPED
                    if mapping is None
                    else FinancialStatus.UNAVAILABLE
                    if numeric is None
                    else FinancialStatus.VERIFIED
                    if confidence >= 0.85
                    else FinancialStatus.NEEDS_REVIEW
                )
                measurement = mapping[1] if mapping else "MONETARY"
                candidate = Candidate(
                    page,
                    label,
                    raw_value,
                    mapping[0] if mapping else None,
                    measurement,
                    numeric,
                    period,
                    currency(raw_value) or current.currency,
                    current.raw_unit if measurement == "MONETARY" else None,
                    current.normalized_unit if measurement == "MONETARY" else "ABSOLUTE",
                    current.unit_multiplier if measurement == "MONETARY" else Decimal(1),
                    line.strip()[:500],
                    confidence,
                    status,
                    page_priority,
                )
                current.candidates.append(candidate)
    return [draft for draft in drafts if draft.candidates]


def reconcile(drafts: list[StatementDraft]) -> None:
    groups: dict[tuple, list[Candidate]] = {}
    for draft in drafts:
        for candidate in draft.candidates:
            if (
                candidate.canonical_name
                and candidate.period
                and candidate.numeric_value is not None
            ):
                key = (
                    draft.statement_type,
                    draft.statement_scope,
                    candidate.period.fiscal_year,
                    candidate.canonical_name,
                )
                groups.setdefault(key, []).append(candidate)
    for candidates in groups.values():
        currencies = {item.currency for item in candidates}
        units = {item.normalized_unit for item in candidates}
        # Missing or mixed currencies/units cannot prove a disagreement.
        if len(currencies) > 1 or None in units:
            for item in candidates:
                item.status = FinancialStatus.NEEDS_REVIEW
            continue
        comparable_values = {
            item.numeric_value * item.unit_multiplier
            if item.measurement_type == "MONETARY"
            else item.numeric_value
            for item in candidates
            if item.numeric_value is not None
        }
        if len(comparable_values) > 1:
            for item in candidates:
                item.status = FinancialStatus.CONFLICTING
        elif len(candidates) > 1:
            preferred = min(
                candidates, key=lambda item: (item.source_priority, item.page.page_number)
            )
            for item in candidates:
                if item is not preferred and item.status == FinancialStatus.VERIFIED:
                    item.status = FinancialStatus.NEEDS_REVIEW
