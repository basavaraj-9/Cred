import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from app.models.enums import FinancialScope, FinancialStatementType

HEADING_PATTERNS = (
    (
        FinancialStatementType.BALANCE_SHEET,
        re.compile(r"\b(?:balance sheet|statement of financial position)\b", re.I),
    ),
    (
        FinancialStatementType.INCOME_STATEMENT,
        re.compile(
            r"\b(?:statement of profit and loss|profit and loss account|income statement)\b", re.I
        ),
    ),
    (
        FinancialStatementType.CASH_FLOW_STATEMENT,
        re.compile(r"\b(?:statement of cash flows|cash flow statement)\b", re.I),
    ),
)
NUMBER = r"(?:\(?[-+]?\s*[₹$€£]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?-?|[—–-]|NIL|N/A|NA)"
ROW = re.compile(
    rf"^\s*(?P<label>[A-Za-z][A-Za-z &'()./\-]{{1,100}}?)\s{{2,}}"
    rf"(?P<values>{NUMBER}(?:\s{{2,}}{NUMBER})*)\s*$",
    re.I,
)
TOKEN = re.compile(NUMBER, re.I)
YEAR = re.compile(r"\b(?:FY\s*)?(20\d{2})(?:\s*[-/]\s*(\d{2,4}))?\b", re.I)
DATE = re.compile(r"\b(?:31\s+March\s+|March\s+31,?\s*)(20\d{2})\b", re.I)
UNIT = re.compile(r"\b(?:in\s+)?(thousands?|lakhs?|millions?|crores?|billions?)\b", re.I)
CURRENCIES = (
    ("INR", re.compile(r"₹|\b(?:Rs\.?|INR|Indian Rupees)\b", re.I)),
    ("USD", re.compile(r"\$|\b(?:USD|US dollars?)\b", re.I)),
    ("EUR", re.compile(r"€|\b(?:EUR|euros?)\b", re.I)),
    ("GBP", re.compile(r"£|\b(?:GBP|pounds? sterling)\b", re.I)),
)
MULTIPLIERS = {
    "ABSOLUTE": 1,
    "THOUSAND": 1_000,
    "LAKH": 100_000,
    "MILLION": 1_000_000,
    "CRORE": 10_000_000,
    "BILLION": 1_000_000_000,
}


@dataclass(frozen=True)
class Period:
    label: str
    fiscal_year: str
    end: date


def heading(line: str) -> FinancialStatementType | None:
    if len(line.strip()) > 130:
        return None
    for statement_type, pattern in HEADING_PATTERNS:
        if pattern.search(line):
            return statement_type
    return None


def scope(text: str) -> FinancialScope:
    if re.search(r"\bconsolidated\b", text, re.I):
        return FinancialScope.CONSOLIDATED
    if re.search(r"\bstandalone\b", text, re.I):
        return FinancialScope.STANDALONE
    return FinancialScope.UNKNOWN


def periods(line: str) -> list[Period]:
    found = []
    for match in YEAR.finditer(line):
        first, second = match.groups()
        ending = int(second) if second else int(first)
        if second and ending < 100:
            ending += (int(first) // 100) * 100
        label = match.group(0).strip()
        found.append(
            Period(label, f"FY{ending}", date(ending, 3, 31) if second else date(ending, 3, 31))
        )
    return found[:4]


def date_periods(line: str) -> list[Period]:
    matches = list(DATE.finditer(line))
    if not matches:
        return periods(line)
    return [
        Period(m.group(0), f"FY{m.group(1)}", date(int(m.group(1)), 3, 31)) for m in matches[:4]
    ]


def currency(text: str) -> str | None:
    for name, pattern in CURRENCIES:
        if pattern.search(text):
            return name
    return None


def unit(text: str) -> tuple[str | None, str | None, Decimal]:
    match = UNIT.search(text)
    if not match:
        return None, None, Decimal(1)
    raw = match.group(1)
    normalized = raw.upper().rstrip("S")
    return raw, normalized, Decimal(MULTIPLIERS[normalized])


def parse_number(raw: str) -> Decimal | None:
    value = raw.strip()
    if re.fullmatch(r"(?:[-—–]|NIL|N/A|NA)", value, re.I):
        return None
    negative = (
        value.startswith("(")
        and value.endswith(")")
        or value.startswith("-")
        or value.endswith("-")
    )
    value = value.strip("()-+ ").replace(",", "").replace(" ", "").lstrip("₹$€£")
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return -number if negative else number


def row(line: str) -> tuple[str, list[str]] | None:
    match = ROW.match(line)
    if not match:
        return None
    return match.group("label").strip(), [
        part.group() for part in TOKEN.finditer(match.group("values"))
    ]
