from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.main import create_app
from app.models import (
    AnalysisJob,
    AuditLog,
    Company,
    Document,
    DocumentPage,
    FinancialExtractionRun,
    FinancialLineItem,
    FinancialStatement,
)
from app.models.enums import DocumentStatus, PageExtractionMethod, ParserStatus
from app.services.financial_engine import service as financial_service
from app.services.financial_engine.extractor import extract, reconcile
from app.services.financial_engine.parsing import (
    currency,
    date_periods,
    heading,
    parse_number,
    row,
    scope,
    unit,
)
from app.services.financial_engine.taxonomy import map_label, taxonomy, validate_taxonomy

INCOME = """CONSOLIDATED STATEMENT OF PROFIT AND LOSS
(₹ in Crores)
Particulars                2026      2025
Revenue from Operations   1,250     1,080
Finance Costs                34        28
Profit After Tax             92        74
Basic EPS                  7.25      6.10
Unknown levy                 12        10"""
BALANCE = """STANDALONE BALANCE SHEET
Rs. in Lakhs
Particulars             2026      2025
Trade Receivables         250       210
Total Assets            1,100       990
Total Equity              450       400"""
CASH = """CONSOLIDATED CASH FLOW STATEMENT
INR in Millions
Particulars                              2026      2025
Net Cash from Operating Activities       250       220
Net Cash from Investing Activities      (80)      (70)
Net Cash from Financing Activities       100        50"""


def page(
    text: str, number: int = 1, method: PageExtractionMethod = PageExtractionMethod.NATIVE_TEXT
) -> DocumentPage:
    return DocumentPage(
        document_id=uuid4(),
        page_number=number,
        text_content=text,
        extraction_method=method,
        parser_version="test",
        text_quality_score=1,
    )


def test_taxonomy_validation_and_synonyms() -> None:
    assert len(taxonomy()["items"]) == 42
    assert map_label("INCOME_STATEMENT", "Sales") == ("revenue_from_operations", "MONETARY")
    assert map_label("INCOME_STATEMENT", "Interest Expense") == ("finance_cost", "MONETARY")
    assert map_label("BALANCE_SHEET", "Sundry Debtors") == ("trade_receivables", "MONETARY")
    broken = {
        "version": "financial_line_items_v1",
        "items": [taxonomy()["items"][0], taxonomy()["items"][0]],
    }
    with pytest.raises(ValueError):
        validate_taxonomy(broken)


def test_period_unit_currency_and_numeric() -> None:
    assert [p.fiscal_year for p in date_periods("Particulars 31 March 2026 31 March 2025")] == [
        "FY2026",
        "FY2025",
    ]
    assert date_periods("FY 2025-26")[0].fiscal_year == "FY2026"
    assert unit("₹ in Lakhs") == ("Lakhs", "LAKH", Decimal(100000))
    assert currency("USD in Millions") == "USD"
    assert [
        parse_number(v) for v in ["1,250.45", "(125)", "125-", "-125", "0", "—", "NIL", "1O0"]
    ] == [
        Decimal("1250.45"),
        Decimal(-125),
        Decimal(-125),
        Decimal(-125),
        Decimal(0),
        None,
        None,
        None,
    ]
    assert row("Revenue from Operations   1,250   1,080") is not None
    assert heading("Statement of Financial Position") == "BALANCE_SHEET"
    assert scope("Standalone Balance Sheet") == "STANDALONE"


def test_three_statements_scopes_periods_eps_and_unmapped() -> None:
    drafts = extract([page(INCOME), page(BALANCE, 2), page(CASH, 3)])
    assert {d.statement_type for d in drafts} == {
        "INCOME_STATEMENT",
        "BALANCE_SHEET",
        "CASH_FLOW_STATEMENT",
    }
    assert [d.statement_scope for d in drafts] == ["CONSOLIDATED", "STANDALONE", "CONSOLIDATED"]
    revenue = [c for c in drafts[0].candidates if c.canonical_name == "revenue_from_operations"]
    assert [(c.period.fiscal_year, c.numeric_value, c.normalized_unit) for c in revenue] == [
        ("FY2026", Decimal(1250), "CRORE"),
        ("FY2025", Decimal(1080), "CRORE"),
    ]
    eps = [c for c in drafts[0].candidates if c.canonical_name == "eps_basic"][0]
    assert eps.measurement_type == "PER_SHARE" and eps.unit_multiplier == 1
    assert any(c.status == "UNMAPPED" for c in drafts[0].candidates)
    assert any(c.numeric_value == -80 for c in drafts[2].candidates)


def test_continuation_conflict_ocr_and_false_positive() -> None:
    first = page(
        "CONSOLIDATED BALANCE SHEET\n₹ in Crores\nParticulars 2026 2025\nTotal Assets   1,000   900"
    )
    second = page("Total Equity   400   350", 2)
    third = page(
        "CONSOLIDATED BALANCE SHEET\n₹ in Crores\n"
        "Particulars 2026 2025\nTotal Assets   1,050   900",
        3,
        PageExtractionMethod.OCR,
    )
    drafts = extract([first, second, third, page("Employee count 500. Share price 100.", 4)])
    assert drafts[0].end_page == 2
    assert len(drafts) == 2
    assert drafts[1].candidates[0].confidence < drafts[0].candidates[0].confidence
    reconcile(drafts)
    assert drafts[0].candidates[0].status == "CONFLICTING"
    assert drafts[1].candidates[0].status == "CONFLICTING"


def test_consistent_audited_note_is_secondary() -> None:
    primary = page(
        "CONSOLIDATED STATEMENT OF PROFIT AND LOSS\n₹ in Crores\nParticulars 2026\nSales   1,250"
    )
    note = page(
        "NOTES TO FINANCIAL STATEMENTS\nConsolidated\n₹ in Crores\n"
        "Particulars 2026\nRevenue from Operations   1,250",
        2,
    )
    drafts = extract([primary, note])
    assert len(drafts) == 2
    reconcile(drafts)
    assert drafts[0].candidates[0].status == "VERIFIED"
    assert drafts[1].candidates[0].source_priority == 2
    assert drafts[1].candidates[0].status == "NEEDS_REVIEW"


def test_equal_amounts_in_different_units_do_not_conflict() -> None:
    primary = page(
        "CONSOLIDATED BALANCE SHEET\nINR in Crores\nParticulars 2026\nTotal Assets   1,250"
    )
    note = page(
        "NOTES TO FINANCIAL STATEMENTS\nConsolidated\nINR in Lakhs\n"
        "Particulars 2026\nTotal Assets   125,000",
        2,
    )
    drafts = extract([primary, note])
    reconcile(drafts)
    assert len(drafts) == 2
    assert all(item.status != "CONFLICTING" for draft in drafts for item in draft.candidates)


@pytest.fixture
def context(database_engine: Engine, test_url: str) -> Iterator[tuple[TestClient, Connection]]:
    connection = database_engine.connect()
    outer = connection.begin()
    app = create_app(
        Settings(_env_file=None, app_env="test", database_url=test_url, ocr_enabled=False)
    )

    def test_db() -> Iterator[Session]:
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, connection
    outer.rollback()
    connection.close()


def make_document(connection: Connection, texts: list[str], parsed: bool = True) -> UUID:
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        company = Company(legal_name="Example Limited")
        session.add(company)
        session.flush()
        job = AnalysisJob(company_id=company.id)
        session.add(job)
        session.flush()
        document = Document(
            company_id=company.id,
            analysis_job_id=job.id,
            original_filename="test.pdf",
            status=DocumentStatus.UPLOADED,
            parser_status=ParserStatus.PARSED if parsed else ParserStatus.NOT_STARTED,
            sha256_hash=uuid4().hex,
        )
        session.add(document)
        session.flush()
        for number, text in enumerate(texts, 1):
            session.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=number,
                    text_content=text,
                    extraction_method=PageExtractionMethod.NATIVE_TEXT,
                    parser_version="test",
                    text_quality_score=1,
                )
            )
        session.commit()
        return document.id


def test_api_idempotency_evidence_and_immutability(context: tuple[TestClient, Connection]) -> None:
    client, connection = context
    document_id = make_document(connection, [INCOME, BALANCE, CASH])
    with Session(connection) as session:
        original = [
            (p.id, p.text_content)
            for p in session.scalars(
                select(DocumentPage).where(DocumentPage.document_id == document_id)
            )
        ]
    path = f"/api/v1/documents/{document_id}/financial-statements"
    response = client.post(path + "/extract")
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["statements_found"] == 6
    assert summary["line_items_extracted"] == 22
    assert summary["unmapped_items"] == 2
    assert client.post(path + "/extract").json() == summary
    statements = client.get(path).json()
    assert len(statements) == 6
    statement = next(
        s
        for s in statements
        if s["statement_type"] == "INCOME_STATEMENT" and s["fiscal_year"] == "FY2026"
    )
    items = client.get(f"/api/v1/financial-statements/{statement['id']}/line-items").json()
    revenue = next(i for i in items if i["canonical_name"] == "revenue_from_operations")
    assert revenue["numeric_value"] == "1250.000000"
    evidence = client.get(f"/api/v1/financial-line-items/{revenue['id']}").json()
    assert evidence["evidence_text"].startswith("Revenue from Operations")
    assert evidence["statement_scope"] == "CONSOLIDATED"
    with Session(connection) as session:
        assert session.scalar(select(func.count()).select_from(FinancialExtractionRun)) == 1
        assert session.scalar(select(func.count()).select_from(FinancialStatement)) == 6
        assert session.scalar(select(func.count()).select_from(FinancialLineItem)) == 22
        assert [
            (p.id, p.text_content)
            for p in session.scalars(
                select(DocumentPage).where(DocumentPage.document_id == document_id)
            )
        ] == original
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "FINANCIAL_EXTRACTION_STARTED")
            )
            == 1
        )


def test_api_preconditions(context: tuple[TestClient, Connection]) -> None:
    client, connection = context
    document_id = make_document(connection, [INCOME], parsed=False)
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-statements/extract").json()[
            "error"
        ]["code"]
        == "DOCUMENT_NOT_PARSED"
    )
    assert client.get(f"/api/v1/documents/{uuid4()}/financial-statements").status_code == 404


def test_extraction_rolls_back_all_rows_on_write_failure(
    context: tuple[TestClient, Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, connection = context
    document_id = make_document(connection, [INCOME])
    original_write = financial_service.write_audit_log

    def fail_on_statement(*args: object, **kwargs: object) -> object:
        if kwargs.get("action") == "FINANCIAL_STATEMENT_FOUND":
            raise RuntimeError("simulated persistence failure")
        return original_write(*args, **kwargs)

    monkeypatch.setattr(financial_service, "write_audit_log", fail_on_statement)
    response = client.post(f"/api/v1/documents/{document_id}/financial-statements/extract")
    assert response.status_code == 500
    with Session(connection) as session:
        assert session.scalar(select(func.count()).select_from(FinancialExtractionRun)) == 0
        assert session.scalar(select(func.count()).select_from(FinancialStatement)) == 0
        assert session.scalar(select(func.count()).select_from(FinancialLineItem)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "FINANCIAL_EXTRACTION_STARTED")
            )
            == 0
        )


def test_upload_parse_profile_financial_smoke(
    database_engine: Engine, test_url: str, tmp_path: Path
) -> None:
    pdf = fitz.open()
    sheet = pdf.new_page()
    report = """Example Limited Annual Report FY 2025-26
Example Limited is a manufacturer of industrial equipment.
CONSOLIDATED STATEMENT OF PROFIT AND LOSS
INR in Crores
Particulars                2026      2025
Revenue from Operations   1,250     1,080
Profit After Tax             92        74"""
    sheet.insert_text((45, 45), report, fontname="cour", fontsize=10)
    source = pdf.tobytes()
    pdf.close()
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

    def test_db() -> Iterator[Session]:
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            uploaded = client.post(
                "/api/v1/documents/upload",
                data={"company_legal_name": "Example Limited"},
                files={"file": ("annual.pdf", source, "application/pdf")},
            )
            assert uploaded.status_code == 201, uploaded.text
            document_id = uploaded.json()["document"]["id"]
            stored = tmp_path / "uploads" / f"{UUID(document_id).hex}.pdf"
            assert stored.read_bytes() == source
            parsed = client.post(f"/api/v1/documents/{document_id}/parse")
            assert parsed.status_code == 200, parsed.text
            assert parsed.json()["parser_status"] == "PARSED"
            profile = client.post(f"/api/v1/documents/{document_id}/company-profile/extract")
            assert profile.status_code == 200, profile.text
            extracted = client.post(f"/api/v1/documents/{document_id}/financial-statements/extract")
            assert extracted.status_code == 200, extracted.text
            assert extracted.json()["line_items_extracted"] >= 4
            listed = client.get(f"/api/v1/documents/{document_id}/financial-statements").json()
            assert len(listed) == 2
            assert stored.read_bytes() == source
    finally:
        outer.rollback()
        connection.close()
