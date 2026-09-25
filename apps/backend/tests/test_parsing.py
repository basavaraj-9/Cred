import hashlib
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.main import create_app
from app.models import AuditLog, Document, DocumentPage
from app.models.enums import AnalysisStage, PageExtractionMethod
from app.services.document_intelligence.ocr import TesseractOCR, get_ocr_provider
from app.services.document_intelligence.pdf_parser import PARSER_VERSION
from app.services.document_intelligence.quality import evaluate_text, normalize_text

NATIVE_TEXT = (
    "ABC Electrical Ltd annual report 2025. Revenue was INR 1,250 crore and operating "
    "profit was INR 180 crore. The company manufactures electrical equipment in India."
)
OCR_TEXT = (
    "Scanned annual report page. Revenue was INR 1,250 crore. The company operates "
    "through several manufacturing facilities and sells electrical equipment."
)


class FakeOCR:
    def __init__(self, text: str = OCR_TEXT, available: bool = True, fail: bool = False) -> None:
        self.text = text
        self.available_state = available
        self.fail = fail
        self.calls = 0

    def available(self) -> bool:
        return self.available_state

    def extract_text(self, image_png: bytes) -> str:
        self.calls += 1
        assert image_png.startswith(b"\x89PNG")
        if self.fail:
            raise RuntimeError("injected OCR failure")
        return self.text


def make_pdf(*kinds: str) -> bytes:
    with fitz.open() as pdf:
        for kind in kinds:
            page = pdf.new_page()
            if kind == "native":
                page.insert_text((72, 72), NATIVE_TEXT, fontsize=11)
            elif kind == "short":
                page.insert_text((72, 72), "Annual Report", fontsize=14)
            elif kind == "garbled":
                page.insert_text((72, 72), "!!!!!!!!!!!!!", fontsize=11)
            elif kind == "scanned":
                with fitz.open() as source:
                    source_page = source.new_page(width=600, height=400)
                    source_page.insert_text((30, 80), OCR_TEXT, fontsize=14)
                    png = source_page.get_pixmap().tobytes("png")
                page.insert_image(page.rect, stream=png)
            elif kind != "blank":
                raise ValueError(kind)
        return pdf.tobytes()


def make_encrypted_pdf() -> bytes:
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), NATIVE_TEXT)
        return pdf.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="test-owner",
            user_pw="test-user",
        )


@dataclass
class ParseContext:
    client: TestClient
    connection: Connection
    storage_root: Path
    ocr: FakeOCR

    def upload(self, content: bytes, name: str | None = None) -> tuple[str, Path]:
        response = self.client.post(
            "/api/v1/documents/upload",
            data={"company_legal_name": name or f"Parse Test {uuid4()}"},
            files={"file": ("report.pdf", content, "application/pdf")},
        )
        assert response.status_code == 201, response.text
        document_id = response.json()["document"]["id"]
        return document_id, self.storage_root / "uploads" / f"{UUID(document_id).hex}.pdf"

    def parse(self, document_id: str):
        return self.client.post(f"/api/v1/documents/{document_id}/parse")

    def page_rows(self, document_id: str) -> list[DocumentPage]:
        with Session(self.connection, join_transaction_mode="create_savepoint") as session:
            return session.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == UUID(document_id))
                .order_by(DocumentPage.page_number)
            ).all()

    def events(self, document_id: str) -> list[str]:
        with Session(self.connection, join_transaction_mode="create_savepoint") as session:
            return list(
                session.scalars(
                    select(AuditLog.event_type)
                    .where(
                        AuditLog.entity_type == "document", AuditLog.entity_id == UUID(document_id)
                    )
                    .order_by(AuditLog.created_at)
                ).all()
            )


@pytest.fixture
def parse_context(database_engine: Engine, test_url: str, tmp_path: Path) -> Iterator[ParseContext]:
    connection = database_engine.connect()
    outer = connection.begin()
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=test_url,
        local_storage_path=tmp_path,
        ocr_enabled=False,
    )
    app = create_app(settings)
    fake = FakeOCR()

    def test_db() -> Iterator[Session]:
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_ocr_provider] = lambda: fake
    with TestClient(app, raise_server_exceptions=False) as client:
        yield ParseContext(client, connection, tmp_path, fake)
    outer.rollback()
    connection.close()


def test_parse_native_text_pdf_persists_page_and_metadata(parse_context: ParseContext) -> None:
    content = make_pdf("native")
    document_id, path = parse_context.upload(content)
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    response = parse_context.parse(document_id)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary == {
        "document_id": document_id,
        "parser_status": "PARSED",
        "page_count": 1,
        "native_text_pages": 1,
        "ocr_pages": 0,
        "blank_pages": 0,
        "failed_pages": 0,
        "extraction_method": "NATIVE_TEXT",
        "parser_version": PARSER_VERSION,
    }
    assert parse_context.ocr.calls == 0
    pages = parse_context.page_rows(document_id)
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].extraction_method == PageExtractionMethod.NATIVE_TEXT
    assert "Revenue was INR" in pages[0].text_content
    assert pages[0].parser_version == PARSER_VERSION
    assert 0 <= pages[0].text_quality_score <= 1
    metadata = parse_context.client.get(f"/api/v1/documents/{document_id}").json()
    assert metadata["status"] == "UPLOADED"
    assert metadata["parser_status"] == "PARSED"
    assert metadata["page_count"] == 1
    assert metadata["parser_version"] == PARSER_VERSION
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
    assert "DOCUMENT_PARSE_STARTED" in parse_context.events(document_id)
    assert "DOCUMENT_PARSE_COMPLETED" in parse_context.events(document_id)
    with Session(parse_context.connection, join_transaction_mode="create_savepoint") as session:
        document = session.get(Document, UUID(document_id))
        assert document is not None
        assert document.analysis_job.current_stage == AnalysisStage.DOCUMENT_PARSING


def test_multipage_numbering_and_page_endpoints(parse_context: ParseContext) -> None:
    document_id, _ = parse_context.upload(
        make_pdf("native", "native", "native", "native", "native")
    )
    summary = parse_context.parse(document_id).json()
    assert summary["page_count"] == 5
    listing = parse_context.client.get(f"/api/v1/documents/{document_id}/pages")
    assert listing.status_code == 200
    assert [page["page_number"] for page in listing.json()] == [1, 2, 3, 4, 5]
    assert "text_content" not in listing.json()[0]
    detail = parse_context.client.get(f"/api/v1/documents/{document_id}/pages/2")
    assert detail.status_code == 200
    assert detail.json()["document_id"] == document_id
    assert "ABC Electrical" in detail.json()["text_content"]
    assert parse_context.client.get(f"/api/v1/documents/{document_id}/pages/6").status_code == 404


def test_blank_page_is_not_sent_to_ocr(parse_context: ParseContext) -> None:
    document_id, _ = parse_context.upload(make_pdf("blank"))
    summary = parse_context.parse(document_id).json()
    assert summary["parser_status"] == "PARSED"
    assert summary["blank_pages"] == 1
    assert summary["extraction_method"] == "BLANK"
    page = parse_context.page_rows(document_id)[0]
    assert page.extraction_method == PageExtractionMethod.BLANK
    assert page.text_content == ""
    assert page.ocr_required is False
    assert parse_context.ocr.calls == 0


def test_scanned_page_uses_ocr_fallback(parse_context: ParseContext) -> None:
    document_id, _ = parse_context.upload(make_pdf("scanned"))
    summary = parse_context.parse(document_id).json()
    assert summary["parser_status"] == "PARSED"
    assert summary["ocr_pages"] == 1
    assert summary["extraction_method"] == "OCR"
    page = parse_context.page_rows(document_id)[0]
    assert page.extraction_method == PageExtractionMethod.OCR
    assert page.ocr_required and page.ocr_attempted and page.ocr_succeeded
    assert "Scanned annual report" in page.text_content
    assert parse_context.ocr.calls == 1
    assert parse_context.events(document_id).count("OCR_FALLBACK_USED") == 1


def test_hybrid_pdf_reports_hybrid_method(parse_context: ParseContext) -> None:
    document_id, _ = parse_context.upload(make_pdf("native", "scanned", "blank"))
    summary = parse_context.parse(document_id).json()
    assert summary["page_count"] == 3
    assert summary["native_text_pages"] == 1
    assert summary["ocr_pages"] == 1
    assert summary["blank_pages"] == 1
    assert summary["extraction_method"] == "HYBRID"


def test_ocr_failure_keeps_partial_document_without_fabricated_text(
    parse_context: ParseContext,
) -> None:
    parse_context.ocr.fail = True
    document_id, _ = parse_context.upload(make_pdf("native", "scanned"))
    summary = parse_context.parse(document_id).json()
    assert summary["parser_status"] == "PARTIAL"
    assert summary["failed_pages"] == 1
    failed = parse_context.page_rows(document_id)[1]
    assert failed.extraction_method == PageExtractionMethod.FAILED
    assert failed.ocr_required and failed.ocr_attempted and not failed.ocr_succeeded
    assert failed.text_content == ""
    assert failed.error_code == "OCR_ERROR"
    assert "DOCUMENT_PARSE_PARTIAL" in parse_context.events(document_id)


def test_ocr_unavailable_marks_page_for_review(parse_context: ParseContext) -> None:
    parse_context.ocr.available_state = False
    document_id, _ = parse_context.upload(make_pdf("scanned"))
    summary = parse_context.parse(document_id).json()
    assert summary["parser_status"] == "REVIEW_REQUIRED"
    assert summary["failed_pages"] == 1
    page = parse_context.page_rows(document_id)[0]
    assert page.error_code == "OCR_UNAVAILABLE"
    assert page.ocr_required and not page.ocr_attempted
    assert page.text_content == ""


def test_short_title_is_native_and_low_quality_requires_ocr(parse_context: ParseContext) -> None:
    document_id, _ = parse_context.upload(make_pdf("short", "garbled"))
    summary = parse_context.parse(document_id).json()
    assert summary["native_text_pages"] == 1
    assert summary["ocr_pages"] == 1
    assert parse_context.ocr.calls == 1


def test_corrupted_pdf_marks_parser_failed_and_preserves_source(
    parse_context: ParseContext,
) -> None:
    content = b"%PDF-this is not a real PDF"
    document_id, path = parse_context.upload(content)
    response = parse_context.parse(document_id)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PDF_PARSE_ERROR"
    metadata = parse_context.client.get(f"/api/v1/documents/{document_id}").json()
    assert metadata["status"] == "UPLOADED"
    assert metadata["parser_status"] == "FAILED"
    assert metadata["parse_error_code"] == "PDF_PARSE_ERROR"
    assert path.read_bytes() == content
    assert "DOCUMENT_PARSE_FAILED" in parse_context.events(document_id)


def test_encrypted_pdf_handled_without_guessing_password(parse_context: ParseContext) -> None:
    document_id, path = parse_context.upload(make_encrypted_pdf())
    response = parse_context.parse(document_id)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PDF_ENCRYPTED"
    assert (
        parse_context.client.get(f"/api/v1/documents/{document_id}").json()["parser_status"]
        == "FAILED"
    )
    assert path.exists()


def test_unknown_document_and_missing_file(parse_context: ParseContext) -> None:
    assert parse_context.parse(str(uuid4())).status_code == 404
    document_id, path = parse_context.upload(make_pdf("native"))
    path.unlink()
    response = parse_context.parse(document_id)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SOURCE_FILE_MISSING"
    assert (
        parse_context.client.get(f"/api/v1/documents/{document_id}").json()["parser_status"]
        == "FAILED"
    )


def test_parse_is_idempotent_without_duplicate_pages_or_audit(parse_context: ParseContext) -> None:
    document_id, _ = parse_context.upload(make_pdf("native", "scanned"))
    first = parse_context.parse(document_id)
    before_events = parse_context.events(document_id)
    second = parse_context.parse(document_id)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(parse_context.page_rows(document_id)) == 2
    assert parse_context.events(document_id) == before_events
    assert parse_context.ocr.calls == 1


def test_document_page_unique_constraint(parse_context: ParseContext) -> None:
    document_id, _ = parse_context.upload(make_pdf("native"))
    assert parse_context.parse(document_id).status_code == 200
    with Session(parse_context.connection, join_transaction_mode="create_savepoint") as session:
        session.add(
            DocumentPage(
                document_id=UUID(document_id),
                page_number=1,
                extraction_method=PageExtractionMethod.BLANK,
                text_content="",
                parser_version=PARSER_VERSION,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_quality_evaluator_handles_financial_and_garbage_text() -> None:
    settings = Settings(_env_file=None, app_env="test")
    normal = evaluate_text(NATIVE_TEXT, settings)
    financial = evaluate_text("Revenue 1250.45 EBITDA 180.23 FY2025 2024 2023 2022 2021", settings)
    garbage = evaluate_text("!!!!!!!!!!!!\ufffd\ufffd\ufffd", settings)
    blank = evaluate_text("   \n", settings)
    ocr_like = evaluate_text(OCR_TEXT, settings)
    assert normal.score >= 0.68
    assert financial.score >= 0.68
    assert ocr_like.score >= 0.68
    assert garbage.score < 0.68
    assert blank.score == 0
    assert all(0 <= item.score <= 1 for item in (normal, financial, garbage, blank, ocr_like))
    assert normalize_text("A\r\nB\x00C") == "A\nBC"


def test_page_and_document_constraints_exist(database_engine: Engine) -> None:
    from sqlalchemy import inspect

    inspector = inspect(database_engine)
    assert "document_pages" in inspector.get_table_names()
    indexes = {index["name"] for index in inspector.get_indexes("document_pages")}
    assert "ix_document_pages_document_id" in indexes
    uniques = {
        constraint["name"] for constraint in inspector.get_unique_constraints("document_pages")
    }
    assert "uq_document_pages_document_page" in uniques


def test_health_and_status_report_ocr_truthfully(parse_context: ParseContext) -> None:
    health = parse_context.client.get("/api/v1/health").json()
    status = parse_context.client.get("/api/v1/status").json()
    assert health["dependencies"]["ocr"] == "disabled"
    assert health["status"] == "healthy"
    assert status["components"]["pdf_parsing"] == "ready"
    assert status["components"]["page_level_extraction"] == "ready"
    assert status["components"]["ocr_fallback"] == "unavailable"
    assert status["components"]["document_intelligence"] == "foundation_ready"
    assert status["development_stage"]["day"] == 20


def test_real_ocr_if_tesseract_is_installed(parse_context: ParseContext) -> None:
    if shutil.which("tesseract") is None:
        pytest.skip("Tesseract executable is not installed")
    settings = Settings(_env_file=None, app_env="test", ocr_enabled=True)
    provider = TesseractOCR(settings)
    assert provider.available()
    document_id, _ = parse_context.upload(make_pdf("scanned"))
    image_doc = fitz.open(make_pdf("scanned"))
    with image_doc:
        png = image_doc[0].get_pixmap().tobytes("png")
    assert isinstance(provider.extract_text(png), str)
    assert parse_context.parse(document_id).status_code == 200
