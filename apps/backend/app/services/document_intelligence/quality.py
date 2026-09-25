import re
from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True)
class TextQuality:
    score: float
    character_count: int
    word_count: int
    alphanumeric_ratio: float
    non_whitespace_count: int


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", normalized)


def evaluate_text(text: str, settings: Settings) -> TextQuality:
    count = len(text)
    non_whitespace = [char for char in text if not char.isspace()]
    nonspace_count = len(non_whitespace)
    words = re.findall(r"\b\w+\b", text, flags=re.UNICODE)
    if count == 0 or nonspace_count == 0:
        return TextQuality(0.0, count, len(words), 0.0, nonspace_count)
    alnum_ratio = sum(char.isalnum() for char in non_whitespace) / nonspace_count
    printable_ratio = sum(char.isprintable() or char in "\n\t" for char in text) / count
    length_score = min(1.0, nonspace_count / settings.text_quality_min_characters)
    word_score = min(1.0, len(words) / 8)
    replacement_ratio = text.count("\ufffd") / nonspace_count
    repeated_runs = sum(len(match.group()) for match in re.finditer(r"(.)\1{4,}", text))
    repeated_ratio = repeated_runs / nonspace_count
    score = (
        0.35 * alnum_ratio
        + 0.30 * printable_ratio
        + 0.20 * word_score
        + 0.15 * length_score
        - 0.50 * replacement_ratio
        - 0.35 * repeated_ratio
    )
    return TextQuality(
        round(max(0.0, min(1.0, score)), 4), count, len(words), alnum_ratio, nonspace_count
    )


def native_text_is_usable(quality: TextQuality, settings: Settings, image_coverage: float) -> bool:
    if quality.alphanumeric_ratio < settings.text_quality_min_alphanumeric_ratio:
        return False
    if quality.score < 0.68:
        return False
    if quality.non_whitespace_count >= settings.text_quality_min_characters:
        return True
    return quality.word_count >= 1 and image_coverage < 0.15
