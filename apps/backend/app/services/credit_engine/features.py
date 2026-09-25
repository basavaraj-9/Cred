from __future__ import annotations

# ruff: noqa: E501
from collections.abc import Sequence
from decimal import Decimal
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company_profile import CompanyProfile
from app.models.domain_classification import DomainClassification
from app.models.enums import (
    ClassificationStatus,
    FinancialScope,
    NormalizationStatus,
    RatioStatus,
    ValidationStatus,
)
from app.models.financial_analysis import (
    FinancialAnalysisRun,
    FinancialRatio,
    FinancialValidationIssue,
    NormalizedFinancialValue,
)
from app.models.financial_trend import FinancialAnomaly, FinancialTrend, FinancialTrendRun
from app.services.credit_engine.schemas import (
    AnomalyFeature,
    CreditFeatures,
    InputRef,
    MetricFeature,
    TrendFeature,
)
from app.services.financial_engine.trend_series import period_year

FEATURE_BUILDER_VERSION = "credit_feature_builder_v1"
CORE_FIELDS = {
    "revenue",
    "profit_after_tax",
    "total_assets",
    "total_equity",
    "total_debt",
    "cash_flow_from_operations",
}


T = TypeVar("T")


def _latest_by_period(rows: Sequence[T], name_attribute: str, year_attribute: str) -> dict[str, T]:
    selected: dict[str, T] = {}
    for row in rows:
        name = str(getattr(row, name_attribute))
        existing = selected.get(name)
        try:
            row_year = period_year(str(getattr(row, year_attribute)))
        except ValueError:
            continue
        if existing is None or row_year > period_year(str(getattr(existing, year_attribute))):
            selected[name] = row
    return selected


def build_credit_features(
    session: Session, day8: FinancialAnalysisRun, day9: FinancialTrendRun, scope: FinancialScope
) -> CreditFeatures:
    features = CreditFeatures(scope=scope)
    ratio_rows = list(
        session.scalars(
            select(FinancialRatio).where(
                FinancialRatio.run_id == day8.id, FinancialRatio.statement_scope == scope
            )
        ).all()
    )
    selected_ratios = _latest_by_period(ratio_rows, "ratio_name", "fiscal_year")
    for name, ratio_row in selected_ratios.items():
        role = f"ratio:{name}"
        features.ratios[name] = MetricFeature(
            name,
            ratio_row.ratio_value,
            ratio_row.status.value,
            Decimal(str(ratio_row.confidence_score)),
            ratio_row.id,
            role,
        )
        features.input_refs.append(InputRef(role, "financial_ratio", ratio_row.id))

    value_rows = list(
        session.scalars(
            select(NormalizedFinancialValue).where(
                NormalizedFinancialValue.run_id == day8.id,
                NormalizedFinancialValue.statement_scope == scope,
                NormalizedFinancialValue.canonical_name.in_(CORE_FIELDS),
            )
        ).all()
    )
    selected_values = _latest_by_period(value_rows, "canonical_name", "fiscal_year")
    for name, value_row in selected_values.items():
        role = f"value:{name}"
        features.values[name] = MetricFeature(
            name,
            value_row.normalized_value,
            value_row.normalization_status.value,
            Decimal(str(value_row.normalization_confidence)),
            value_row.id,
            role,
        )
        features.input_refs.append(InputRef(role, "normalized_financial_value", value_row.id))
    available_core = sum(
        1
        for item in features.values.values()
        if item.value is not None
        and item.status
        in {NormalizationStatus.NORMALIZED.value, NormalizationStatus.NEEDS_REVIEW.value}
    )
    features.completeness = Decimal(available_core) / Decimal(len(CORE_FIELDS))

    trend_rows = list(
        session.scalars(
            select(FinancialTrend).where(
                FinancialTrend.run_id == day9.id, FinancialTrend.statement_scope == scope
            )
        ).all()
    )
    for name, trend_row in _latest_by_period(trend_rows, "metric_name", "end_fiscal_year").items():
        role = f"trend:{name}"
        features.trends[name] = TrendFeature(
            name,
            trend_row.trend_direction.value,
            trend_row.status.value,
            Decimal(str(trend_row.confidence_score)),
            len(trend_row.missing_periods or []),
            trend_row.id,
            role,
            "|".join(
                (
                    str(trend_row.start_value),
                    str(trend_row.end_value),
                    str(trend_row.absolute_change),
                    str(trend_row.percentage_change),
                    str(trend_row.cagr),
                    str(trend_row.percentage_point_change),
                    str(trend_row.state_transition),
                    str(trend_row.series),
                )
            ),
        )
        features.input_refs.append(InputRef(role, "financial_trend", trend_row.id))
    features.missing_period_count = sum(item.missing_periods for item in features.trends.values())

    anomalies = session.scalars(
        select(FinancialAnomaly).where(
            FinancialAnomaly.run_id == day9.id, FinancialAnomaly.statement_scope == scope
        )
    ).all()
    for anomaly_row in anomalies:
        role = f"anomaly:{anomaly_row.anomaly_type}"
        features.anomalies[anomaly_row.anomaly_type] = AnomalyFeature(
            anomaly_row.anomaly_type,
            anomaly_row.severity.value,
            anomaly_row.status.value,
            Decimal(str(anomaly_row.confidence_score)),
            anomaly_row.id,
            role,
            "|".join(
                (
                    anomaly_row.start_fiscal_year,
                    anomaly_row.end_fiscal_year,
                    str(anomaly_row.persistence_count),
                    anomaly_row.rule_version,
                )
            ),
        )
        features.input_refs.append(InputRef(role, "financial_anomaly", anomaly_row.id))

    issues = session.scalars(
        select(FinancialValidationIssue).where(
            FinancialValidationIssue.run_id == day8.id,
            FinancialValidationIssue.statement_scope == scope,
        )
    ).all()
    features.validation_errors = sum(issue.status == ValidationStatus.FAIL for issue in issues)
    features.conflicting_inputs = sum(
        item.normalization_status
        in {NormalizationStatus.CONFLICTING, NormalizationStatus.CURRENCY_MISMATCH}
        for item in value_rows
    )
    eligible_ratios = [
        item for item in selected_ratios.values() if isinstance(item, FinancialRatio)
    ]
    features.verified_ratio_share = Decimal(
        sum(item.status == RatioStatus.VERIFIED for item in eligible_ratios)
    ) / Decimal(len(eligible_ratios) or 1)
    critical_names = {
        "current_ratio",
        "debt_to_equity",
        "interest_coverage",
        "debt_to_ebitda",
        "operating_cash_flow_to_debt",
    }
    features.critical_conflict = (
        any(
            item.status == RatioStatus.CONFLICTING and item.ratio_name in critical_names
            for item in eligible_ratios
        )
        or features.conflicting_inputs > 0
    )

    profile = session.scalar(
        select(CompanyProfile)
        .where(CompanyProfile.document_id == day8.document_id)
        .order_by(CompanyProfile.created_at.desc())
    )
    if profile:
        features.profile_status = profile.status.value
        features.profile_confidence = Decimal(str(profile.overall_confidence))
        features.input_refs.append(InputRef("company_profile", "company_profile", profile.id))
        domain = session.scalar(
            select(DomainClassification)
            .where(DomainClassification.company_profile_id == profile.id)
            .order_by(DomainClassification.created_at.desc())
        )
        if domain:
            features.domain_status = domain.status.value
            features.domain_confidence = Decimal(str(domain.overall_confidence))
            features.input_refs.append(
                InputRef("domain_classification", "domain_classification", domain.id)
            )
            if domain.status != ClassificationStatus.VERIFIED:
                features.domain_status = domain.status.value
    return features
