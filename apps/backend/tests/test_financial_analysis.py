from collections.abc import Iterator

# ruff: noqa: E501
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.main import create_app
from app.models import AnalysisJob, AuditLog, Company, Document, DocumentPage
from app.models.enums import (
    DocumentStatus,
    FinancialScope,
    NormalizationStatus,
    PageExtractionMethod,
    ParserStatus,
    RatioStatus,
    ValueOrigin,
)
from app.models.financial import FinancialLineItem
from app.models.financial_analysis import (
    FinancialAnalysisRun,
    FinancialRatio,
    FinancialRatioInput,
    FinancialValidationIssue,
    NormalizedFinancialValue,
)
from app.services.financial_engine import analysis_service
from app.services.financial_engine.analysis_service import _calculate_ratio
from app.services.financial_engine.normalization import normalize_line_item
from app.services.financial_engine.ratio_definitions import ratio_definitions

INCOME = """CONSOLIDATED STATEMENT OF PROFIT AND LOSS
INR in Crores
Particulars                2026      2025
Revenue from Operations   1,250     1,080
EBITDA                       185       160
EBIT                         150       130
Finance Costs                 34        30
Profit Before Tax             126       108
Tax Expense                    34        30
Profit After Tax               92        78"""

BALANCE = """CONSOLIDATED BALANCE SHEET
INR in Lakhs
Particulars                2026      2025
Inventory                  10,000     9,000
Total Current Assets       50,000    45,000
Total Assets              190,000   170,000
Short Term Borrowings      10,000     9,000
Long Term Borrowings       21,000    20,000
Total Current Liabilities  30,000    28,000
Total Liabilities         126,000   113,000
Total Equity               64,000    57,000"""

CASH = """CONSOLIDATED CASH FLOW STATEMENT
INR in Millions
Particulars                              2026      2025
Net Cash from Operating Activities      1,500     1,300
Net Change in Cash and Cash Equivalents    300       200
Cash and Cash Equivalents at Beginning of Year  500       400
Cash and Cash Equivalents at End of Year        800       600"""


@pytest.fixture
def analysis_context(
    database_engine: Engine, test_url: str
) -> Iterator[tuple[TestClient, Connection, UUID]]:
    connection = database_engine.connect()
    outer = connection.begin()
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        company = Company(legal_name="Analysis Limited")
        session.add(company)
        session.flush()
        job = AnalysisJob(company_id=company.id)
        session.add(job)
        session.flush()
        document = Document(
            company_id=company.id,
            analysis_job_id=job.id,
            original_filename="analysis.pdf",
            status=DocumentStatus.UPLOADED,
            parser_status=ParserStatus.PARSED,
            sha256_hash=uuid4().hex,
        )
        session.add(document)
        session.flush()
        for number, text in enumerate((INCOME, BALANCE, CASH), 1):
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
        document_id = document.id
    app = create_app(
        Settings(_env_file=None, app_env="test", database_url=test_url, ocr_enabled=False)
    )

    def test_db() -> Iterator[Session]:
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, connection, document_id
    outer.rollback()
    connection.close()


def test_ratio_taxonomy_is_versioned_and_complete() -> None:
    definitions = ratio_definitions()
    assert len(definitions) == 13
    assert {definition["name"] for definition in definitions} >= {
        "current_ratio",
        "quick_ratio",
        "debt_to_equity",
        "debt_to_assets",
        "interest_coverage",
        "debt_to_ebitda",
        "ebitda_margin",
        "ebit_margin",
        "net_profit_margin",
        "return_on_assets",
        "return_on_equity",
        "operating_cash_flow_to_debt",
        "asset_turnover",
    }


def test_normalization_scales_only_monetary_values() -> None:
    from app.models.financial import FinancialLineItem

    money = FinancialLineItem(
        numeric_value=Decimal("1250"),
        measurement_type="MONETARY",
        unit_multiplier=Decimal("10000000"),
        currency="INR",
        status="VERIFIED",
    )
    eps = FinancialLineItem(
        numeric_value=Decimal("7.25"),
        measurement_type="PER_SHARE",
        unit_multiplier=Decimal("10000000"),
        currency="INR",
        status="VERIFIED",
    )
    assert normalize_line_item(money)[0] == Decimal("12500000000")
    assert normalize_line_item(eps)[0] == Decimal("7.25")


def analytical_value(name: str, amount: str, *, currency: str = "INR") -> NormalizedFinancialValue:
    return NormalizedFinancialValue(
        run_id=uuid4(),
        analysis_job_id=uuid4(),
        company_id=uuid4(),
        document_id=uuid4(),
        canonical_name=name,
        statement_type="BALANCE_SHEET",
        statement_scope=FinancialScope.CONSOLIDATED,
        fiscal_year="FY2026",
        measurement_type="MONETARY",
        normalized_value=Decimal(amount),
        normalized_currency=currency,
        canonical_unit="BASE_CURRENCY",
        unit_multiplier=1,
        normalization_status=NormalizationStatus.NORMALIZED,
        normalization_confidence=0.9,
        value_origin=ValueOrigin.EXTRACTED,
    )


def test_ratio_zero_negative_and_currency_mismatch_are_explicit() -> None:
    definition = next(item for item in ratio_definitions() if item["name"] == "debt_to_equity")
    debt = analytical_value("total_debt", "100")
    zero = analytical_value("total_equity", "0")
    result = _calculate_ratio(definition, {"total_debt": debt, "total_equity": zero}, {})
    assert (
        result[0] is None
        and result[1] == RatioStatus.UNAVAILABLE
        and result[-1] == "ZERO_DENOMINATOR"
    )
    negative = analytical_value("total_equity", "-20")
    result = _calculate_ratio(definition, {"total_debt": debt, "total_equity": negative}, {})
    assert result[1] == RatioStatus.NOT_MEANINGFUL and result[-1] == "NEGATIVE_DENOMINATOR"
    usd = analytical_value("total_debt", "100", currency="USD")
    result = _calculate_ratio(
        definition, {"total_debt": usd, "total_equity": analytical_value("total_equity", "50")}, {}
    )
    assert result[0] is None and result[-1] == "CURRENCY_MISMATCH"


def test_analysis_ratios_validation_lineage_and_idempotency(
    analysis_context: tuple[TestClient, Connection, UUID],
) -> None:
    client, connection, document_id = analysis_context
    extract = client.post(f"/api/v1/documents/{document_id}/financial-statements/extract")
    assert extract.status_code == 200, extract.text
    before_pages: list[tuple[UUID, str]]
    with Session(connection) as session:
        before_pages = [
            (page.id, page.text_content)
            for page in session.scalars(
                select(DocumentPage).where(DocumentPage.document_id == document_id)
            )
        ]
    response = client.post(f"/api/v1/documents/{document_id}/financial-analysis")
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["normalized_values"] >= 20
    assert summary["derived_values"] == 4  # revenue and total debt for both years
    assert summary["completeness_score"] == 1
    assert summary["ratios_calculated"] == 26
    assert client.post(f"/api/v1/documents/{document_id}/financial-analysis").json() == summary
    validation = client.get(f"/api/v1/documents/{document_id}/financial-validation").json()
    revenue = next(
        value
        for value in validation["normalized_values"]
        if value["canonical_name"] == "revenue" and value["fiscal_year"] == "FY2026"
    )
    debt = next(
        value
        for value in validation["normalized_values"]
        if value["canonical_name"] == "total_debt" and value["fiscal_year"] == "FY2026"
    )
    assert Decimal(revenue["normalized_value"]) == Decimal("12500000000")
    assert Decimal(debt["normalized_value"]) == Decimal("3100000000")
    assert debt["origin"] == "DERIVED" and len(debt["input_value_ids"]) == 2
    accounting = next(
        issue
        for issue in validation["issues"]
        if issue["issue_type"] == "ACCOUNTING_EQUATION_MISMATCH"
        and issue["fiscal_year"] == "FY2026"
    )
    assert accounting["status"] == "PASS"
    cash = next(
        issue
        for issue in validation["issues"]
        if issue["issue_type"] == "CASH_RECONCILIATION_MISMATCH"
        and issue["fiscal_year"] == "FY2026"
    )
    assert cash["status"] == "PASS"
    ratios = client.get(
        f"/api/v1/documents/{document_id}/financial-ratios?scope=CONSOLIDATED&fiscal_year=FY2026"
    ).json()
    assert len(ratios) == 13
    current = next(ratio for ratio in ratios if ratio["ratio_name"] == "current_ratio")
    margin = next(ratio for ratio in ratios if ratio["ratio_name"] == "net_profit_margin")
    roa = next(ratio for ratio in ratios if ratio["ratio_name"] == "return_on_assets")
    assert Decimal(current["ratio_value"]) == Decimal("1.666667")
    assert Decimal(margin["ratio_value"]) == Decimal("0.073600")
    assert roa["calculation_basis"] == "AVERAGE_BALANCE"
    detail = client.get(f"/api/v1/financial-ratios/{current['id']}").json()
    assert {item["input_role"] for item in detail["inputs"]} == {
        "current_assets",
        "current_liabilities",
    }
    assert all(item["source"]["page_number"] == 2 for item in detail["inputs"])
    debt_ratio = next(ratio for ratio in ratios if ratio["ratio_name"] == "debt_to_equity")
    debt_detail = client.get(f"/api/v1/financial-ratios/{debt_ratio['id']}").json()
    derived_debt = next(
        item for item in debt_detail["inputs"] if item["input_role"] == "total_debt"
    )
    assert len(derived_debt["derived_sources"]) == 2
    with Session(connection) as session:
        assert session.scalar(select(func.count()).select_from(FinancialAnalysisRun)) == 1
        assert session.scalar(select(func.count()).select_from(FinancialRatio)) == 26
        assert session.scalar(select(func.count()).select_from(FinancialRatioInput)) > 30
        assert session.scalar(select(func.count()).select_from(FinancialValidationIssue)) > 0
        audit_actions = set(
            session.scalars(select(AuditLog.action).where(AuditLog.entity_id == document_id)).all()
        )
        assert {
            "FINANCIAL_NORMALIZATION_STARTED",
            "FINANCIAL_NORMALIZATION_COMPLETED",
            "FINANCIAL_VALIDATION_COMPLETED",
            "FINANCIAL_RATIOS_CALCULATED",
            "FINANCIAL_ANALYSIS_COMPLETED",
        } <= audit_actions
        assert [
            (page.id, page.text_content)
            for page in session.scalars(
                select(DocumentPage).where(DocumentPage.document_id == document_id)
            )
        ] == before_pages


def test_analysis_requires_extraction(
    analysis_context: tuple[TestClient, Connection, UUID],
) -> None:
    client, connection, _ = analysis_context
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        company = Company(legal_name="Missing Extract Limited")
        session.add(company)
        session.flush()
        job = AnalysisJob(company_id=company.id)
        session.add(job)
        session.flush()
        document = Document(
            company_id=company.id,
            analysis_job_id=job.id,
            original_filename="missing.pdf",
            status=DocumentStatus.UPLOADED,
            parser_status=ParserStatus.PARSED,
            sha256_hash=uuid4().hex,
        )
        session.add(document)
        session.commit()
        document_id = document.id
    response = client.post(f"/api/v1/documents/{document_id}/financial-analysis")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FINANCIAL_EXTRACTION_REQUIRED"


def test_analysis_transaction_rolls_back_on_failure(
    analysis_context: tuple[TestClient, Connection, UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, connection, document_id = analysis_context
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-statements/extract").status_code
        == 200
    )
    original = analysis_service.write_audit_log

    def fail_completion(*args: object, **kwargs: object) -> object:
        if kwargs.get("action") in {
            "FINANCIAL_ANALYSIS_COMPLETED",
            "FINANCIAL_ANALYSIS_REVIEW_REQUIRED",
        }:
            raise RuntimeError("simulated analysis persistence failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(analysis_service, "write_audit_log", fail_completion)
    response = client.post(f"/api/v1/documents/{document_id}/financial-analysis")
    assert response.status_code == 500
    with Session(connection) as session:
        assert session.scalar(select(func.count()).select_from(FinancialAnalysisRun)) == 0
        assert session.scalar(select(func.count()).select_from(NormalizedFinancialValue)) == 0
        assert session.scalar(select(func.count()).select_from(FinancialRatio)) == 0


def test_changed_line_item_input_creates_new_analysis_run(
    analysis_context: tuple[TestClient, Connection, UUID],
) -> None:
    client, connection, document_id = analysis_context
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-statements/extract").status_code
        == 200
    )
    assert client.post(f"/api/v1/documents/{document_id}/financial-analysis").status_code == 200
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        item = session.scalar(
            select(FinancialLineItem).where(
                FinancialLineItem.document_id == document_id,
                FinancialLineItem.canonical_name == "profit_after_tax",
                FinancialLineItem.fiscal_year == "FY2026",
            )
        )
        assert item is not None
        item.numeric_value = Decimal("93")
        session.commit()
    assert client.post(f"/api/v1/documents/{document_id}/financial-analysis").status_code == 200
    with Session(connection) as session:
        assert session.scalar(select(func.count()).select_from(FinancialAnalysisRun)) == 2
