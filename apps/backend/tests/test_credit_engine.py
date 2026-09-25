from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.enums import CreditAssessmentStatus, CreditRiskBand, FinancialScope
from app.services.credit_engine.business_stability import score_business_stability
from app.services.credit_engine.data_quality import score_data_quality
from app.services.credit_engine.financial_strength import score_financial_strength
from app.services.credit_engine.industry_context import score_industry_context
from app.services.credit_engine.overlap import suppress_overlaps
from app.services.credit_engine.policy import credit_policy, risk_band
from app.services.credit_engine.repayment_capacity import score_repayment_capacity
from app.services.credit_engine.rules import clamp_score
from app.services.credit_engine.schemas import (
    AnomalyFeature,
    CreditFeatures,
    MetricFeature,
    TrendFeature,
)
from app.services.credit_engine.scoring import score_credit


def metric(name: str, value: str, role: str | None = None) -> MetricFeature:
    return MetricFeature(name, Decimal(value), "VERIFIED", Decimal("0.95"), uuid4(), role or name)


def trend(name: str, direction: str) -> TrendFeature:
    return TrendFeature(name, direction, "VERIFIED", Decimal("0.9"), 0, uuid4(), f"trend:{name}")


def anomaly(name: str) -> AnomalyFeature:
    return AnomalyFeature(name, "HIGH", "VERIFIED", Decimal("0.9"), uuid4(), f"anomaly:{name}")


def complete_features() -> CreditFeatures:
    features = CreditFeatures(scope=FinancialScope.CONSOLIDATED)
    features.ratios = {
        "current_ratio": metric("current_ratio", "1.8", "ratio:current_ratio"),
        "quick_ratio": metric("quick_ratio", "1.2", "ratio:quick_ratio"),
        "debt_to_equity": metric("debt_to_equity", "0.4", "ratio:debt_to_equity"),
        "debt_to_assets": metric("debt_to_assets", "0.3", "ratio:debt_to_assets"),
        "ebitda_margin": metric("ebitda_margin", "0.16", "ratio:ebitda_margin"),
        "net_profit_margin": metric("net_profit_margin", "0.09", "ratio:net_profit_margin"),
        "return_on_assets": metric("return_on_assets", "0.08", "ratio:return_on_assets"),
        "return_on_equity": metric("return_on_equity", "0.14", "ratio:return_on_equity"),
        "interest_coverage": metric("interest_coverage", "5", "ratio:interest_coverage"),
        "debt_to_ebitda": metric("debt_to_ebitda", "1.8", "ratio:debt_to_ebitda"),
        "operating_cash_flow_to_debt": metric(
            "operating_cash_flow_to_debt", "0.35", "ratio:operating_cash_flow_to_debt"
        ),
    }
    features.values = {
        "cash_flow_from_operations": metric(
            "cash_flow_from_operations", "100", "value:cash_flow_from_operations"
        ),
        "total_equity": metric("total_equity", "500", "value:total_equity"),
    }
    features.trends = {
        "revenue": trend("revenue", "INCREASING"),
        "profit_after_tax": trend("profit_after_tax", "INCREASING"),
        "ebitda": trend("ebitda", "INCREASING"),
    }
    features.completeness = Decimal(1)
    features.verified_ratio_share = Decimal(1)
    features.profile_status = "VERIFIED"
    features.profile_confidence = Decimal("0.9")
    return features


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        ("100", CreditRiskBand.LOW_RISK),
        ("80", CreditRiskBand.LOW_RISK),
        ("79.99", CreditRiskBand.MODERATE_LOW_RISK),
        ("65", CreditRiskBand.MODERATE_LOW_RISK),
        ("50", CreditRiskBand.MODERATE_RISK),
        ("35", CreditRiskBand.ELEVATED_RISK),
        ("0", CreditRiskBand.HIGH_RISK),
    ],
)
def test_risk_band_boundaries(score: str, expected: CreditRiskBand) -> None:
    assert risk_band(Decimal(score)) == expected


def test_policy_weights_sum_to_one() -> None:
    assert sum(Decimal(str(value)) for value in credit_policy()["component_weights"].values()) == 1


def test_unverified_industry_is_renormalized() -> None:
    result = score_credit(complete_features())
    assert result.component_coverage == Decimal("0.9000")
    assert result.score is not None and result.risk_band is not None
    assert (
        next(
            item for item in result.components if item.component.value == "INDUSTRY_CONTEXT"
        ).status
        == CreditAssessmentStatus.UNAVAILABLE
    )


def test_verified_industry_raises_coverage_without_label_risk() -> None:
    features = complete_features()
    features.domain_status = "VERIFIED"
    features.domain_confidence = Decimal("0.88")
    result = score_credit(features)
    assert result.component_coverage == Decimal("1.0000")
    industry = next(
        item for item in result.components if item.component.value == "INDUSTRY_CONTEXT"
    )
    assert [item.code for item in industry.rules] == ["VERIFIED_DOMAIN_CONTEXT"]


def test_missing_critical_components_omits_score_and_band() -> None:
    features = complete_features()
    features.ratios = {}
    result = score_credit(features)
    assert result.status == CreditAssessmentStatus.INSUFFICIENT_DATA
    assert result.score is None and result.risk_band is None


def test_persistent_ocf_alert_suppresses_one_year_alert() -> None:
    selected = suppress_overlaps(
        {
            "PERSISTENT_NEGATIVE_OPERATING_CASH_FLOW": anomaly(
                "PERSISTENT_NEGATIVE_OPERATING_CASH_FLOW"
            ),
            "NEGATIVE_OPERATING_CASH_FLOW": anomaly("NEGATIVE_OPERATING_CASH_FLOW"),
        }
    )
    assert "PERSISTENT_NEGATIVE_OPERATING_CASH_FLOW" in selected
    assert "NEGATIVE_OPERATING_CASH_FLOW" not in selected


def test_persistent_revenue_alert_suppresses_single_decline() -> None:
    selected = suppress_overlaps(
        {
            "PERSISTENT_REVENUE_DECLINE": anomaly("PERSISTENT_REVENUE_DECLINE"),
            "REVENUE_DECLINE": anomaly("REVENUE_DECLINE"),
        }
    )
    assert set(selected) == {"PERSISTENT_REVENUE_DECLINE"}


def test_critical_conflict_propagates_to_assessment() -> None:
    features = complete_features()
    features.critical_conflict = True
    assert score_credit(features).status == CreditAssessmentStatus.CONFLICTING


@pytest.mark.parametrize(
    ("name", "value", "code"),
    [
        ("current_ratio", "1.5", "STRONG_CURRENT_RATIO"),
        ("current_ratio", "1.0", "MODERATE_CURRENT_RATIO"),
        ("current_ratio", "0.99", "LOW_CURRENT_RATIO"),
        ("debt_to_equity", "0.5", "LOW_LEVERAGE"),
        ("debt_to_equity", "1.0", "MODERATE_LEVERAGE"),
        ("debt_to_equity", "1.5", "NEUTRAL_LEVERAGE"),
        ("debt_to_equity", "2.01", "HIGH_LEVERAGE"),
    ],
)
def test_financial_strength_threshold_rules(name: str, value: str, code: str) -> None:
    features = complete_features()
    features.ratios = {name: metric(name, value, f"ratio:{name}")}
    result = score_financial_strength(features)
    assert code in {item.code for item in result.rules}


def test_margin_compression_and_negative_equity_penalized() -> None:
    features = complete_features()
    features.anomalies["EBITDA_MARGIN_COMPRESSION"] = anomaly("EBITDA_MARGIN_COMPRESSION")
    features.values["total_equity"] = metric("total_equity", "-1", "value:total_equity")
    codes = {item.code for item in score_financial_strength(features).rules}
    assert {"MARGIN_COMPRESSION", "NEGATIVE_EQUITY"} <= codes


def test_not_meaningful_roe_is_not_rewarded() -> None:
    features = complete_features()
    source = features.ratios["return_on_equity"]
    features.ratios["return_on_equity"] = MetricFeature(
        source.name,
        source.value,
        "NOT_MEANINGFUL",
        source.confidence,
        source.source_id,
        source.source_role,
    )
    assert "POSITIVE_ROE" not in {item.code for item in score_financial_strength(features).rules}


@pytest.mark.parametrize(
    ("name", "value", "code"),
    [
        ("interest_coverage", "4", "STRONG_INTEREST_COVERAGE"),
        ("interest_coverage", "1.5", "LOW_INTEREST_COVERAGE"),
        ("interest_coverage", "0.9", "VERY_LOW_INTEREST_COVERAGE"),
        ("debt_to_ebitda", "1.9", "LOW_DEBT_TO_EBITDA"),
        ("debt_to_ebitda", "3.0", "MODERATE_DEBT_TO_EBITDA"),
        ("debt_to_ebitda", "4.0", "WEAK_DEBT_TO_EBITDA"),
        ("debt_to_ebitda", "5.1", "HIGH_DEBT_TO_EBITDA"),
    ],
)
def test_repayment_threshold_rules(name: str, value: str, code: str) -> None:
    features = complete_features()
    features.ratios = {name: metric(name, value, f"ratio:{name}")}
    assert code in {item.code for item in score_repayment_capacity(features).rules}


def test_negative_ebitda_ratio_not_scored() -> None:
    features = complete_features()
    features.ratios["debt_to_ebitda"] = MetricFeature(
        "debt_to_ebitda", None, "NOT_MEANINGFUL", Decimal("0.9"), uuid4(), "ratio:debt_to_ebitda"
    )
    assert not {
        "LOW_DEBT_TO_EBITDA",
        "MODERATE_DEBT_TO_EBITDA",
        "WEAK_DEBT_TO_EBITDA",
        "HIGH_DEBT_TO_EBITDA",
    } & {item.code for item in score_repayment_capacity(features).rules}


def test_repayment_anomaly_reasons_and_no_dscr() -> None:
    features = complete_features()
    features.anomalies = {
        name: anomaly(name)
        for name in (
            "PERSISTENT_NEGATIVE_OPERATING_CASH_FLOW",
            "PROFIT_CASH_FLOW_DIVERGENCE",
            "DECLINING_INTEREST_COVERAGE",
        )
    }
    codes = {item.code for item in score_repayment_capacity(features).rules}
    assert {
        "PERSISTENT_NEGATIVE_OPERATING_CASH_FLOW",
        "PROFIT_CASHFLOW_DIVERGENCE",
        "DECLINING_INTEREST_COVERAGE",
    } <= codes
    assert all("DSCR" not in code for code in codes)


@pytest.mark.parametrize(
    ("alert", "code"),
    [
        ("PERSISTENT_REVENUE_DECLINE", "PERSISTENT_REVENUE_DECLINE"),
        ("PERSISTENT_NET_LOSS", "PERSISTENT_NET_LOSS"),
        ("PROFIT_TO_LOSS", "PROFIT_TO_LOSS"),
        ("LOSS_TO_PROFIT", "LOSS_TO_PROFIT"),
        ("NET_MARGIN_COMPRESSION", "STABILITY_MARGIN_COMPRESSION"),
    ],
)
def test_business_stability_alert_rules(alert: str, code: str) -> None:
    features = complete_features()
    features.anomalies = {alert: anomaly(alert)}
    assert code in {item.code for item in score_business_stability(features).rules}


def test_data_quality_penalizes_gaps_errors_and_conflicts() -> None:
    features = complete_features()
    features.completeness = Decimal("0.4")
    features.validation_errors = 2
    features.conflicting_inputs = 1
    features.verified_ratio_share = Decimal("0.4")
    features.missing_period_count = 2
    result = score_data_quality(features)
    codes = {item.code for item in result.rules}
    assert {
        "LOW_DATA_COMPLETENESS",
        "VALIDATION_ERRORS",
        "CONFLICTING_FINANCIAL_INPUTS",
        "LOW_VERIFIED_RATIO_SHARE",
        "MISSING_FINANCIAL_PERIODS",
    } <= codes


def test_industry_label_never_changes_industry_rule() -> None:
    first = complete_features()
    second = complete_features()
    for features in (first, second):
        features.domain_status = "VERIFIED"
        features.domain_confidence = Decimal("0.9")
    assert score_industry_context(first) == score_industry_context(second)


def test_interest_coverage_level_suppresses_decline() -> None:
    selected = suppress_overlaps(
        {
            "LOW_INTEREST_COVERAGE_ALERT": anomaly("LOW_INTEREST_COVERAGE_ALERT"),
            "DECLINING_INTEREST_COVERAGE": anomaly("DECLINING_INTEREST_COVERAGE"),
        }
    )
    assert set(selected) == {"LOW_INTEREST_COVERAGE_ALERT"}


def test_score_clamping() -> None:
    assert clamp_score(Decimal("120")) == Decimal("100.00")
    assert clamp_score(Decimal("-20")) == Decimal("0.00")


def test_review_input_prevents_verified_status() -> None:
    features = complete_features()
    source = features.ratios["interest_coverage"]
    features.ratios["interest_coverage"] = MetricFeature(
        source.name,
        source.value,
        "NEEDS_REVIEW",
        source.confidence,
        source.source_id,
        source.source_role,
    )
    assert score_credit(features).status == CreditAssessmentStatus.NEEDS_REVIEW


def test_confidence_does_not_exceed_critical_component() -> None:
    features = complete_features()
    source = features.ratios["interest_coverage"]
    features.ratios["interest_coverage"] = MetricFeature(
        source.name,
        source.value,
        source.status,
        Decimal("0.6"),
        source.source_id,
        source.source_role,
    )
    result = score_credit(features)
    repayment = next(
        item for item in result.components if item.component.value == "REPAYMENT_CAPACITY"
    )
    assert result.confidence <= repayment.confidence


def test_low_data_quality_reduces_assessment_confidence() -> None:
    high = complete_features()
    low = complete_features()
    low.completeness = Decimal("0.4")
    low.validation_errors = 2
    low.verified_ratio_share = Decimal("0.4")
    low.missing_period_count = 2
    assert score_credit(low).confidence < score_credit(high).confidence
