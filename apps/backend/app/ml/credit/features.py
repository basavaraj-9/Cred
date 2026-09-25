from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.credit.feature_schema import (
    FEATURE_BUILDER_VERSION,
    FEATURE_SCHEMA_VERSION,
    feature_schema,
    validate_features,
)
from app.models.company_profile import CompanyProfile
from app.models.credit import CreditAssessment, CreditSubscore
from app.models.credit_ml import CreditMLFeatureSnapshot, CreditMLFeatureSource, CreditMLObservation
from app.models.domain_classification import DomainClassification
from app.models.enums import ClassificationStatus, NormalizationStatus, RatioStatus, TrendStatus
from app.models.financial_analysis import (
    FinancialAnalysisRun,
    FinancialRatio,
    FinancialValidationIssue,
    NormalizedFinancialValue,
)
from app.models.financial_trend import FinancialAnomaly, FinancialTrend, FinancialTrendRun
from app.services.financial_engine.trend_series import period_year

RATIOS = (
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
)
VALUES = (
    "revenue",
    "profit_after_tax",
    "total_assets",
    "total_equity",
    "total_debt",
    "cash_flow_from_operations",
    "trade_receivables",
    "inventory",
)
TRENDS = (
    "revenue",
    "profit_after_tax",
    "total_debt",
    "ebitda_margin",
    "net_profit_margin",
    "interest_coverage",
)
ANOMALIES = (
    "PERSISTENT_REVENUE_DECLINE",
    "PERSISTENT_NET_LOSS",
    "NEGATIVE_OPERATING_CASH_FLOW",
    "PERSISTENT_NEGATIVE_OPERATING_CASH_FLOW",
    "PROFIT_CASH_FLOW_DIVERGENCE",
    "RISING_LEVERAGE",
    "RECEIVABLES_OUTPACING_REVENUE",
    "INVENTORY_OUTPACING_REVENUE",
    "EBITDA_MARGIN_COMPRESSION",
    "NET_MARGIN_COMPRESSION",
)


def _number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _eligible_period(period: str, as_of: str) -> bool:
    try:
        return period_year(period) <= period_year(as_of)
    except ValueError:
        return False


def _source_kwargs(source_type: str, source_id: UUID) -> dict[str, UUID | None]:
    names = {
        "normalized_financial_value": "normalized_financial_value_id",
        "financial_ratio": "financial_ratio_id",
        "financial_trend": "financial_trend_id",
        "financial_anomaly": "financial_anomaly_id",
        "credit_assessment": "credit_assessment_id",
        "company_profile": "company_profile_id",
        "domain_classification": "domain_classification_id",
    }
    result: dict[str, UUID | None] = {name: None for name in names.values()}
    result[names[source_type]] = source_id
    return result


def build_feature_snapshot(
    session: Session, observation: CreditMLObservation, feature_group: str = "ANOMALY_ENRICHED_V1"
) -> CreditMLFeatureSnapshot:
    schema = feature_schema()
    enabled = set(schema["feature_groups"].get(feature_group, []))
    if not enabled:
        raise ValueError(f"Unknown credit feature group: {feature_group}")
    cutoff = observation.feature_cutoff_timestamp
    features: dict[str, object] = {"statement_scope": None}
    sources: dict[str, tuple[str, UUID, object]] = {}
    day8 = (
        session.scalar(
            select(FinancialAnalysisRun)
            .where(
                FinancialAnalysisRun.document_id == observation.document_id,
                FinancialAnalysisRun.created_at <= cutoff,
            )
            .order_by(FinancialAnalysisRun.created_at.desc())
        )
        if observation.document_id
        else None
    )
    day9 = (
        session.scalar(
            select(FinancialTrendRun)
            .where(
                FinancialTrendRun.document_id == observation.document_id,
                FinancialTrendRun.created_at <= cutoff,
            )
            .order_by(FinancialTrendRun.created_at.desc())
        )
        if observation.document_id
        else None
    )
    if "ratios" in enabled:
        for name in RATIOS:
            features[name] = None
            features[f"{name}_confidence"] = None
        if day8:
            ratio_rows = session.scalars(
                select(FinancialRatio)
                .where(FinancialRatio.run_id == day8.id, FinancialRatio.created_at <= cutoff)
                .order_by(FinancialRatio.fiscal_year.desc())
            ).all()
            for ratio_row in ratio_rows:
                if (
                    ratio_row.ratio_name not in RATIOS
                    or features[ratio_row.ratio_name] is not None
                    or not _eligible_period(ratio_row.fiscal_year, observation.as_of_fiscal_year)
                ):
                    continue
                if ratio_row.status == RatioStatus.VERIFIED:
                    features[ratio_row.ratio_name] = _number(ratio_row.ratio_value)
                    features[f"{ratio_row.ratio_name}_confidence"] = ratio_row.confidence_score
                    features["statement_scope"] = ratio_row.statement_scope.value
                    sources[ratio_row.ratio_name] = (
                        "financial_ratio",
                        ratio_row.id,
                        ratio_row.created_at,
                    )
    if "financial_values" in enabled:
        for name in VALUES:
            features[name] = None
            features[f"{name}_confidence"] = None
        if day8:
            value_rows = session.scalars(
                select(NormalizedFinancialValue)
                .where(
                    NormalizedFinancialValue.run_id == day8.id,
                    NormalizedFinancialValue.created_at <= cutoff,
                )
                .order_by(NormalizedFinancialValue.fiscal_year.desc())
            ).all()
            for value_row in value_rows:
                if (
                    value_row.canonical_name not in VALUES
                    or features[value_row.canonical_name] is not None
                    or not _eligible_period(value_row.fiscal_year, observation.as_of_fiscal_year)
                ):
                    continue
                if value_row.normalization_status == NormalizationStatus.NORMALIZED:
                    features[value_row.canonical_name] = _number(value_row.normalized_value)
                    features[f"{value_row.canonical_name}_confidence"] = (
                        value_row.normalization_confidence
                    )
                    features["statement_scope"] = value_row.statement_scope.value
                    sources[value_row.canonical_name] = (
                        "normalized_financial_value",
                        value_row.id,
                        value_row.created_at,
                    )
    if "trends" in enabled:
        for name in TRENDS:
            features[f"trend_{name}_direction"] = None
            features[f"trend_{name}_cagr"] = None
        if day9:
            trend_rows = session.scalars(
                select(FinancialTrend).where(
                    FinancialTrend.run_id == day9.id, FinancialTrend.created_at <= cutoff
                )
            ).all()
            for trend_row in trend_rows:
                if (
                    trend_row.metric_name not in TRENDS
                    or not _eligible_period(
                        trend_row.end_fiscal_year, observation.as_of_fiscal_year
                    )
                    or trend_row.status != TrendStatus.VERIFIED
                ):
                    continue
                features[f"trend_{trend_row.metric_name}_direction"] = (
                    trend_row.trend_direction.value
                )
                features[f"trend_{trend_row.metric_name}_cagr"] = _number(trend_row.cagr)
                sources[f"trend_{trend_row.metric_name}_direction"] = (
                    "financial_trend",
                    trend_row.id,
                    trend_row.created_at,
                )
    if "anomalies" in enabled:
        for name in ANOMALIES:
            features[f"anomaly_{name.lower()}"] = 0
        if day9:
            anomaly_rows = session.scalars(
                select(FinancialAnomaly).where(
                    FinancialAnomaly.run_id == day9.id, FinancialAnomaly.created_at <= cutoff
                )
            ).all()
            for anomaly_row in anomaly_rows:
                if anomaly_row.anomaly_type in ANOMALIES and _eligible_period(
                    anomaly_row.end_fiscal_year, observation.as_of_fiscal_year
                ):
                    key = f"anomaly_{anomaly_row.anomaly_type.lower()}"
                    features[key] = 1
                    sources[key] = (
                        "financial_anomaly",
                        anomaly_row.id,
                        anomaly_row.created_at,
                    )
    if "data_quality" in enabled:
        features.update(
            {
                "financial_completeness": None,
                "validation_error_count": 0,
                "review_input_count": 0,
                "conflict_count": 0,
            }
        )
        if day8:
            values = session.scalars(
                select(NormalizedFinancialValue).where(
                    NormalizedFinancialValue.run_id == day8.id,
                    NormalizedFinancialValue.created_at <= cutoff,
                )
            ).all()
            available_value_names = {
                row.canonical_name
                for row in values
                if row.canonical_name in VALUES and row.normalized_value is not None
            }
            features["financial_completeness"] = len(available_value_names) / len(VALUES)
            features["review_input_count"] = sum(
                row.normalization_status == NormalizationStatus.NEEDS_REVIEW for row in values
            )
            features["conflict_count"] = sum(
                row.normalization_status
                in {NormalizationStatus.CONFLICTING, NormalizationStatus.CURRENCY_MISMATCH}
                for row in values
            )
            features["validation_error_count"] = len(
                session.scalars(
                    select(FinancialValidationIssue).where(
                        FinancialValidationIssue.run_id == day8.id,
                        FinancialValidationIssue.created_at <= cutoff,
                        FinancialValidationIssue.status == "FAIL",
                    )
                ).all()
            )
    if "business_metadata" in enabled:
        features.update({"sector": None, "industry": None, "domain": None})
        profile = (
            session.scalar(
                select(CompanyProfile)
                .where(
                    CompanyProfile.document_id == observation.document_id,
                    CompanyProfile.created_at <= cutoff,
                )
                .order_by(CompanyProfile.created_at.desc())
            )
            if observation.document_id
            else None
        )
        domain = (
            session.scalar(
                select(DomainClassification)
                .where(
                    DomainClassification.company_profile_id == profile.id,
                    DomainClassification.created_at <= cutoff,
                )
                .order_by(DomainClassification.created_at.desc())
            )
            if profile
            else None
        )
        if domain and domain.status == ClassificationStatus.VERIFIED:
            features.update(
                {"sector": domain.sector, "industry": domain.industry, "domain": domain.domain}
            )
            for name in ("sector", "industry", "domain"):
                sources[name] = ("domain_classification", domain.id, domain.created_at)
    if "rule_score" in enabled:
        features["credit_score"] = None
        assessment = (
            session.scalar(
                select(CreditAssessment)
                .where(
                    CreditAssessment.document_id == observation.document_id,
                    CreditAssessment.created_at <= cutoff,
                )
                .order_by(CreditAssessment.created_at.desc())
            )
            if observation.document_id
            else None
        )
        if assessment and assessment.overall_score is not None:
            features["credit_score"] = _number(assessment.overall_score)
            sources["credit_score"] = ("credit_assessment", assessment.id, assessment.created_at)
            for subscore in session.scalars(
                select(CreditSubscore).where(CreditSubscore.credit_assessment_id == assessment.id)
            ).all():
                key = f"credit_subscore_{subscore.component_name.value.lower()}"
                features[key] = _number(subscore.normalized_score)
                sources[key] = ("credit_assessment", assessment.id, assessment.created_at)
    validate_features(features, feature_group)
    canonical = json.dumps(
        {
            "observation_date": observation.observation_date.isoformat(),
            "cutoff": cutoff.isoformat(),
            "builder": FEATURE_BUILDER_VERSION,
            "schema": FEATURE_SCHEMA_VERSION,
            "group": feature_group,
            "features": features,
            "sources": sorted(
                (name, kind, str(source_id), str(available))
                for name, (kind, source_id, available) in sources.items()
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    input_hash = hashlib.sha256(canonical.encode()).hexdigest()
    existing = session.scalar(
        select(CreditMLFeatureSnapshot).where(
            CreditMLFeatureSnapshot.observation_id == observation.id,
            CreditMLFeatureSnapshot.feature_builder_version == FEATURE_BUILDER_VERSION,
            CreditMLFeatureSnapshot.feature_schema_version == FEATURE_SCHEMA_VERSION,
            CreditMLFeatureSnapshot.feature_group == feature_group,
            CreditMLFeatureSnapshot.input_hash == input_hash,
        )
    )
    if existing:
        return existing
    snapshot = CreditMLFeatureSnapshot(
        observation_id=observation.id,
        company_id=observation.company_id,
        observation_date=observation.observation_date,
        feature_cutoff_timestamp=cutoff,
        feature_builder_version=FEATURE_BUILDER_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_group=feature_group,
        features_json=features,
        feature_count=sum(value is not None for value in features.values()),
        missing_feature_count=sum(value is None for value in features.values()),
        input_hash=input_hash,
        availability_complete=False,
    )
    session.add(snapshot)
    session.flush()
    for name, (kind, source_id, available) in sources.items():
        session.add(
            CreditMLFeatureSource(
                feature_snapshot_id=snapshot.id,
                feature_name=name,
                source_available_at=available,
                **_source_kwargs(kind, source_id),
            )
        )
    session.flush()
    return snapshot
