from __future__ import annotations

# ruff: noqa: E501
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.five_cs import get_five_cs, get_five_cs_evidence, get_five_cs_review_items
from app.models.analysis_job import AnalysisJob
from app.models.company import Company
from app.models.company_profile import CompanyProfile
from app.models.credit import CreditAssessment, CreditSubscore
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.enums import (
    ChangeType,
    CreditAssessmentStatus,
    CreditComponent,
    CreditRiskBand,
    FinancialScope,
    IdentityMatchStatus,
    NormalizationStatus,
    PageExtractionMethod,
    ProfileStatus,
    RatioStatus,
    TrendDirection,
    TrendMetricSourceType,
    TrendStatus,
    ValueOrigin,
)
from app.models.financial_analysis import (
    FinancialAnalysisRun,
    FinancialRatio,
    FinancialRatioInput,
    NormalizedFinancialValue,
)
from app.models.financial_trend import FinancialTrend, FinancialTrendInput, FinancialTrendRun
from app.models.five_cs import FiveCsAssessment, FiveCsEvidence, FiveCsReviewItem, FiveCsSection
from app.services.five_cs.capacity import build_capacity
from app.services.five_cs.capital import build_capital
from app.services.five_cs.character import build_character
from app.services.five_cs.collateral import build_collateral
from app.services.five_cs.completeness import overall_completeness, section_completeness
from app.services.five_cs.conditions import build_conditions
from app.services.five_cs.confidence import section_confidence, section_status
from app.services.five_cs.evidence import draft
from app.services.five_cs.policy import (
    ENGINE_VERSION,
    POLICY_VERSION,
    SECTIONS,
    SUMMARY_VERSION,
    five_cs_policy,
    validate_policy,
    validate_section,
)
from app.services.five_cs.service import FiveCsAssessmentService
from app.services.five_cs.summaries import summary


def page(text: str) -> DocumentPage:
    return DocumentPage(
        page_number=1,
        extraction_method=PageExtractionMethod.NATIVE_TEXT,
        text_content=text,
        character_count=len(text),
        word_count=len(text.split()),
        text_quality_score=0.95,
        parser_version="test",
    )


def profile() -> CompanyProfile:
    return CompanyProfile(
        legal_name="Example Ltd",
        business_description="Manufactures electrical equipment.",
        overall_confidence=0.9,
        status=ProfileStatus.VERIFIED,
        identity_match_status=IdentityMatchStatus.MATCHED,
        extractor_version="test",
    )


def test_five_cs_policy_versions_sections_and_thresholds() -> None:
    policy = five_cs_policy()
    assert policy["version"] == POLICY_VERSION
    assert policy["engine_version"] == ENGINE_VERSION
    assert policy["summary_version"] == SUMMARY_VERSION
    assert tuple(policy["sections"]) == SECTIONS
    assert validate_section("capacity") == "CAPACITY"
    with pytest.raises(ValueError, match="FIVE_CS_SECTION_UNKNOWN"):
        validate_section("PERSONALITY")
    broken = {**policy, "confidence": {"verified_min": 1.1, "review_min": 0.5}}
    with pytest.raises(ValueError, match="OUT_OF_RANGE"):
        validate_policy(broken)


def test_character_is_partial_and_never_infers_personality() -> None:
    rows = build_character(profile(), [page("Independent auditor's report")], False)
    codes = {item.observation_code for item in rows}
    text = " ".join(item.description for item in rows).lower()
    assert "CHARACTER_IDENTITY_MATCHED" in codes
    assert "CHARACTER_PROMOTER_RESEARCH_UNAVAILABLE" in codes
    assert "CHARACTER_REPAYMENT_HISTORY_UNAVAILABLE" in codes
    assert all(word not in text for word in ("honest", "trustworthy", "integrity"))
    assert "external promoter" in summary("CHARACTER", rows).lower()


def test_character_identity_conflict_requires_review() -> None:
    item = profile()
    item.identity_match_status = IdentityMatchStatus.MISMATCH
    rows = build_character(item, [], True)
    assert "CHARACTER_IDENTITY_CONFLICT" in {row.observation_code for row in rows}
    assert any(row.status == "CONFLICTING" for row in rows)


def test_collateral_requires_explicit_security_phrase_and_never_uses_generic_ppe() -> None:
    generic = build_collateral([page("Property plant and machinery total assets 500")])
    assert not {item.observation_code for item in generic} & {
        "COLLATERAL_SECURITY_MENTIONED",
        "COLLATERAL_SECURED_BORROWINGS_MENTIONED",
    }
    explicit = build_collateral(
        [page("Borrowings are secured by first charge over plant and machinery.")]
    )
    assert "COLLATERAL_SECURED_BORROWINGS_MENTIONED" in {item.observation_code for item in explicit}
    assert "COLLATERAL_VALUE_UNAVAILABLE" in {item.observation_code for item in explicit}
    assert explicit[0].page_number == 1
    assert "value" in summary("COLLATERAL", explicit).lower()


def test_collateral_explicit_mention_remains_partial() -> None:
    rows = build_collateral([page("Secured borrowings have a first charge over inventory.")])
    completeness = section_completeness("COLLATERAL", rows, five_cs_policy())
    confidence = section_confidence("COLLATERAL", rows, five_cs_policy())
    assert section_status("COLLATERAL", rows, completeness, confidence, five_cs_policy()) in {
        "PARTIAL",
        "NEEDS_REVIEW",
    }
    assert completeness < 1


def ratio(name: str, value: str) -> FinancialRatio:
    return FinancialRatio(
        ratio_name=name,
        ratio_value=Decimal(value),
        status=RatioStatus.VERIFIED,
        confidence_score=0.9,
    )


def value(name: str, amount: str) -> NormalizedFinancialValue:
    return NormalizedFinancialValue(
        canonical_name=name,
        normalized_value=Decimal(amount),
        normalization_status=NormalizationStatus.NORMALIZED,
        normalization_confidence=0.9,
    )


def subscore(component: CreditComponent) -> CreditSubscore:
    return CreditSubscore(
        component_name=component,
        normalized_score=Decimal(80),
        confidence_score=Decimal("0.88"),
        status=CreditAssessmentStatus.VERIFIED,
    )


def test_capacity_uses_persisted_ratios_cash_flow_and_repayment_subscore() -> None:
    rows = build_capacity(
        {
            "interest_coverage": ratio("interest_coverage", "4"),
            "debt_to_ebitda": ratio("debt_to_ebitda", "1.8"),
            "operating_cash_flow_to_debt": ratio("operating_cash_flow_to_debt", "0.35"),
        },
        {"cash_flow_from_operations": value("cash_flow_from_operations", "100")},
        {},
        {},
        subscore(CreditComponent.REPAYMENT_CAPACITY),
        {},
        five_cs_policy()["thresholds"],  # type: ignore[arg-type]
    )
    codes = {row.observation_code for row in rows}
    assert {
        "CAPACITY_REPAYMENT_SUBSCORE",
        "CAPACITY_STRONG_INTEREST_COVERAGE",
        "CAPACITY_LOW_DEBT_TO_EBITDA",
        "CAPACITY_POSITIVE_OPERATING_CASH_FLOW",
    } <= codes
    assert "interest coverage" in summary("CAPACITY", rows).lower()


def test_capacity_negative_cash_flow_is_negative_evidence() -> None:
    rows = build_capacity(
        {},
        {"cash_flow_from_operations": value("cash_flow_from_operations", "-10")},
        {},
        {},
        None,
        {},
        five_cs_policy()["thresholds"],  # type: ignore[arg-type]
    )
    assert (
        next(
            row for row in rows if row.observation_code == "CAPACITY_NEGATIVE_OPERATING_CASH_FLOW"
        ).impact
        == "NEGATIVE"
    )


def test_capital_negative_equity_and_net_worth_unavailable() -> None:
    rows = build_capital(
        {"debt_to_equity": ratio("debt_to_equity", "2.5")},
        {"total_equity": value("total_equity", "-5")},
        {},
        subscore(CreditComponent.FINANCIAL_STRENGTH),
        {},
        five_cs_policy()["thresholds"],  # type: ignore[arg-type]
    )
    codes = {row.observation_code for row in rows}
    assert "CAPITAL_NEGATIVE_EQUITY" in codes
    assert "CAPITAL_HIGH_LEVERAGE" in codes
    assert "CAPITAL_NET_WORTH_UNAVAILABLE" in codes


def test_conditions_internal_context_never_claims_external_outlook() -> None:
    rows = build_conditions(profile(), None, {}, {}, {})
    codes = {row.observation_code for row in rows}
    assert "CONDITIONS_EXTERNAL_SECTOR_OUTLOOK_UNAVAILABLE" in codes
    assert "CONDITIONS_REGULATORY_RESEARCH_UNAVAILABLE" in codes
    text = summary("CONDITIONS", rows).lower()
    assert "external sector" in text and "unavailable" in text


def test_completeness_is_availability_not_strength_and_confidence_is_conservative() -> None:
    policy = five_cs_policy()
    evidence = [
        draft("CAPACITY", "repayment_subscore", "A", "A", "A", "NEGATIVE", 0.6, "VERIFIED"),
        draft("CAPACITY", "interest_coverage", "B", "B", "B", "NEGATIVE", 0.9, "VERIFIED"),
        draft("CAPACITY", "debt_to_ebitda", "C", "C", "C", "NEGATIVE", 0.9, "VERIFIED"),
        draft("CAPACITY", "ocf_to_debt", "D", "D", "D", "NEGATIVE", 0.9, "VERIFIED"),
        draft("CAPACITY", "cash_flow", "E", "E", "E", "NEGATIVE", 0.9, "VERIFIED"),
    ]
    assert section_completeness("CAPACITY", evidence, policy) == 1
    assert section_confidence("CAPACITY", evidence, policy) == 0.6
    assert overall_completeness([0.4, 1.0, 0.8, 0.0, 0.5]) == pytest.approx(0.54)


def _context(
    session: Session, company_name: str = "Day 15 Test Ltd"
) -> tuple[Document, CreditAssessment]:
    company = Company(legal_name=company_name, country="India")
    session.add(company)
    session.flush()
    job = AnalysisJob(company_id=company.id)
    session.add(job)
    session.flush()
    document = Document(
        analysis_job_id=job.id,
        company_id=company.id,
        original_filename="day15.pdf",
        sha256_hash="1" * 64,
    )
    session.add(document)
    session.flush()
    source_page = DocumentPage(
        document_id=document.id,
        page_number=1,
        extraction_method=PageExtractionMethod.NATIVE_TEXT,
        text_content="Independent Auditor's Report. Borrowings are secured by first charge over plant and machinery.",
        character_count=93,
        word_count=13,
        text_quality_score=0.95,
        parser_version="test",
    )
    session.add(source_page)
    session.flush()
    company_profile = CompanyProfile(
        analysis_job_id=job.id,
        company_id=company.id,
        document_id=document.id,
        legal_name=company.legal_name,
        business_description="Manufactures electrical equipment.",
        overall_confidence=0.9,
        status=ProfileStatus.VERIFIED,
        identity_match_status=IdentityMatchStatus.MATCHED,
        extractor_version="test",
    )
    session.add(company_profile)
    analysis = FinancialAnalysisRun(
        document_id=document.id,
        analysis_job_id=job.id,
        input_hash="2" * 64,
        status="VERIFIED",
        completeness_score=0.95,
        normalized_value_count=2,
        derived_value_count=0,
        ratio_count=5,
        validator_version="test",
        calculator_version="test",
        ratio_taxonomy_version="test",
    )
    session.add(analysis)
    session.flush()
    values = {}
    for name, value in (("total_equity", "500"), ("cash_flow_from_operations", "100")):
        row = NormalizedFinancialValue(
            run_id=analysis.id,
            analysis_job_id=job.id,
            company_id=company.id,
            document_id=document.id,
            canonical_name=name,
            statement_type="BALANCE_SHEET" if name == "total_equity" else "CASH_FLOW_STATEMENT",
            statement_scope=FinancialScope.CONSOLIDATED,
            fiscal_year="FY2026",
            measurement_type="MONETARY",
            raw_numeric_value=Decimal(value),
            normalized_value=Decimal(value),
            currency="INR",
            normalized_currency="INR",
            raw_unit="absolute",
            canonical_unit="absolute",
            unit_multiplier=Decimal(1),
            normalization_status=NormalizationStatus.NORMALIZED,
            normalization_confidence=0.92,
            value_origin=ValueOrigin.EXTRACTED,
            financial_line_item_id=None,
            formula=None,
            input_value_ids=None,
        )
        session.add(row)
        session.flush()
        values[name] = row
    ratios = {}
    for name, value in (
        ("interest_coverage", "4"),
        ("debt_to_ebitda", "1.8"),
        ("operating_cash_flow_to_debt", "0.35"),
        ("debt_to_equity", "0.5"),
        ("debt_to_assets", "0.25"),
    ):
        row = FinancialRatio(
            run_id=analysis.id,
            analysis_job_id=job.id,
            company_id=company.id,
            document_id=document.id,
            statement_scope=FinancialScope.CONSOLIDATED,
            fiscal_year="FY2026",
            ratio_name=name,
            ratio_category="test",
            ratio_value=Decimal(value),
            ratio_unit="x",
            status=RatioStatus.VERIFIED,
            confidence_score=0.9,
            calculation_basis="ENDING_BALANCE",
            formula="test",
            formula_version="test",
            ratio_taxonomy_version="test",
            calculator_version="test",
        )
        session.add(row)
        session.flush()
        session.add(
            FinancialRatioInput(
                financial_ratio_id=row.id,
                normalized_financial_value_id=values["total_equity"].id,
                input_role="support",
            )
        )
        ratios[name] = row
    trend_run = FinancialTrendRun(
        analysis_job_id=job.id,
        company_id=company.id,
        document_id=document.id,
        financial_analysis_run_id=analysis.id,
        input_hash="3" * 64,
        trend_calculator_version="test",
        anomaly_rule_version="test",
        status="VERIFIED",
        trend_count=2,
        anomaly_count=0,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(trend_run)
    session.flush()
    for name, direction, source_id in (
        ("total_equity", TrendDirection.INCREASING, values["total_equity"].id),
        ("revenue", TrendDirection.INCREASING, values["cash_flow_from_operations"].id),
    ):
        trend = FinancialTrend(
            run_id=trend_run.id,
            analysis_job_id=job.id,
            company_id=company.id,
            document_id=document.id,
            statement_scope=FinancialScope.CONSOLIDATED,
            metric_name=name,
            metric_source_type=TrendMetricSourceType.NORMALIZED_VALUE,
            currency="INR",
            start_fiscal_year="FY2025",
            end_fiscal_year="FY2026",
            period_count=2,
            start_value=Decimal(400),
            end_value=Decimal(500),
            absolute_change=Decimal(100),
            percentage_change=Decimal(25),
            cagr=Decimal(25),
            percentage_point_change=None,
            change_type=ChangeType.PERCENT,
            state_transition=None,
            trend_direction=direction,
            trend_strength=None,
            status=TrendStatus.VERIFIED,
            confidence_score=0.9,
            series=[
                {"fiscal_year": "FY2025", "value": "400"},
                {"fiscal_year": "FY2026", "value": "500"},
            ],
            missing_periods=None,
            calculator_version="test",
        )
        session.add(trend)
        session.flush()
        session.add(
            FinancialTrendInput(
                financial_trend_id=trend.id,
                normalized_financial_value_id=source_id,
                financial_ratio_id=None,
                input_role="FY2026",
                fiscal_year="FY2026",
            )
        )
    assessment = CreditAssessment(
        analysis_job_id=job.id,
        company_id=company.id,
        document_id=document.id,
        financial_analysis_run_id=analysis.id,
        financial_trend_run_id=trend_run.id,
        statement_scope=FinancialScope.CONSOLIDATED,
        overall_score=Decimal(75),
        risk_band=CreditRiskBand.MODERATE_LOW_RISK,
        component_coverage=Decimal("0.9"),
        confidence_score=Decimal("0.9"),
        status=CreditAssessmentStatus.VERIFIED,
        feature_builder_version="test",
        policy_version="test",
        score_engine_version="test",
        input_hash="4" * 64,
    )
    session.add(assessment)
    session.flush()
    for component in (CreditComponent.REPAYMENT_CAPACITY, CreditComponent.FINANCIAL_STRENGTH):
        session.add(
            CreditSubscore(
                credit_assessment_id=assessment.id,
                component_name=component,
                raw_score=Decimal(80),
                max_score=Decimal(100),
                normalized_score=Decimal(80),
                weight=Decimal("0.3"),
                weighted_score=Decimal(24),
                coverage_ratio=Decimal("0.9"),
                confidence_score=Decimal("0.88"),
                status=CreditAssessmentStatus.VERIFIED,
            )
        )
    session.flush()
    return document, assessment


def test_full_assessment_persistence_idempotency_lineage_and_source_immutability(
    db_session: Session,
) -> None:
    document, credit = _context(db_session)
    original_score = credit.overall_score
    service = FiveCsAssessmentService(db_session)
    first = service.analyze(document.id, FinancialScope.CONSOLIDATED)[0]
    second = service.analyze(document.id, FinancialScope.CONSOLIDATED)[0]
    assert first["assessment_id"] == second["assessment_id"]
    assert second["idempotent"] is True
    assert first["no_total_credit_score"] is True and first["lending_decision"] is None
    assert first["stale"] is False
    assert set(first["sections"]) == {name.lower() for name in SECTIONS}
    assert first["sections"]["character"]["status"] != "VERIFIED"
    assert first["sections"]["conditions"]["status"] != "VERIFIED"
    assert first["sections"]["collateral"]["status"] in {"PARTIAL", "NEEDS_REVIEW"}
    assert db_session.scalar(select(func.count()).select_from(FiveCsAssessment)) == 1
    assert db_session.scalar(select(func.count()).select_from(FiveCsSection)) == 5
    assert db_session.scalar(select(func.count()).select_from(FiveCsEvidence)) > 15
    assert db_session.scalar(select(func.count()).select_from(FiveCsReviewItem)) > 0
    assert db_session.get(CreditAssessment, credit.id).overall_score == original_score
    evidence = get_five_cs_evidence(first["assessment_id"], "CAPITAL", db_session)  # type: ignore[arg-type]
    assert any(item["source_type"] == "FINANCIAL_VALUE" for item in evidence)
    collateral = get_five_cs_evidence(first["assessment_id"], "COLLATERAL", db_session)  # type: ignore[arg-type]
    assert any(item["page_number"] == 1 for item in collateral)
    assert get_five_cs_review_items(first["assessment_id"], db_session)  # type: ignore[arg-type]
    assert get_five_cs(first["assessment_id"], db_session)["status"] in {"PARTIAL", "NEEDS_REVIEW"}  # type: ignore[arg-type]
