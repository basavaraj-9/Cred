import logging
from dataclasses import dataclass
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from app.core.config import Settings
from app.models.enums import DocumentExtractionMethod, PageExtractionMethod, ParserStatus
from app.services.document_intelligence.ocr import OCRFailure, OCRProvider
from app.services.document_intelligence.quality import (
    evaluate_text,
    native_text_is_usable,
    normalize_text,
)

PARSER_VERSION = "pdf_parser_v1"
logger = logging.getLogger(__name__)


class PDFParseError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    extraction_method: PageExtractionMethod
    text_content: str
    character_count: int
    word_count: int
    text_quality_score: float
    ocr_required: bool
    ocr_attempted: bool
    ocr_succeeded: bool
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ParsedDocument:
    page_count: int
    pages: list[ParsedPage]
    parser_status: ParserStatus
    extraction_method: DocumentExtractionMethod
    native_text_pages: int
    ocr_pages: int
    blank_pages: int
    failed_pages: int


def _image_coverage(page: fitz.Page) -> float:
    page_area = max(1.0, page.rect.get_area())
    coverage = 0.0
    for image in page.get_images(full=True):
        for rect in page.get_image_rects(image[0]):
            coverage += rect.get_area() / page_area
    return min(1.0, coverage)


def _has_meaningful_drawings(page: fitz.Page) -> bool:
    drawings = page.get_drawings()
    if len(drawings) >= 5:
        return True
    page_area = max(1.0, page.rect.get_area())
    return any(drawing["rect"].get_area() / page_area >= 0.05 for drawing in drawings)


def _page_result(
    page_number: int,
    method: PageExtractionMethod,
    text: str,
    settings: Settings,
    *,
    ocr_required: bool = False,
    ocr_attempted: bool = False,
    ocr_succeeded: bool = False,
    error_code: str | None = None,
    error_message: str | None = None,
) -> ParsedPage:
    quality = evaluate_text(text, settings)
    return ParsedPage(
        page_number,
        method,
        text,
        quality.character_count,
        quality.word_count,
        quality.score,
        ocr_required,
        ocr_attempted,
        ocr_succeeded,
        error_code,
        error_message,
    )


def _parse_page(
    page: fitz.Page, page_number: int, ocr: OCRProvider, settings: Settings
) -> ParsedPage:
    try:
        native = normalize_text(page.get_text("text", sort=False))
        coverage = _image_coverage(page)
        drawings = _has_meaningful_drawings(page)
    except Exception:
        logger.warning("Native page extraction failed on page %s", page_number)
        native = ""
        coverage = 1.0
        drawings = True

    quality = evaluate_text(native, settings)
    if not native.strip() and coverage < 0.05 and not drawings:
        return _page_result(page_number, PageExtractionMethod.BLANK, "", settings)
    if native_text_is_usable(quality, settings, coverage):
        return _page_result(page_number, PageExtractionMethod.NATIVE_TEXT, native, settings)
    if not ocr.available():
        return _page_result(
            page_number,
            PageExtractionMethod.FAILED,
            native,
            settings,
            ocr_required=True,
            error_code="OCR_UNAVAILABLE",
            error_message="OCR is required but the provider is unavailable",
        )
    try:
        scale = settings.ocr_dpi / 72
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image_png = pixmap.tobytes("png")
        del pixmap
        ocr_text = normalize_text(ocr.extract_text(image_png))
        ocr_quality = evaluate_text(ocr_text, settings)
        if not native_text_is_usable(ocr_quality, settings, 0.0):
            return _page_result(
                page_number,
                PageExtractionMethod.FAILED,
                native,
                settings,
                ocr_required=True,
                ocr_attempted=True,
                error_code="OCR_LOW_QUALITY",
                error_message="OCR returned no usable text",
            )
        return _page_result(
            page_number,
            PageExtractionMethod.OCR,
            ocr_text,
            settings,
            ocr_required=True,
            ocr_attempted=True,
            ocr_succeeded=True,
        )
    except (OCRFailure, RuntimeError, ValueError) as exc:
        logger.warning("OCR failed on page %s: %s", page_number, type(exc).__name__)
        return _page_result(
            page_number,
            PageExtractionMethod.FAILED,
            native,
            settings,
            ocr_required=True,
            ocr_attempted=True,
            error_code="OCR_ERROR",
            error_message="OCR could not extract this page",
        )


def _summarize(pages: list[ParsedPage]) -> ParsedDocument:
    counts = {method: 0 for method in PageExtractionMethod}
    for page in pages:
        counts[page.extraction_method] += 1
    native = counts[PageExtractionMethod.NATIVE_TEXT]
    ocr = counts[PageExtractionMethod.OCR]
    blank = counts[PageExtractionMethod.BLANK]
    failed = counts[PageExtractionMethod.FAILED]
    if failed == 0:
        status = ParserStatus.PARSED
    elif native + ocr + blank > 0:
        status = ParserStatus.PARTIAL
    else:
        status = ParserStatus.REVIEW_REQUIRED
    if native and ocr:
        method = DocumentExtractionMethod.HYBRID
    elif ocr:
        method = DocumentExtractionMethod.OCR
    elif native:
        method = DocumentExtractionMethod.NATIVE_TEXT
    elif blank and not failed:
        method = DocumentExtractionMethod.BLANK
    else:
        method = DocumentExtractionMethod.FAILED
    return ParsedDocument(len(pages), pages, status, method, native, ocr, blank, failed)


def parse_pdf(path: Path, ocr: OCRProvider, settings: Settings) -> ParsedDocument:
    try:
        document = fitz.open(path)
    except (fitz.FileDataError, fitz.EmptyFileError, RuntimeError) as exc:
        raise PDFParseError("PDF_PARSE_ERROR", "The stored PDF could not be opened") from exc
    with document:
        if document.needs_pass or document.is_encrypted:
            raise PDFParseError(
                "PDF_ENCRYPTED", "This PDF is password-protected and cannot be parsed"
            )
        if document.page_count < 1:
            raise PDFParseError("PDF_PARSE_ERROR", "The stored PDF contains no pages")
        pages = []
        for index in range(document.page_count):
            try:
                pages.append(_parse_page(document.load_page(index), index + 1, ocr, settings))
            except Exception:
                logger.exception("Page processing failed on page %s", index + 1)
                pages.append(
                    _page_result(
                        index + 1,
                        PageExtractionMethod.FAILED,
                        "",
                        settings,
                        error_code="PAGE_PARSE_ERROR",
                        error_message="This page could not be parsed",
                    )
                )
        return _summarize(pages)
