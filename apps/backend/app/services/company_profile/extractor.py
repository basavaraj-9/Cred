import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.models.document_page import DocumentPage
from app.models.enums import FieldStatus, IdentityMatchStatus

EXTRACTOR_VERSION = "company_profile_extractor_v1"
EVIDENCE_LIMIT = 800
LEGAL_SUFFIX = r"(?:Private\s+Limited|Pvt\.?\s+Ltd\.?|Limited|Ltd\.?|LLP)"
LEGAL_NAME_RE = re.compile(
    rf"\b([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Za-z0-9&.'-]+){{0,6}}\s+{LEGAL_SUFFIX})\b",
    re.IGNORECASE,
)
PERIOD_RE = re.compile(
    r"\b(?:Annual\s+Report|Financial\s+Year|FY)\s*[:–—-]?\s*(20\d{2})\s*[-–—/]\s*(\d{2,4})\b",
    re.IGNORECASE,
)
YEAR_ENDED_RE = re.compile(r"\bYear\s+ended\s+(?:on\s+)?31\s+March\s+(20\d{2})\b", re.I)
WEBSITE_RE = re.compile(
    r"\b(?:https?://)?(?:www\.)[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/[^\s]*)?", re.I
)
SECTIONS = {
    "business": {
        "about us",
        "company overview",
        "corporate profile",
        "business overview",
        "our business",
        "management discussion",
        "operations",
    },
    "product": {"products", "our products", "product portfolio"},
    "service": {"services", "our services", "service portfolio"},
    "operating_segment": {"operating segments", "business segments", "segment information"},
}
EXCLUDED_IDENTITY_CONTEXT = (
    "subsidiar",
    "auditor",
    "chartered accountant",
    "customer",
    "client",
    "supplier",
    "vendor",
    "bank",
    "registrar",
    "stock exchange",
)


@dataclass(frozen=True)
class Candidate:
    field_group: str
    field_name: str
    raw_value: str
    normalized_value: str
    page: DocumentPage
    evidence_text: str
    confidence: float
    status: FieldStatus = FieldStatus.NEEDS_REVIEW


def normalize_legal_name(value: str) -> str:
    words = re.sub(r"\s+", " ", value.strip(" .,;:-"))
    return " ".join(
        word.upper()
        if (word.isupper() and len(word) <= 4) or word.upper() == "LLP"
        else word.capitalize()
        for word in words.split()
    )


def identity_key(value: str) -> str:
    name = re.sub(r"[^a-z0-9 ]", " ", value.lower())
    name = re.sub(r"\b(ltd|limited)\b", "limited", name)
    name = re.sub(r"\b(pvt|private)\b", "private", name)
    return " ".join(name.split())


def compare_identity(uploaded: str, extracted: str | None) -> IdentityMatchStatus:
    if extracted is None:
        return IdentityMatchStatus.UNAVAILABLE
    left, right = identity_key(uploaded), identity_key(extracted)
    if left == right:
        return IdentityMatchStatus.MATCHED
    left_tokens, right_tokens = set(left.split()), set(right.split())
    if (
        left_tokens
        and right_tokens
        and len(left_tokens & right_tokens) / len(left_tokens | right_tokens) >= 0.7
    ):
        return IdentityMatchStatus.POSSIBLE_MATCH
    return IdentityMatchStatus.MISMATCH


def field_status(confidence: float) -> FieldStatus:
    if confidence >= 0.85:
        return FieldStatus.VERIFIED
    if confidence >= 0.65:
        return FieldStatus.NEEDS_REVIEW
    return FieldStatus.UNAVAILABLE


def _candidate(
    group: str, name: str, raw: str, normalized: str, page: DocumentPage, line: str, score: float
) -> Candidate:
    snippet = line.strip()[:EVIDENCE_LIMIT].strip()
    return Candidate(
        group,
        name,
        raw.strip(),
        normalized.strip(),
        page,
        snippet,
        round(min(score, 0.99), 2),
        field_status(score),
    )


def _heading(line: str) -> str | None:
    cleaned = re.sub(r"[^a-z ]", "", line.lower()).strip()
    for name, headings in SECTIONS.items():
        if cleaned in headings:
            return name
    return None


def extract_candidates(pages: Sequence[DocumentPage], uploaded_name: str) -> list[Candidate]:
    candidates: list[Candidate] = []
    for page in pages:
        section: str | None = None
        subsidiary_list = False
        for line in page.text_content.splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if not line:
                continue
            heading = _heading(line)
            if heading:
                section = heading
                subsidiary_list = False
                continue
            lower = line.lower()
            if "subsidiar" in lower and (lower.endswith(":") or "following" in lower):
                subsidiary_list = True
            if not subsidiary_list and not any(word in lower for word in EXCLUDED_IDENTITY_CONTEXT):
                for match in LEGAL_NAME_RE.finditer(line):
                    raw = match.group(1).strip()
                    # Strip lead-in words that describe context rather than the name.
                    raw = re.sub(r"^(?:The|Company|Of|For|To)\s+", "", raw, flags=re.I)
                    normalized = normalize_legal_name(raw)
                    if len(normalized) > 255:
                        continue
                    score = 0.70
                    if page.page_number <= 10:
                        score += 0.04
                    if "annual report" in lower or "corporate information" in lower:
                        score += 0.14
                    if compare_identity(uploaded_name, normalized) == IdentityMatchStatus.MATCHED:
                        score += 0.04
                    candidates.append(
                        _candidate(
                            "COMPANY_IDENTITY", "legal_name", raw, normalized, page, line, score
                        )
                    )
            period = PERIOD_RE.search(line)
            if period:
                end = period.group(2)
                end_year = int(end) if len(end) == 4 else int(period.group(1)[:2] + end)
                candidates.append(
                    _candidate(
                        "REPORTING_PERIOD",
                        "reporting_period",
                        period.group(),
                        f"FY{end_year}",
                        page,
                        line,
                        0.93 if "annual report" in lower else 0.86,
                    )
                )
            else:
                ended = YEAR_ENDED_RE.search(line)
                if ended:
                    candidates.append(
                        _candidate(
                            "REPORTING_PERIOD",
                            "reporting_period",
                            ended.group(),
                            f"FY{ended.group(1)}",
                            page,
                            line,
                            0.88,
                        )
                    )
            if re.search(
                r"\b(is (?:a|an)|engaged in|manufactures|provides|operates in)\b", lower
            ) and (section == "business" or "company" in lower or "limited" in lower):
                if 30 <= len(line) <= 1000:
                    candidates.append(
                        _candidate(
                            "BUSINESS_PROFILE",
                            "business_description",
                            line,
                            line,
                            page,
                            line,
                            0.89 if section == "business" else 0.72,
                        )
                    )
            for field, label in (
                ("product", "products"),
                ("service", "services"),
                ("operating_segment", "operating segments"),
            ):
                item_match = re.match(rf"^{label}\s*:\s*(.+)$", line, re.I)
                value_text = (
                    item_match.group(1)
                    if item_match
                    else (line if section == field and len(line) <= 160 else "")
                )
                if not value_text:
                    continue
                for item in re.split(r"[,;]", value_text):
                    item = item.strip(" .:-")
                    if 3 <= len(item) <= 100 and not re.search(
                        r"\b(revenue|profit|asset|debt)\b", item, re.I
                    ):
                        candidates.append(
                            _candidate(
                                field.upper(),
                                field,
                                item,
                                item,
                                page,
                                line,
                                0.9 if item_match else 0.86,
                            )
                        )
            for field, label in (
                ("headquarters", r"(?:headquarters|headquartered at)"),
                ("registered_office", "registered office"),
                ("country", "country"),
            ):
                location_match = re.match(rf"^{label}\s*:\s*(.+)$", line, re.I)
                if location_match:
                    value = location_match.group(1).strip(" .")
                    if 2 <= len(value) <= 255:
                        candidates.append(
                            _candidate("BUSINESS_PROFILE", field, value, value, page, line, 0.91)
                        )
            website = WEBSITE_RE.search(line)
            if website:
                value = website.group().rstrip(".,;)")
                candidates.append(
                    _candidate(
                        "BUSINESS_PROFILE", "website", value, value.lower(), page, line, 0.92
                    )
                )
    return _deduplicate_and_resolve(candidates)


def _deduplicate_and_resolve(candidates: list[Candidate]) -> list[Candidate]:
    # Keep one entry per field, value, and page; retain evidence from other pages.
    unique: dict[tuple[str, str, int], Candidate] = {}
    for candidate in candidates:
        key = (
            candidate.field_name,
            identity_key(candidate.normalized_value),
            candidate.page.page_number,
        )
        if key not in unique or candidate.confidence > unique[key].confidence:
            unique[key] = candidate
    values = list(unique.values())
    legal = [item for item in values if item.field_name == "legal_name"]
    strong_names = {
        identity_key(item.normalized_value) for item in legal if item.confidence >= 0.85
    }
    if len(strong_names) > 1:
        values = [
            replace(item, status=FieldStatus.CONFLICTING)
            if item.field_name == "legal_name" and item.confidence >= 0.85
            else item
            for item in values
        ]
    return values
