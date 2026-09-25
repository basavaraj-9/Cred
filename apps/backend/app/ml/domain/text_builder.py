import hashlib
import re
import unicodedata
from collections.abc import Sequence

from app.models.enums import FieldStatus
from app.models.extracted_field import ExtractedField

INPUT_BUILDER_VERSION = "domain_input_builder_v1"
BUSINESS_FIELDS = ("business_description", "product", "service", "operating_segment")
HEADINGS = {
    "business_description": "BUSINESS DESCRIPTION",
    "product": "PRODUCTS",
    "service": "SERVICES",
    "operating_segment": "OPERATING SEGMENTS",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).lower()).strip()


def build_text(values: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for field in BUSINESS_FIELDS:
        unique = sorted({normalize_text(item) for item in values.get(field, []) if item.strip()})
        if unique:
            lines.extend((f"{HEADINGS[field]}:", *unique))
    return "\n".join(lines)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_from_fields(fields: Sequence[ExtractedField]) -> tuple[str, list[ExtractedField]]:
    used = [
        field
        for field in fields
        if field.field_name in BUSINESS_FIELDS and field.status == FieldStatus.VERIFIED
    ]
    values: dict[str, list[str]] = {}
    for field in used:
        values.setdefault(field.field_name, []).append(field.normalized_value)
    return build_text(values), used
