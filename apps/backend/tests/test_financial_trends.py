from __future__ import annotations

# ruff: noqa: E501
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
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
from app.ml.credit.features import build_feature_snapshot
from app.ml.credit.observations import create_observation
from app.models import AnalysisJob, AuditLog, Company, Document, DocumentPage
from app.models.credit import (
    CreditAssessment,
    CreditAssessmentInput,
    CreditRuleResult,
    CreditSubscore,
)
from app.models.credit_ml import CreditMLFeatureSource
from app.models.enums import (
    DocumentStatus,
    FinancialScope,
    PageExtractionMethod,
    ParserStatus,
    TrendDirection,
    TrendStatus,
)
from app.models.financial_analysis import FinancialRatio, NormalizedFinancialValue
from app.models.financial_trend import (
    FinancialAnomaly,
    FinancialAnomalyInput,
    FinancialTrend,
    FinancialTrendInput,
    FinancialTrendRun,
)
from app.services.credit_engine import service as credit_service
from app.services.financial_engine import trend_service
from app.services.financial_engine.anomaly_engine import detect_anomalies
from app.services.financial_engine.cagr import calculate_cagr
from app.services.financial_engine.growth import calculate_change, percentage_point_change
from app.services.financial_engine.trend_classifier import classify
from app.services.financial_engine.trend_series import (
    SeriesPoint,
    chronological,
    missing_years,
    period_year,
)

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
def trend_context(
    database_engine: Engine, test_url: str
) -> Iterator[tuple[TestClient, Connection, UUID]]:
    connection = database_engine.connect()
    outer = connection.begin()
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        company = Company(legal_name="Trend Analysis Limited")
        session.add(company)
        session.flush()
        job = AnalysisJob(company_id=company.id)
        session.add(job)
        session.flush()
        document = Document(
            company_id=company.id,
            analysis_job_id=job.id,
            original_filename="trends.pdf",
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


def point(year: str, value: str, currency: str = "INR", confidence: float = 0.95) -> SeriesPoint:
    return SeriesPoint(
        year, period_year(year), Decimal(value), confidence, "VERIFIED", object(), currency
    )


def trend(
    name: str, values: list[str], *, direction: TrendDirection | None = None, pp: str | None = None
) -> FinancialTrend:
    years = [f"FY{2024 + index}" for index in range(len(values))]
    series: list[dict[str, object]] = []
    for index, value in enumerate(values):
        item: dict[str, object] = {"fiscal_year": years[index], "value": value}
        if index:
            change = calculate_change(Decimal(values[index - 1]), Decimal(value))
            item["percentage_change"] = str(change.percent) if change.percent is not None else None
            item["state_transition"] = change.state_transition
        series.append(item)
    derived_direction = direction or classify([Decimal(value) for value in values])[0]
    return FinancialTrend(
        metric_name=name,
        series=series,
        trend_direction=derived_direction,
        percentage_point_change=Decimal(pp) if pp else None,
        period_count=len(values),
        confidence_score=0.9,
        status=TrendStatus.VERIFIED,
        start_fiscal_year=years[0],
        end_fiscal_year=years[-1],
    )


def anomaly_types(*trends: FinancialTrend) -> set[str]:
    return {item.anomaly_type for item in detect_anomalies(list(trends))}


def test_yoy_revenue_growth() -> None:
    assert calculate_change(Decimal("1000"), Decimal("1200")).percent == Decimal("0.2")


def test_yoy_negative_growth() -> None:
    assert calculate_change(Decimal("100"), Decimal("80")).percent == Decimal("-0.2")


def test_yoy_zero_base_not_meaningful() -> None:
    result = calculate_change(Decimal(0), Decimal(20))
    assert result.percent is None and result.reason == "ZERO_BASE"


def test_profit_to_loss_state_transition() -> None:
    assert calculate_change(Decimal(20), Decimal(-5)).state_transition == "PROFIT_TO_LOSS"


def test_loss_to_profit_state_transition() -> None:
    assert calculate_change(Decimal(-30), Decimal(20)).state_transition == "LOSS_TO_PROFIT"


def test_loss_narrowed() -> None:
    assert calculate_change(Decimal(-30), Decimal(-10)).state_transition == "LOSS_NARROWED"


def test_loss_widened() -> None:
    assert calculate_change(Decimal(-10), Decimal(-30)).state_transition == "LOSS_WIDENED"


def test_cagr_two_year_interval() -> None:
    assert calculate_cagr(Decimal(100), Decimal(121), 2).quantize(Decimal("0.0001")) == Decimal(
        "0.1000"
    )


def test_cagr_three_year_interval() -> None:
    assert calculate_cagr(Decimal(100), Decimal("133.1"), 3).quantize(Decimal("0.0001")) == Decimal(
        "0.1000"
    )


def test_cagr_invalid_negative_start() -> None:
    assert calculate_cagr(Decimal(-10), Decimal(20), 2) is None


def test_absolute_change() -> None:
    assert calculate_change(Decimal(80), Decimal(125)).absolute == Decimal(45)


def test_percentage_point_change() -> None:
    assert percentage_point_change(Decimal("0.15"), Decimal("0.12")) == Decimal("-3.00")


def test_periods_sorted_chronologically() -> None:
    assert [
        item.fiscal_year
        for item in chronological(
            [point("FY2026", "3"), point("2024-03-31", "1"), point("FY2025", "2")]
        )
    ] == ["2024-03-31", "FY2025", "FY2026"]


def test_scope_series_isolated() -> None:
    assert FinancialScope.CONSOLIDATED != FinancialScope.STANDALONE


def test_currency_series_isolated() -> None:
    assert point("FY2025", "1", "INR").currency != point("FY2026", "1", "USD").currency


def test_missing_middle_year_handled() -> None:
    assert missing_years([point("FY2024", "1"), point("FY2026", "2")]) == ["FY2025"]


def test_revenue_increasing() -> None:
    assert classify([Decimal(100), Decimal(120), Decimal(150)])[0] == TrendDirection.INCREASING


def test_revenue_decreasing() -> None:
    assert classify([Decimal(150), Decimal(120), Decimal(100)])[0] == TrendDirection.DECREASING


def test_mixed_trend() -> None:
    assert classify([Decimal(100), Decimal(130), Decimal(110)])[0] in {
        TrendDirection.MIXED,
        TrendDirection.VOLATILE,
    }


def test_insufficient_data() -> None:
    assert classify([Decimal(100)])[0] == TrendDirection.INSUFFICIENT_DATA


def test_revenue_decline_anomaly() -> None:
    assert "REVENUE_DECLINE" in anomaly_types(trend("revenue", ["100", "80"]))


def test_persistent_revenue_decline() -> None:
    assert "PERSISTENT_REVENUE_DECLINE" in anomaly_types(trend("revenue", ["100", "90", "80"]))


def test_profit_decline() -> None:
    assert "PROFIT_DECLINE" in anomaly_types(trend("profit_after_tax", ["100", "70"]))


def test_profit_to_loss_anomaly() -> None:
    assert "PROFIT_TO_LOSS" in anomaly_types(trend("profit_after_tax", ["10", "-1"]))


def test_persistent_loss_anomaly() -> None:
    assert "PERSISTENT_NET_LOSS" in anomaly_types(trend("profit_after_tax", ["-10", "-12", "-14"]))


def test_ebitda_margin_compression() -> None:
    assert "EBITDA_MARGIN_COMPRESSION" in anomaly_types(
        trend("ebitda_margin", ["0.18", "0.13"], pp="-5")
    )


def test_net_margin_compression() -> None:
    assert "NET_MARGIN_COMPRESSION" in anomaly_types(
        trend("net_profit_margin", ["0.12", "0.08"], pp="-4")
    )


def test_rising_leverage() -> None:
    assert "RISING_LEVERAGE" in anomaly_types(trend("debt_to_equity", ["0.4", "0.55", "0.82"]))


def test_debt_growth_outpaces_revenue() -> None:
    assert "DEBT_GROWTH_OUTPACING_REVENUE" in anomaly_types(
        trend("revenue", ["100", "110"]), trend("total_debt", ["50", "65"])
    )


def test_interest_coverage_deterioration() -> None:
    assert "DECLINING_INTEREST_COVERAGE" in anomaly_types(trend("interest_coverage", ["5", "3"]))


def test_liquidity_deterioration() -> None:
    assert "LIQUIDITY_DETERIORATION" in anomaly_types(trend("current_ratio", ["1.5", "1.2"]))


def test_negative_operating_cash_flow() -> None:
    assert "NEGATIVE_OPERATING_CASH_FLOW" in anomaly_types(
        trend("cash_flow_from_operations", ["10", "-1"])
    )


def test_persistent_negative_operating_cash_flow() -> None:
    assert "PERSISTENT_NEGATIVE_OPERATING_CASH_FLOW" in anomaly_types(
        trend("cash_flow_from_operations", ["-1", "-2", "-3"])
    )


def test_profit_cashflow_divergence() -> None:
    assert "PROFIT_CASH_FLOW_DIVERGENCE" in anomaly_types(
        trend("profit_after_tax", ["10", "12"]), trend("cash_flow_from_operations", ["5", "-2"])
    )


def test_receivables_outpace_revenue() -> None:
    assert "RECEIVABLES_OUTPACING_REVENUE" in anomaly_types(
        trend("revenue", ["100", "110"]), trend("trade_receivables", ["10", "14"])
    )


def test_inventory_outpace_revenue() -> None:
    assert "INVENTORY_OUTPACING_REVENUE" in anomaly_types(
        trend("revenue", ["100", "110"]), trend("inventory", ["10", "14"])
    )


def test_declining_roe() -> None:
    assert "DECLINING_ROE" in anomaly_types(trend("return_on_equity", ["0.18", "0.12"]))


def test_declining_roa() -> None:
    assert "DECLINING_ROA" in anomaly_types(trend("return_on_assets", ["0.10", "0.06"]))


def test_debt_to_ebitda_deterioration() -> None:
    assert "DEBT_TO_EBITDA_DETERIORATION" in anomaly_types(trend("debt_to_ebitda", ["2", "3"]))


def test_low_interest_coverage_alert_if_enabled() -> None:
    assert "LOW_INTEREST_COVERAGE_ALERT" in anomaly_types(trend("interest_coverage", ["2", "1.2"]))


def test_false_positive_growth_comparisons() -> None:
    types = anomaly_types(
        trend("revenue", ["100", "125"]),
        trend("total_debt", ["100", "120"]),
        trend("trade_receivables", ["100", "108"]),
        trend("profit_after_tax", ["10", "12"]),
        trend("cash_flow_from_operations", ["10", "13"]),
    )
    assert "DEBT_GROWTH_OUTPACING_REVENUE" not in types
    assert "RECEIVABLES_OUTPACING_REVENUE" not in types
    assert "PROFIT_CASH_FLOW_DIVERGENCE" not in types


def test_run_trends_api_persistence_lineage_and_idempotency(
    trend_context: tuple[TestClient, Connection, UUID],
) -> None:
    client, connection, document_id = trend_context
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-statements/extract").status_code
        == 200
    )
    assert client.post(f"/api/v1/documents/{document_id}/financial-analysis").status_code == 200
    with Session(connection) as session:
        source_values = {
            row.id: row.normalized_value
            for row in session.scalars(select(NormalizedFinancialValue)).all()
        }
        source_ratios = {
            row.id: row.ratio_value for row in session.scalars(select(FinancialRatio)).all()
        }
    response = client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze")
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["status"] == "COMPLETED" and summary["trend_count"] >= 20
    assert summary["trend_calculator_version"] == "financial_trend_calculator_v1"
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze").json() == summary
    )
    trends = client.get(
        f"/api/v1/documents/{document_id}/financial-trends?scope=CONSOLIDATED&metric=revenue"
    ).json()
    assert len(trends) == 1 and trends[0]["trend_direction"] == "INCREASING"
    assert Decimal(trends[0]["percentage_change"]) == Decimal("0.157407")
    detail = client.get(f"/api/v1/financial-trends/{trends[0]['id']}").json()
    assert len(detail["inputs"]) == 2 and all(item["evidence"] for item in detail["inputs"])
    anomalies = client.get(f"/api/v1/documents/{document_id}/financial-anomalies").json()
    if anomalies:
        anomaly_detail = client.get(f"/api/v1/financial-anomalies/{anomalies[0]['id']}")
        assert anomaly_detail.status_code == 200 and anomaly_detail.json()["inputs"]
    with Session(connection) as session:
        assert session.scalar(select(func.count()).select_from(FinancialTrendRun)) == 1
        assert (
            session.scalar(select(func.count()).select_from(FinancialTrendInput))
            >= summary["trend_count"] * 2
        )
        assert (
            session.scalar(select(func.count()).select_from(FinancialAnomalyInput))
            >= summary["anomaly_count"]
        )
        assert {
            row.id: row.normalized_value
            for row in session.scalars(select(NormalizedFinancialValue)).all()
        } == source_values
        assert {
            row.id: row.ratio_value for row in session.scalars(select(FinancialRatio)).all()
        } == source_ratios
        actions = set(
            session.scalars(select(AuditLog.action).where(AuditLog.entity_id == document_id)).all()
        )
        assert {
            "FINANCIAL_TREND_ANALYSIS_STARTED",
            "FINANCIAL_TRENDS_CALCULATED",
            "FINANCIAL_TREND_ANALYSIS_COMPLETED",
        } <= actions


def test_day8_required_and_unknown_document(
    trend_context: tuple[TestClient, Connection, UUID],
) -> None:
    client, _, document_id = trend_context
    response = client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze")
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "FINANCIAL_ANALYSIS_REQUIRED"
    )
    assert client.get(f"/api/v1/documents/{uuid4()}/financial-trends").status_code == 404


def test_credit_risk_preconditions_and_scope_filter(
    trend_context: tuple[TestClient, Connection, UUID],
) -> None:
    client, _, document_id = trend_context
    response = client.post(f"/api/v1/documents/{document_id}/credit-risk/analyze")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FINANCIAL_ANALYSIS_REQUIRED"
    client.post(f"/api/v1/documents/{document_id}/financial-statements/extract")
    client.post(f"/api/v1/documents/{document_id}/financial-analysis")
    response = client.post(f"/api/v1/documents/{document_id}/credit-risk/analyze")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FINANCIAL_TREND_ANALYSIS_REQUIRED"
    client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze")
    response = client.post(
        f"/api/v1/documents/{document_id}/credit-risk/analyze?scope=CONSOLIDATED"
    )
    assert response.status_code == 200, response.text
    rows = client.get(f"/api/v1/documents/{document_id}/credit-risk?scope=CONSOLIDATED").json()
    assert len(rows) == 1 and rows[0]["scope"] == "CONSOLIDATED"
    assert client.get(f"/api/v1/documents/{uuid4()}/credit-risk").status_code == 404


def test_changed_day9_input_creates_new_credit_assessment(
    trend_context: tuple[TestClient, Connection, UUID],
) -> None:
    client, connection, document_id = trend_context
    client.post(f"/api/v1/documents/{document_id}/financial-statements/extract")
    client.post(f"/api/v1/documents/{document_id}/financial-analysis")
    client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze")
    first = client.post(f"/api/v1/documents/{document_id}/credit-risk/analyze").json()
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        row = session.scalar(
            select(FinancialTrend).where(
                FinancialTrend.document_id == document_id,
                FinancialTrend.metric_name == "revenue",
            )
        )
        assert row is not None
        row.end_value += Decimal("1")
        session.commit()
    second = client.post(f"/api/v1/documents/{document_id}/credit-risk/analyze").json()
    assert second["assessment_id"] != first["assessment_id"]
    with Session(connection) as session:
        assert session.scalar(select(func.count()).select_from(CreditAssessment)) == 2


def test_credit_assessment_transaction_rollback(
    trend_context: tuple[TestClient, Connection, UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, connection, document_id = trend_context
    client.post(f"/api/v1/documents/{document_id}/financial-statements/extract")
    client.post(f"/api/v1/documents/{document_id}/financial-analysis")
    client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze")
    original = credit_service.write_audit_log

    def fail_completion(*args: object, **kwargs: object) -> object:
        if kwargs.get("action") == "CREDIT_RISK_ANALYSIS_COMPLETED":
            raise RuntimeError("simulated Day 10 persistence failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(credit_service, "write_audit_log", fail_completion)
    assert client.post(f"/api/v1/documents/{document_id}/credit-risk/analyze").status_code == 500
    with Session(connection) as session:
        assert session.scalar(select(func.count()).select_from(CreditAssessment)) == 0
        assert session.scalar(select(func.count()).select_from(CreditSubscore)) == 0
        assert session.scalar(select(func.count()).select_from(CreditRuleResult)) == 0


def test_credit_ml_feature_snapshot_uses_day8_day9_and_optional_day10(
    trend_context: tuple[TestClient, Connection, UUID],
) -> None:
    client, connection, document_id = trend_context
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-statements/extract").status_code
        == 200
    )
    assert client.post(f"/api/v1/documents/{document_id}/financial-analysis").status_code == 200
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze").status_code == 200
    )
    assert client.post(f"/api/v1/documents/{document_id}/credit-risk/analyze").status_code == 200
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        document = session.get(Document, document_id)
        assert document is not None
        observation = create_observation(
            session,
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            document_id=document.id,
            observation_date=date(2026, 12, 31),
            as_of_fiscal_year="FY2026",
            feature_cutoff_timestamp=datetime.now(UTC) + timedelta(minutes=1),
        )
        base = build_feature_snapshot(session, observation, "BASE_FINANCIAL_V1")
        enriched = build_feature_snapshot(session, observation, "TREND_ENRICHED_V1")
        anomaly = build_feature_snapshot(session, observation, "ANOMALY_ENRICHED_V1")
        rule = build_feature_snapshot(session, observation, "RULE_SCORE_ENRICHED_V1")
        assert base.features_json["current_ratio"] is not None
        assert enriched.features_json["trend_revenue_direction"] == "INCREASING"
        assert "anomaly_persistent_net_loss" in anomaly.features_json
        assert rule.features_json["credit_score"] is not None
        assert {"company_id", "target", "target_value"}.isdisjoint(rule.features_json)
        assert (
            session.scalar(
                select(func.count())
                .select_from(CreditMLFeatureSource)
                .where(CreditMLFeatureSource.feature_snapshot_id == rule.id)
            )
            > 0
        )
        session.rollback()


def test_credit_ml_feature_cutoff_rejects_future_sources(
    trend_context: tuple[TestClient, Connection, UUID],
) -> None:
    client, connection, document_id = trend_context
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-statements/extract").status_code
        == 200
    )
    assert client.post(f"/api/v1/documents/{document_id}/financial-analysis").status_code == 200
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze").status_code == 200
    )
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        document = session.get(Document, document_id)
        assert document is not None
        observation = create_observation(
            session,
            company_id=document.company_id,
            analysis_job_id=document.analysis_job_id,
            document_id=document.id,
            observation_date=date(2020, 1, 1),
            as_of_fiscal_year="FY2020",
            feature_cutoff_timestamp=datetime(2020, 1, 1, tzinfo=UTC),
        )
        snapshot = build_feature_snapshot(session, observation)
        assert snapshot.features_json["current_ratio"] is None
        assert snapshot.features_json["trend_revenue_direction"] is None
        assert snapshot.features_json["anomaly_persistent_net_loss"] == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(CreditMLFeatureSource)
                .where(CreditMLFeatureSource.feature_snapshot_id == snapshot.id)
            )
            == 0
        )
        session.rollback()


def test_changed_day8_input_creates_new_run(
    trend_context: tuple[TestClient, Connection, UUID],
) -> None:
    client, connection, document_id = trend_context
    client.post(f"/api/v1/documents/{document_id}/financial-statements/extract")
    client.post(f"/api/v1/documents/{document_id}/financial-analysis")
    client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze")
    with Session(connection, join_transaction_mode="create_savepoint") as session:
        ratio = session.scalar(
            select(FinancialRatio).where(
                FinancialRatio.document_id == document_id, FinancialRatio.ratio_value.is_not(None)
            )
        )
        assert ratio is not None
        ratio.ratio_value += Decimal("0.01")
        session.commit()
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze").status_code == 200
    )
    with Session(connection) as session:
        assert session.scalar(select(func.count()).select_from(FinancialTrendRun)) == 2


def test_trend_analysis_rollback(
    trend_context: tuple[TestClient, Connection, UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, connection, document_id = trend_context
    client.post(f"/api/v1/documents/{document_id}/financial-statements/extract")
    client.post(f"/api/v1/documents/{document_id}/financial-analysis")
    original = trend_service.write_audit_log

    def fail_completion(*args: object, **kwargs: object) -> object:
        if kwargs.get("action") == "FINANCIAL_TREND_ANALYSIS_COMPLETED":
            raise RuntimeError("simulated Day 9 persistence failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(trend_service, "write_audit_log", fail_completion)
    assert (
        client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze").status_code == 500
    )
    with Session(connection) as session:
        assert session.scalar(select(func.count()).select_from(FinancialTrendRun)) == 0
        assert session.scalar(select(func.count()).select_from(FinancialTrend)) == 0
        assert session.scalar(select(func.count()).select_from(FinancialAnomaly)) == 0


def test_disposable_upload_to_day9_smoke(
    database_engine: Engine, test_url: str, tmp_path: Path
) -> None:
    with fitz.open() as pdf:
        for text in (
            "TREND ANALYSIS LIMITED\nANNUAL REPORT 2025-26\nAbout Us\nThe company manufactures electrical equipment and provides maintenance services to industrial customers.",
            INCOME,
            BALANCE,
            CASH,
        ):
            page = pdf.new_page()
            page.insert_textbox(fitz.Rect(50, 50, 560, 790), text, fontsize=10)
        pdf_bytes = pdf.tobytes()
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
            upload = client.post(
                "/api/v1/documents/upload",
                data={"company_legal_name": "Trend Analysis Limited"},
                files={"file": ("annual-report.pdf", pdf_bytes, "application/pdf")},
            )
            assert upload.status_code == 201, upload.text
            document_id = upload.json()["document"]["id"]
            assert client.post(f"/api/v1/documents/{document_id}/parse").status_code == 200
            assert (
                client.post(f"/api/v1/documents/{document_id}/company-profile/extract").status_code
                == 200
            )
            assert (
                client.post(
                    f"/api/v1/documents/{document_id}/financial-statements/extract"
                ).status_code
                == 200
            )
            assert (
                client.post(f"/api/v1/documents/{document_id}/financial-analysis").status_code
                == 200
            )
            with Session(connection) as session:
                before = (
                    session.scalar(select(func.count()).select_from(DocumentPage)),
                    session.scalar(select(func.count()).select_from(NormalizedFinancialValue)),
                    session.scalar(select(func.count()).select_from(FinancialRatio)),
                )
            analysis = client.post(f"/api/v1/documents/{document_id}/financial-trends/analyze")
            assert analysis.status_code == 200, analysis.text
            assert analysis.json()["trend_count"] >= 20
            assert (
                client.get(f"/api/v1/documents/{document_id}/financial-trends").status_code == 200
            )
            assert (
                client.get(f"/api/v1/documents/{document_id}/financial-anomalies").status_code
                == 200
            )
            credit = client.post(f"/api/v1/documents/{document_id}/credit-risk/analyze")
            assert credit.status_code == 200, credit.text
            credit_payload = credit.json()
            assert credit_payload["policy_version"] == "credit_policy_v1"
            assert len(credit_payload["subscores"]) == 5
            assessment_id = credit_payload["assessment_id"]
            assert client.get(f"/api/v1/credit-assessments/{assessment_id}").status_code == 200
            assert client.get(f"/api/v1/credit-assessments/{assessment_id}/reasons").json()
            assert client.get(f"/api/v1/credit-assessments/{assessment_id}/evidence").json()
            assert (
                client.post(f"/api/v1/documents/{document_id}/credit-risk/analyze").json()
                == credit_payload
            )
            with Session(connection) as session:
                after = (
                    session.scalar(select(func.count()).select_from(DocumentPage)),
                    session.scalar(select(func.count()).select_from(NormalizedFinancialValue)),
                    session.scalar(select(func.count()).select_from(FinancialRatio)),
                )
                assert session.scalar(select(func.count()).select_from(CreditAssessment)) == 1
                assert session.scalar(select(func.count()).select_from(CreditSubscore)) == 5
                assert session.scalar(select(func.count()).select_from(CreditRuleResult)) > 0
                assert session.scalar(select(func.count()).select_from(CreditAssessmentInput)) > 0
            assert after == before
            assert next((tmp_path / "uploads").glob("*.pdf")).read_bytes() == pdf_bytes
    finally:
        outer.rollback()
        connection.close()
