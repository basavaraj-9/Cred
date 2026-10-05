from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID
from xml.sax.saxutils import escape

from jsonschema import validate  # type: ignore[import-untyped]
from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import (  # type: ignore[import-untyped]
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import desc, func, or_, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.analysis_job import AnalysisJob
from app.models.company import Company
from app.models.company_profile import CompanyProfile
from app.models.credit import CreditAssessment, CreditRuleResult, CreditSubscore
from app.models.credit_fusion import CreditFusionExperiment
from app.models.decision import (
    CreditDecisionGate,
    CreditDecisionSupport,
    CreditLimitPreparation,
    CreditPolicyException,
)
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.domain_classification import DomainClassification
from app.models.enums import IdentityMatchStatus
from app.models.extracted_field import ExtractedField
from app.models.financial import FinancialLineItem, FinancialStatement
from app.models.financial_analysis import FinancialRatio, NormalizedFinancialValue
from app.models.financial_trend import FinancialAnomaly, FinancialTrend
from app.models.five_cs import FiveCsAssessment, FiveCsEvidence, FiveCsReviewItem, FiveCsSection
from app.models.recommendation import CreditRecommendationPreparation, FiveCsRefreshRun
from app.models.reporting import (
    GeneratedReport,
    ReportArtifact,
    ReportFinalizationAction,
    ReportSnapshot,
    ReportSourceLink,
)
from app.models.research import ResearchFinding, ResearchRun, ResearchSource
from app.models.review import (
    CreditCommitteePackage,
    CreditHumanDecision,
    CreditInformationRequest,
    CreditReviewCase,
    CreditReviewEvidenceAcknowledgement,
)
from app.models.stock import (
    ListedCompany,
    MarketDataRun,
    PeerGroup,
    PeerGroupMember,
    StockListing,
    StockPrice,
)
from app.models.stock_analytics import (
    SectorMetric,
    SectorMetricRun,
    StockFeature,
    StockFeatureRun,
    StockFundamental,
    StockFundamentalRun,
    StockValuation,
    StockValuationRun,
)
from app.models.stock_intelligence import (
    StockIntelligenceComponent,
    StockIntelligenceComponentInput,
    StockIntelligenceRun,
    StockRankingMember,
    StockRankingRun,
)
from app.models.stock_ml import StockMLDataset, StockMLDatasetRow, StockMLModel, StockMLPrediction
from app.models.stock_monitoring import (
    StockFeatureDrift,
    StockGovernanceAssessment,
    StockModelMonitoring,
    StockMonitoringFinding,
    StockMonitoringRun,
    StockProviderMonitoring,
    StockRankingMonitoring,
    StockScoreMonitoring,
)
from app.models.stock_validation import (
    StockIntelligenceAblationMetric,
    StockIntelligenceAblationRun,
    StockIntelligenceSensitivityRun,
    StockIntelligenceValidationPeriod,
    StockIntelligenceValidationRun,
)
from app.models.user import User
from app.services.company_profile.extractor import compare_identity

REPORT_TYPE = "COMPANY_INTELLIGENCE_360"
REPORT_VERSION = "company_intelligence_360_v1"
POLICY_VERSION = "company_intelligence_report_policy_v1"
SCHEMA_VERSION = "company_intelligence_360_schema_v1"
RENDERER_VERSION = "company_intelligence_renderer_v1"
CREDIT_DISCLAIMER = (
    "This report supports credit analysis and human review. It is not an autonomous "
    "lending decision."
)
STOCK_DISCLAIMER = (
    "Stock Intelligence outputs are research analytics only and are not investment recommendations."
)
VALIDATION_DISCLAIMER = (
    "Historical relationships based on development data do not guarantee future outcomes."
)
SEPARATION = (
    "Creditworthiness and equity-market analytical strength are separate assessments and "
    "should not be interpreted as substitutes for one another."
)


def _now() -> datetime:
    return datetime.now(UTC)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (UUID, date, datetime, Decimal)):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _row(value: object | None) -> dict[str, Any] | None:
    if value is None:
        return None
    inspected = cast(Any, sa_inspect(value))
    return {item.key: _jsonable(getattr(value, item.key)) for item in inspected.mapper.column_attrs}


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class CompanyIntelligenceReportService:
    def __init__(self, session: Session, storage_root: Path):
        self.s = session
        self.storage_root = storage_root.resolve()
        directory = Path(__file__).parent
        self.policy = json.loads(
            (directory / "company_intelligence_report_policy_v1.json").read_text("utf-8")
        )
        self.schema = json.loads(
            (directory / "company_intelligence_360_schema_v1.json").read_text("utf-8")
        )

    def _user(self, user_id: UUID) -> User:
        user = self.s.get(User, user_id)
        if user is None or not user.is_active:
            raise AppError("REPORT_ACTOR_NOT_AUTHORIZED", "Active report actor not found", 403)
        authority = json.loads(
            (Path(__file__).parent / "report_authority_policy_v1.json").read_text("utf-8")
        )
        if user.reviewer_role not in authority["download_roles"]:
            raise AppError("REPORT_ACTOR_NOT_AUTHORIZED", "Role cannot access reports", 403)
        return user

    def _cutoff(self, as_of: date) -> datetime:
        return datetime.combine(as_of, time.max, tzinfo=UTC)

    def _latest(self, model: Any, *criteria: Any, order: Any | None = None) -> Any | None:
        query = select(model).where(*criteria)
        if hasattr(model, "created_at") and hasattr(self, "_as_of_cutoff"):
            query = query.where(model.created_at <= self._as_of_cutoff)
            if hasattr(model, "updated_at"):
                query = query.where(model.updated_at <= self._as_of_cutoff)
        target = order if order is not None else model.created_at
        return self.s.scalar(query.order_by(desc(target), desc(model.id)).limit(1))

    def _rows(self, model: Any, *criteria: Any, order: Any | None = None) -> list[Any]:
        query = select(model).where(*criteria)
        if hasattr(model, "created_at") and hasattr(self, "_as_of_cutoff"):
            query = query.where(model.created_at <= self._as_of_cutoff)
            if hasattr(model, "updated_at"):
                query = query.where(model.updated_at <= self._as_of_cutoff)
        if order is not None:
            query = query.order_by(order, model.id)
        else:
            query = query.order_by(model.id)
        limit = int(self.policy["max_records_per_collection"])
        records = list(self.s.scalars(query.limit(limit + 1)))
        if len(records) > limit:
            raise AppError(
                "REPORT_SCOPE_TOO_LARGE",
                "Report source limit exceeded; select a narrower analysis job",
                422,
            )
        return records

    def _section(
        self,
        data: Any,
        *,
        applicable: bool = True,
        review: bool = False,
        partial: bool = False,
    ) -> dict[str, Any]:
        if not applicable:
            status = "NOT_APPLICABLE"
        elif review:
            status = "NEEDS_REVIEW"
        elif data in (None, [], {}):
            status = "UNAVAILABLE"
        elif partial:
            status = "PARTIAL"
        else:
            status = "AVAILABLE"
        return {"status": status, "data": _jsonable(data)}

    def _listed_company(self, company: Company) -> ListedCompany | None:
        names = {company.legal_name.strip().lower()}
        if company.display_name:
            names.add(company.display_name.strip().lower())
        return self.s.scalar(
            select(ListedCompany)
            .where(
                or_(
                    func.lower(ListedCompany.legal_name).in_(names),
                    func.lower(ListedCompany.canonical_name).in_(names),
                )
            )
            .order_by(ListedCompany.id)
            .limit(1)
        )

    def _resolve(
        self,
        company: Company,
        analysis_job_id: UUID | None,
        as_of: date,
        include_credit: bool,
        include_stock: bool,
    ) -> tuple[dict[str, Any], list[tuple[str, UUID, str, dict[str, Any] | None]]]:
        cutoff = self._cutoff(as_of)
        self._as_of_cutoff = cutoff
        links: list[tuple[str, UUID, str, dict[str, Any] | None]] = []

        def link(source_type: str, value: Any, role: str, metadata: dict[str, Any] | None = None):
            if value is not None:
                links.append((source_type, value.id, role, metadata))

        job = (
            self.s.get(AnalysisJob, analysis_job_id)
            if analysis_job_id
            else self._latest(
                AnalysisJob,
                AnalysisJob.company_id == company.id,
                AnalysisJob.created_at <= cutoff,
            )
        )
        if job is not None and job.company_id != company.id:
            raise AppError(
                "REPORT_ANALYSIS_JOB_MISMATCH", "Analysis job belongs to another company", 409
            )
        if job is not None and job.created_at > cutoff:
            raise AppError(
                "REPORT_FUTURE_ANALYSIS_JOB", "Analysis job is after report as-of date", 409
            )
        documents = self._rows(
            Document,
            Document.company_id == company.id,
            Document.created_at <= cutoff,
            *([Document.analysis_job_id == analysis_job_id] if analysis_job_id else []),
            order=Document.created_at,
        )
        document = documents[-1] if documents else None
        profile = (
            self._latest(
                CompanyProfile,
                CompanyProfile.document_id.in_([item.id for item in documents]),
                CompanyProfile.created_at <= cutoff,
            )
            if documents
            else None
        )
        domain = (
            self._latest(
                DomainClassification,
                DomainClassification.company_profile_id == profile.id,
                DomainClassification.created_at <= cutoff,
            )
            if profile
            else None
        )
        pages = (
            self._rows(
                DocumentPage,
                DocumentPage.document_id.in_([item.id for item in documents]),
                order=DocumentPage.page_number,
            )
            if documents
            else []
        )
        fields = (
            self._rows(ExtractedField, ExtractedField.company_profile_id == profile.id)
            if profile
            else []
        )
        statements = (
            self._rows(
                FinancialStatement,
                FinancialStatement.document_id.in_([item.id for item in documents]),
                FinancialStatement.created_at <= cutoff,
                or_(
                    FinancialStatement.period_end.is_(None), FinancialStatement.period_end <= as_of
                ),
            )
            if documents
            else []
        )
        financial_values = (
            self._rows(
                NormalizedFinancialValue,
                NormalizedFinancialValue.document_id.in_([item.id for item in documents]),
                NormalizedFinancialValue.created_at <= cutoff,
            )
            if documents
            else []
        )
        line_items = (
            self._rows(
                FinancialLineItem,
                FinancialLineItem.document_id.in_([item.id for item in documents]),
                FinancialLineItem.created_at <= cutoff,
                or_(FinancialLineItem.period_end.is_(None), FinancialLineItem.period_end <= as_of),
            )
            if documents
            else []
        )
        ratios = (
            self._rows(
                FinancialRatio,
                FinancialRatio.document_id.in_([item.id for item in documents]),
                FinancialRatio.created_at <= cutoff,
            )
            if documents
            else []
        )
        trends = (
            self._rows(
                FinancialTrend,
                FinancialTrend.document_id.in_([item.id for item in documents]),
                FinancialTrend.created_at <= cutoff,
            )
            if documents
            else []
        )
        anomalies = (
            self._rows(
                FinancialAnomaly,
                FinancialAnomaly.document_id.in_([item.id for item in documents]),
                FinancialAnomaly.created_at <= cutoff,
            )
            if documents
            else []
        )
        credit = (
            self._latest(
                CreditAssessment,
                CreditAssessment.company_id == company.id,
                CreditAssessment.created_at <= cutoff,
                *([CreditAssessment.analysis_job_id == analysis_job_id] if analysis_job_id else []),
            )
            if include_credit
            else None
        )
        subscores = (
            self._rows(CreditSubscore, CreditSubscore.credit_assessment_id == credit.id)
            if credit
            else []
        )
        reasons = (
            self._rows(CreditRuleResult, CreditRuleResult.credit_assessment_id == credit.id)
            if credit
            else []
        )
        # Select one applicable dependency chain. A newer timestamp cannot make a
        # run built against another profile/classification/credit input current.
        consistency_issues: list[dict[str, Any]] = []
        excluded_sources: list[dict[str, Any]] = []
        research = (
            self._latest(
                ResearchRun,
                ResearchRun.company_id == company.id,
                ResearchRun.company_profile_id == profile.id,
                ResearchRun.domain_classification_id == (domain.id if domain else None),
                ResearchRun.status.in_(("COMPLETED", "PARTIAL", "NEEDS_REVIEW")),
                order=ResearchRun.refresh_number,
            )
            if include_credit and profile
            else None
        )
        candidates = (
            self._rows(FiveCsAssessment, FiveCsAssessment.credit_assessment_id == credit.id)
            if include_credit and credit
            else []
        )
        applicable = []
        for candidate in candidates:
            valid = bool(
                profile
                and candidate.company_profile_id == profile.id
                and compare_identity(company.legal_name, profile.legal_name)
                == IdentityMatchStatus.MATCHED
                and candidate.domain_classification_id == (domain.id if domain else None)
            )
            refresh = self._latest(
                FiveCsRefreshRun,
                FiveCsRefreshRun.refreshed_five_cs_assessment_id == candidate.id,
            )
            if candidate.engine_version == "five_cs_engine_v2":
                valid = bool(
                    valid
                    and refresh
                    and research
                    and refresh.research_run_id == research.id
                    and refresh.input_hash == candidate.input_hash
                )
            if valid:
                applicable.append((bool(refresh), candidate))
            else:
                excluded_sources.append(
                    {
                        "source_type": "FIVE_CS",
                        "source_id": str(candidate.id),
                        "input_hash": candidate.input_hash,
                        "status": "SUPERSEDED_OR_STALE",
                    }
                )
        applicable.sort(
            key=lambda item: (item[0], item[1].created_at, str(item[1].id)), reverse=True
        )
        five = applicable[0][1] if applicable else None
        five_sections = (
            self._rows(FiveCsSection, FiveCsSection.five_cs_assessment_id == five.id)
            if five
            else []
        )
        # Even correctly linked imported records can contain contradictory states.
        # Exclude the entire assessment, not individual evidence or computed scores.
        if five and domain and _jsonable(domain.status) == "VERIFIED":
            unavailable = self.s.scalar(
                select(FiveCsEvidence.id)
                .where(
                    FiveCsEvidence.five_cs_section_id.in_([item.id for item in five_sections]),
                    FiveCsEvidence.observation_code == "CONDITIONS_DOMAIN_UNVERIFIED",
                )
                .limit(1)
            )
            missing = self._latest(
                FiveCsReviewItem,
                FiveCsReviewItem.five_cs_assessment_id == five.id,
                FiveCsReviewItem.reason_code == "DOMAIN_CLASSIFICATION_REVIEW_REQUIRED",
            )
            if unavailable or missing:
                consistency_issues.append(
                    {
                        "type": "DOMAIN_EVIDENCE_CONFLICT",
                        "status": "CONFLICTING",
                        "source_id": str(five.id),
                        "classification_id": str(domain.id),
                        "message": "Verified domain contradicts assessment; rebuild required.",
                    }
                )
                excluded_sources.append(
                    {
                        "source_type": "FIVE_CS",
                        "source_id": str(five.id),
                        "input_hash": five.input_hash,
                        "status": "STALE_REBUILD_REQUIRED",
                    }
                )
                five, five_sections = None, []
        if candidates and five is None:
            consistency_issues.append(
                {
                    "type": "STALE_FIVE_CS_LINEAGE",
                    "status": "NEEDS_REVIEW",
                    "message": "Stale source lineage; rebuild through the Five Cs service.",
                }
            )
        findings = (
            self._rows(ResearchFinding, ResearchFinding.research_run_id == research.id)
            if research
            else []
        )
        research_sources = (
            self._rows(ResearchSource, ResearchSource.research_run_id == research.id)
            if research
            else []
        )
        recommendation = (
            self._latest(
                CreditRecommendationPreparation,
                CreditRecommendationPreparation.five_cs_assessment_id == five.id,
                CreditRecommendationPreparation.credit_assessment_id == credit.id,
                CreditRecommendationPreparation.research_run_id == research.id,
            )
            if five and credit and research
            else None
        )
        support = (
            self._latest(
                CreditDecisionSupport,
                CreditDecisionSupport.recommendation_preparation_id == recommendation.id,
            )
            if recommendation
            else None
        )
        review = (
            self._latest(
                CreditReviewCase,
                CreditReviewCase.company_id == company.id,
                CreditReviewCase.decision_support_id == support.id,
                CreditReviewCase.created_at <= cutoff,
                *([CreditReviewCase.analysis_job_id == analysis_job_id] if analysis_job_id else []),
            )
            if include_credit and support
            else None
        )
        human = (
            self._latest(
                CreditHumanDecision,
                CreditHumanDecision.review_case_id == review.id,
                CreditHumanDecision.created_at <= cutoff,
            )
            if review
            else None
        )
        committee = (
            self._latest(
                CreditCommitteePackage,
                CreditCommitteePackage.review_case_id == review.id,
                CreditCommitteePackage.created_at <= cutoff,
            )
            if review
            else None
        )
        cam = self._latest(
            GeneratedReport,
            GeneratedReport.company_id == company.id,
            GeneratedReport.report_type == "CAM",
            GeneratedReport.generated_at <= cutoff,
        )
        if not include_credit:
            cam = None

        listed = self._listed_company(company) if include_stock else None
        listing = (
            self.s.scalar(
                select(StockListing)
                .where(StockListing.listed_company_id == listed.id)
                .order_by(desc(StockListing.is_primary), StockListing.exchange)
                .limit(1)
            )
            if listed
            else None
        )
        peer = self._latest(
            PeerGroup,
            PeerGroup.source_company_id == company.id,
            PeerGroup.created_at <= cutoff,
        )
        if not include_stock:
            peer = None
        peer_members = (
            self._rows(PeerGroupMember, PeerGroupMember.peer_group_id == peer.id) if peer else []
        )
        price = (
            self._latest(
                StockPrice,
                StockPrice.stock_listing_id == listing.id,
                StockPrice.trade_date <= as_of,
                order=StockPrice.trade_date,
            )
            if listing
            else None
        )
        market_run = self.s.get(MarketDataRun, price.market_data_run_id) if price else None
        fundamental_runs = (
            self._rows(
                StockFundamentalRun,
                StockFundamentalRun.listed_company_id == listed.id,
                StockFundamentalRun.availability_date <= as_of,
                order=StockFundamentalRun.period_end,
            )
            if listed
            else []
        )
        fundamentals = (
            self._rows(
                StockFundamental,
                StockFundamental.fundamental_run_id.in_([item.id for item in fundamental_runs]),
                StockFundamental.availability_date <= as_of,
                order=StockFundamental.period_end,
            )
            if fundamental_runs
            else []
        )
        valuation_run = (
            self._latest(
                StockValuationRun,
                StockValuationRun.stock_listing_id == listing.id,
                StockValuationRun.valuation_date <= as_of,
                order=StockValuationRun.valuation_date,
            )
            if listing
            else None
        )
        valuations = (
            self._rows(StockValuation, StockValuation.valuation_run_id == valuation_run.id)
            if valuation_run
            else []
        )
        relative_runs = (
            self._rows(SectorMetricRun, SectorMetricRun.as_of_date == valuation_run.valuation_date)
            if valuation_run
            else []
        )
        relative_metrics = (
            self._rows(
                SectorMetric,
                SectorMetric.listed_company_id == listed.id,
                SectorMetric.sector_metric_run_id.in_([item.id for item in relative_runs]),
            )
            if listed and relative_runs
            else []
        )
        feature_run = (
            self._latest(
                StockFeatureRun,
                StockFeatureRun.stock_listing_id == listing.id,
                StockFeatureRun.as_of_date <= as_of,
                order=StockFeatureRun.as_of_date,
            )
            if listing
            else None
        )
        features = (
            self._rows(StockFeature, StockFeature.feature_run_id == feature_run.id)
            if feature_run
            else []
        )
        score = (
            self._latest(
                StockIntelligenceRun,
                StockIntelligenceRun.stock_listing_id == listing.id,
                StockIntelligenceRun.as_of_date <= as_of,
                order=StockIntelligenceRun.as_of_date,
            )
            if listing
            else None
        )
        components = (
            self._rows(
                StockIntelligenceComponent,
                StockIntelligenceComponent.run_id == score.id,
                order=StockIntelligenceComponent.component_name,
            )
            if score
            else []
        )
        ranking_member = (
            self.s.scalar(
                select(StockRankingMember)
                .join(StockRankingRun)
                .where(
                    StockRankingMember.stock_listing_id == listing.id,
                    StockRankingRun.as_of_date <= as_of,
                    StockRankingRun.created_at <= cutoff,
                )
                .order_by(desc(StockRankingRun.as_of_date))
                .limit(1)
            )
            if listing
            else None
        )
        ranking_run = (
            self.s.get(StockRankingRun, ranking_member.ranking_run_id) if ranking_member else None
        )
        dataset_row = (
            self._latest(
                StockMLDatasetRow,
                StockMLDatasetRow.stock_listing_id == listing.id,
                StockMLDatasetRow.as_of_date <= as_of,
                order=StockMLDatasetRow.as_of_date,
            )
            if listing
            else None
        )
        prediction = (
            self.s.scalar(
                select(StockMLPrediction)
                .join(StockMLDatasetRow)
                .where(
                    StockMLDatasetRow.stock_listing_id == listing.id,
                    StockMLDatasetRow.as_of_date <= as_of,
                    StockMLPrediction.created_at <= cutoff,
                )
                .order_by(
                    StockMLDatasetRow.as_of_date.desc(),
                    StockMLPrediction.created_at.desc(),
                    StockMLPrediction.id,
                )
                .limit(1)
            )
            if listing
            else None
        )
        if prediction:
            dataset_row = self.s.get(StockMLDatasetRow, prediction.dataset_row_id)
        # The collection bound applies to each component's evidence. A score's
        # eleven components legitimately reference thousands of price observations
        # in total; the snapshot byte limit still bounds the combined export.
        component_inputs = [
            source
            for component in components
            for source in self._rows(
                StockIntelligenceComponentInput,
                StockIntelligenceComponentInput.component_id == component.id,
            )
        ]
        ml_model = (
            self.s.scalar(
                select(StockMLModel).where(
                    StockMLModel.ml_run_id == prediction.ml_run_id,
                    StockMLModel.created_at <= cutoff,
                )
            )
            if prediction
            else None
        )
        dataset = self.s.get(StockMLDataset, dataset_row.dataset_id) if dataset_row else None
        validation_run = self._latest(
            StockIntelligenceValidationRun,
            StockIntelligenceValidationRun.end_date <= as_of,
            order=StockIntelligenceValidationRun.end_date,
        )
        if not listing:
            validation_run = None
        validation_periods = (
            self._rows(
                StockIntelligenceValidationPeriod,
                StockIntelligenceValidationPeriod.validation_run_id == validation_run.id,
                StockIntelligenceValidationPeriod.as_of_date <= as_of,
                order=StockIntelligenceValidationPeriod.as_of_date,
            )
            if validation_run
            else []
        )
        ablations = (
            self._rows(
                StockIntelligenceAblationRun,
                StockIntelligenceAblationRun.validation_run_id == validation_run.id,
            )
            if validation_run
            else []
        )
        ablation_metrics = (
            self._rows(
                StockIntelligenceAblationMetric,
                StockIntelligenceAblationMetric.ablation_run_id.in_(
                    [item.id for item in ablations]
                ),
            )
            if ablations
            else []
        )
        sensitivities = (
            self._rows(
                StockIntelligenceSensitivityRun,
                StockIntelligenceSensitivityRun.validation_run_id == validation_run.id,
            )
            if validation_run
            else []
        )
        monitoring = self._latest(
            StockMonitoringRun,
            StockMonitoringRun.current_end_date <= as_of,
            order=StockMonitoringRun.current_end_date,
        )
        if not listing:
            monitoring = None
        monitoring_findings = (
            self._rows(
                StockMonitoringFinding,
                StockMonitoringFinding.monitoring_run_id == monitoring.id,
            )
            if monitoring
            else []
        )
        providers = (
            self._rows(
                StockProviderMonitoring,
                StockProviderMonitoring.monitoring_run_id == monitoring.id,
            )
            if monitoring
            else []
        )
        governance = (
            self._latest(
                StockGovernanceAssessment,
                StockGovernanceAssessment.monitoring_run_id == monitoring.id,
            )
            if monitoring
            else None
        )

        credit_details: dict[str, Any] = {}
        if support:
            for key, model in (
                ("policy_gates", CreditDecisionGate),
                ("policy_exceptions", CreditPolicyException),
                ("analytical_limits", CreditLimitPreparation),
            ):
                credit_details[key] = [
                    _row(item)
                    for item in self._rows(model, model.credit_decision_support_id == support.id)
                ]
            fusion = (
                self._latest(
                    CreditFusionExperiment,
                    CreditFusionExperiment.id == support.fusion_experiment_id,
                )
                if support.fusion_experiment_id
                else None
            )
            credit_details["fusion"] = _row(fusion)
        if review:
            for key, review_model in (
                ("information_requests", CreditInformationRequest),
                ("evidence_acknowledgements", CreditReviewEvidenceAcknowledgement),
            ):
                credit_details[key] = [
                    _row(item)
                    for item in self._rows(review_model, review_model.review_case_id == review.id)
                ]
        if five:
            credit_details["five_cs_evidence"] = [
                _row(item)
                for item in self._rows(
                    FiveCsEvidence,
                    FiveCsEvidence.five_cs_section_id.in_([item.id for item in five_sections]),
                )
            ]
            credit_details["five_cs_missing_information"] = [
                _row(item)
                for item in self._rows(
                    FiveCsReviewItem, FiveCsReviewItem.five_cs_assessment_id == five.id
                )
            ]
        monitoring_details = {}
        if monitoring:
            for key, monitoring_model in (
                ("feature_drift", StockFeatureDrift),
                ("prediction_drift", StockModelMonitoring),
                ("score_drift", StockScoreMonitoring),
                ("ranking_stability", StockRankingMonitoring),
            ):
                monitoring_details[key] = [
                    _row(item)
                    for item in self._rows(
                        monitoring_model, monitoring_model.monitoring_run_id == monitoring.id
                    )
                ]

        for item in documents:
            link("DOCUMENT", item, "SOURCE_DOCUMENT")
        for item in pages:
            link(
                "DOCUMENT_PAGE",
                item,
                "DOCUMENT_EVIDENCE",
                {
                    "document_id": str(item.document_id),
                    "page_number": item.page_number,
                    "snippet": item.text_content[:1000],
                },
            )
        for item in fields:
            link(
                "EXTRACTED_FIELD",
                item,
                "PROFILE_EVIDENCE",
                {
                    "document_id": str(item.document_id),
                    "page_number": item.page_number,
                    "snippet": item.evidence_text,
                },
            )
        for source_type, item in (
            ("ANALYSIS_JOB", job),
            ("LISTED_COMPANY", listed),
            ("STOCK_LISTING", listing),
            ("PEER_GROUP", peer),
            ("STOCK_PRICE", price),
            ("MARKET_DATA_RUN", market_run),
            ("CREDIT_DECISION_SUPPORT", support),
            ("STOCK_ML_DATASET", dataset),
            ("STOCK_ML_MODEL", ml_model),
            ("STOCK_GOVERNANCE", governance),
            ("CAM", cam),
        ):
            link(source_type, item, "SELECTED_INPUT")
        for item in relative_metrics:
            link("STOCK_RELATIVE_METRIC", item, "RELATIVE_VALUATION")
        for source_type, item, role in (
            ("COMPANY_PROFILE", profile, "COMPANY_PROFILE"),
            ("DOMAIN_CLASSIFICATION", domain, "CLASSIFICATION"),
            ("CREDIT_SCORE", credit, "CREDIT_ANALYSIS"),
            ("FIVE_CS", five, "FIVE_CS"),
            ("RESEARCH_RUN", research, "EXTERNAL_RESEARCH"),
            ("CREDIT_RECOMMENDATION", recommendation, "CREDIT_RECOMMENDATION"),
            ("HUMAN_REVIEW", review, "HUMAN_REVIEW"),
            ("HUMAN_DECISION", human, "HUMAN_DECISION"),
            ("STOCK_VALUATION", valuation_run, "STOCK_VALUATION"),
            ("STOCK_FEATURE", feature_run, "STOCK_FEATURES"),
            ("STOCK_ML_PREDICTION", prediction, "STOCK_ML_RESEARCH"),
            ("STOCK_INTELLIGENCE_SCORE", score, "STOCK_SCORE"),
            ("STOCK_RANKING", ranking_run, "STOCK_RANKING"),
            ("STOCK_VALIDATION", validation_run, "STOCK_VALIDATION"),
            ("STOCK_MONITORING", monitoring, "STOCK_MONITORING"),
        ):
            link(source_type, item, role)
        for item in financial_values:
            link("NORMALIZED_FINANCIAL", item, "FINANCIAL_EVIDENCE")
        for item in ratios:
            link("FINANCIAL_RATIO", item, "FINANCIAL_ANALYTICS")
        for item in trends:
            link("FINANCIAL_TREND", item, "FINANCIAL_ANALYTICS")
        for item in anomalies:
            link("FINANCIAL_ANOMALY", item, "FINANCIAL_ANALYTICS")
        for item in findings:
            link("RESEARCH_FINDING", item, "EXTERNAL_RESEARCH")
        for item in fundamental_runs:
            link("STOCK_FUNDAMENTAL", item, "STOCK_FUNDAMENTALS")

        credit_applicable = include_credit
        stock_applicable = include_stock and listed is not None
        financial_values.sort(
            key=lambda item: (
                item.fiscal_year,
                str(item.statement_scope),
                item.canonical_name,
                str(item.id),
            )
        )
        ratios.sort(
            key=lambda item: (
                str(getattr(item, "fiscal_year", "")),
                str(getattr(item, "ratio_code", "")),
                str(item.id),
            )
        )
        five_order = ("CHARACTER", "CAPACITY", "CAPITAL", "COLLATERAL", "CONDITIONS")
        five_sections.sort(key=lambda item: five_order.index(item.section))
        component_order = (
            "ML_SIGNAL",
            "VALUATION",
            "FUNDAMENTAL_QUALITY",
            "GROWTH",
            "PROFITABILITY",
            "BALANCE_SHEET",
            "MOMENTUM",
            "RISK",
            "PEER_RELATIVE",
            "SECTOR_RELATIVE",
            "DATA_QUALITY",
        )
        components.sort(key=lambda item: component_order.index(item.component_name))
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        anomalies.sort(
            key=lambda item: (severity_order.get(_jsonable(item.severity), 5), str(item.id))
        )
        conflicts: list[dict[str, Any]] = consistency_issues
        profile_snapshot = _row(profile)
        identity = compare_identity(company.legal_name, profile.legal_name if profile else None)
        if profile_snapshot and profile:
            profile_snapshot["recorded_identity_match_status"] = profile_snapshot[
                "identity_match_status"
            ]
            profile_snapshot["identity_match_status"] = identity.value
            if identity != IdentityMatchStatus.MATCHED:
                profile_snapshot["recorded_status"] = profile_snapshot["status"]
                profile_snapshot["status"] = "CONFLICTING" if profile.legal_name else "NEEDS_REVIEW"
        if profile and identity != IdentityMatchStatus.MATCHED:
            conflicts.append(
                {
                    "type": "COMPANY_NAME",
                    "source_a": company.legal_name,
                    "source_b": profile.legal_name,
                    "company_id": str(company.id),
                    "profile_id": str(profile.id),
                    "status": "CONFLICTING",
                }
            )
        if support and human and support.system_recommendation != human.decision:
            conflicts.append(
                {
                    "type": "SYSTEM_HUMAN_DECISION",
                    "source_a": support.system_recommendation,
                    "source_b": human.decision,
                    "status": "CONFLICTING",
                }
            )

        listing_snapshot = _row(listing)
        if (
            listing is not None
            and listing_snapshot
            and listing.last_price_date
            and listing.last_price_date > as_of
        ):
            listing_snapshot.pop("last_price_date", None)
            listing_snapshot.pop("price_data_status", None)
            listing_snapshot["price_metadata_status"] = "EXCLUDED_AFTER_AS_OF_DATE"
        # Ingestion runs and research datasets may span dates beyond the selected
        # report. Expose identity/provenance, not future-window aggregate counts.
        market_metadata = (
            {
                key: value
                for key, value in (_row(market_run) or {}).items()
                if key in {"id", "provider", "provider_version", "status"}
            }
            if market_run
            else None
        )
        dataset_metadata = (
            {
                key: value
                for key, value in (_row(dataset) or {}).items()
                if key
                in {
                    "id",
                    "dataset_version",
                    "feature_set_version",
                    "label_policy_version",
                    "benchmark_policy_version",
                    "split_policy_version",
                    "feature_schema_hash",
                }
            }
            if dataset
            else None
        )

        sections = {
            "company_profile": self._section(
                {
                    "company": _row(company),
                    "profile": profile_snapshot,
                    "classification": _row(domain),
                    "extracted_fields": [_row(item) for item in fields],
                },
                partial=not all((profile, domain)),
                review=bool(profile and identity != IdentityMatchStatus.MATCHED),
            ),
            "documents": self._section(
                {
                    "documents": [_row(item) for item in documents],
                    "pages": [_row(item) for item in pages],
                }
                if documents
                else None
            ),
            "financials": self._section(
                {
                    "statements": [_row(item) for item in statements],
                    "normalized_values": [_row(item) for item in financial_values],
                    "line_items": [_row(item) for item in line_items],
                    "ratios": [_row(item) for item in ratios],
                    "trends": [_row(item) for item in trends],
                    "anomalies": [_row(item) for item in anomalies],
                }
                if statements or financial_values
                else None,
                partial=bool(statements or financial_values) and not ratios,
            ),
            "credit": self._section(
                {
                    "assessment": _row(credit),
                    "subscores": [_row(item) for item in subscores],
                    "reasons": [_row(item) for item in reasons],
                    "ml_context": {
                        "lifecycle": "PIPELINE_VALIDATION_ONLY",
                        "production_use_permitted": False,
                        "production_ml_contribution": 0,
                    },
                    "five_cs": _row(five),
                    "five_cs_sections": [_row(item) for item in five_sections],
                    "research": _row(research),
                    "research_findings": [_row(item) for item in findings],
                    "research_sources": [_row(item) for item in research_sources],
                    "decision_support": _row(support),
                    "recommendation": _row(recommendation),
                    "human_review": _row(review),
                    "human_decision": _row(human),
                    "committee_package": _row(committee),
                    "cam_link": _row(cam),
                    "excluded_historical_sources": excluded_sources,
                    **credit_details,
                }
                if credit or five or support
                else None,
                applicable=credit_applicable,
                partial=credit_applicable and not all((credit, five, support, research)),
                review=bool(review and review.workflow_status not in {"DECIDED", "CLOSED"}),
            ),
            "stock": self._section(
                {
                    "listed_company": _row(listed),
                    "listing": listing_snapshot,
                    "peer_group": _row(peer),
                    "peer_members": [_row(item) for item in peer_members],
                    "market_data": {"price": _row(price), "run": market_metadata},
                    "fundamental_runs": [_row(item) for item in fundamental_runs],
                    "fundamentals": [_row(item) for item in fundamentals],
                    "valuation_run": _row(valuation_run),
                    "valuations": [_row(item) for item in valuations],
                    "relative_valuation": [_row(item) for item in relative_metrics],
                    "feature_run": _row(feature_run),
                    "features": [_row(item) for item in features],
                    "score": _row(score),
                    "components": [_row(item) for item in components],
                    "component_inputs": [_row(item) for item in component_inputs],
                    "ranking": _row(ranking_run),
                    "ranking_member": _row(ranking_member),
                    "watchlist": ranking_member.research_priority if ranking_member else None,
                    "ml_research": {
                        "prediction": _row(prediction),
                        "model": _row(ml_model),
                        "dataset": dataset_metadata,
                        "lifecycle": "PIPELINE_VALIDATION_ONLY",
                        "production_use_permitted": False,
                    },
                },
                applicable=stock_applicable,
                partial=stock_applicable
                and not all((price, fundamental_runs, valuation_run, score)),
            ),
            "validation": self._section(
                {
                    "scope": "PLATFORM_RESEARCH_DIAGNOSTICS",
                    "run": _row(validation_run),
                    "periods": [_row(item) for item in validation_periods],
                    "ablations": [_row(item) for item in ablations],
                    "ablation_metrics": [_row(item) for item in ablation_metrics],
                    "sensitivity": [_row(item) for item in sensitivities],
                    "policy_optimization_performed": False,
                }
                if validation_run
                else None,
                applicable=stock_applicable,
            ),
            "monitoring": self._section(
                {
                    "scope": "PLATFORM_RESEARCH_GOVERNANCE",
                    "run": _row(monitoring),
                    "findings": [_row(item) for item in monitoring_findings],
                    "providers": [_row(item) for item in providers],
                    "governance": _row(governance),
                    "automatic_action": "NONE",
                    **monitoring_details,
                }
                if monitoring
                else None,
                applicable=stock_applicable,
                review=bool(monitoring and monitoring.overall_health_status == "REVIEW_REQUIRED"),
            ),
        }

        def freshness(reference: date | datetime | None) -> dict[str, Any]:
            day = reference.date() if isinstance(reference, datetime) else reference
            return {
                "reference_date": str(day) if day else None,
                "age_days": (as_of - day).days if day else None,
            }

        sections["company_profile"]["freshness"] = freshness(
            document.created_at if document else None
        )
        sections["financials"]["freshness"] = freshness(
            max((item.period_end for item in statements if item.period_end), default=None)
        )
        sections["credit"]["freshness"] = freshness(research.created_at if research else None)
        sections["stock"]["freshness"] = {
            "market_data": freshness(price.trade_date if price else None),
            "fundamentals": freshness(
                max(
                    (item.availability_date for item in fundamental_runs if item.availability_date),
                    default=None,
                )
            ),
            "score": freshness(score.as_of_date if score else None),
        }
        sections["monitoring"]["freshness"] = freshness(
            monitoring.current_end_date if monitoring else None
        )
        for kind, records in (
            ("FINANCIAL", financial_values),
            ("RESEARCH", findings),
            ("CLASSIFICATION", [domain] if domain else []),
        ):
            for record in records:
                status = str(
                    _jsonable(
                        getattr(record, "status", getattr(record, "normalization_status", ""))
                    )
                )
                if "CONFLICT" in status or status == "NEEDS_REVIEW":
                    conflicts.append(
                        {
                            "type": kind,
                            "source_a": str(record.id),
                            "source_b": None,
                            "status": "CONFLICTING" if "CONFLICT" in status else "NEEDS_REVIEW",
                            "source_status": status,
                        }
                    )
        # Every included persisted record has a section-level source reference.
        # Traversal covers the batched child records without issuing more queries.
        known = {source_id for _, source_id, _, _ in links}

        def collect(value: Any, key: str, references: list[str]) -> None:
            if isinstance(value, dict):
                if value.get("id"):
                    source_id = UUID(value["id"])
                    references.append(str(source_id))
                    if source_id not in known:
                        link_metadata = {"section_key": key, "source_record": value}
                        links.append(
                            (key.upper()[:60], source_id, "SECTION_EVIDENCE", link_metadata)
                        )
                        known.add(source_id)
                for child_key, child in value.items():
                    collect(child, child_key, references)
            elif isinstance(value, list):
                for child in value:
                    collect(child, key, references)

        for key, section in sections.items():
            references: list[str] = []
            if section["status"] == "NOT_APPLICABLE":
                section["data"] = None
            collect(section["data"], key, references)
            section["source_references"] = sorted(set(references))
            section["subsection_statuses"] = {
                name: "UNAVAILABLE" if value in (None, [], {}) else "AVAILABLE"
                for name, value in (section["data"] or {}).items()
            }
        links.sort(key=lambda item: (item[0], str(item[1]), item[2]))
        return {
            "job": job,
            "document": document,
            "review": review,
            "support": support,
            "human": human,
            "committee": committee,
            "sections": sections,
            "conflicts": conflicts,
            "links": links,
            "listed": listed,
            "score": score,
            "monitoring": monitoring,
            "governance": governance,
            "credit": credit,
        }, links

    def build_snapshot(
        self,
        company_id: UUID,
        analysis_job_id: UUID | None,
        as_of: date,
        include_credit: bool,
        include_stock: bool,
    ) -> tuple[dict[str, Any], list[tuple[str, UUID, str, dict[str, Any] | None]], dict[str, Any]]:
        company = self.s.get(Company, company_id)
        if company is None:
            raise AppError("COMPANY_NOT_FOUND", "Company not found", 404)
        resolved, links = self._resolve(
            company, analysis_job_id, as_of, include_credit, include_stock
        )
        sections = cast(dict[str, dict[str, Any]], resolved["sections"])
        statuses = {key: item["status"] for key, item in sections.items()}
        applicable = [status for status in statuses.values() if status != "NOT_APPLICABLE"]
        available = sum(status == "AVAILABLE" for status in applicable)
        partial = sum(status == "PARTIAL" for status in applicable)
        review_count = sum(status == "NEEDS_REVIEW" for status in applicable)
        unavailable = sum(status == "UNAVAILABLE" for status in applicable)
        ratio = Decimal(available) + Decimal("0.5") * Decimal(partial)
        completeness = ratio / Decimal(len(applicable)) if applicable else Decimal("0")
        claim_ids = {
            source_id
            for section in sections.values()
            for source_id in section.get("source_references", [])
        }
        linked_ids = {str(item[1]) for item in links}
        evidenced = len(claim_ids & linked_ids)
        evidence_coverage = (
            Decimal(evidenced) / Decimal(len(claim_ids)) if claim_ids else Decimal("0")
        )
        readiness = (
            "NEEDS_REVIEW"
            if review_count or resolved["conflicts"]
            else "INSUFFICIENT_DATA"
            if not any(
                statuses[key] in {"AVAILABLE", "PARTIAL"}
                for key in ("documents", "financials", "credit", "stock")
            )
            else "PARTIAL"
            if partial or unavailable
            else "COMPLETE"
            if available
            else "INSUFFICIENT_DATA"
        )
        credit = resolved["credit"]
        score = resolved["score"]
        governance = resolved["governance"]
        strengths: list[str] = []
        risks: list[str] = []
        credit_data = sections["credit"].get("data") or {}
        financial_data = sections["financials"].get("data") or {}
        summary_references: list[str] = []
        for reason in credit_data.get("reasons", []):
            if reason.get("reason_type") in {"POSITIVE", "NEGATIVE"}:
                target = strengths if reason["reason_type"] == "POSITIVE" else risks
                target.append(reason["message"])
                summary_references.append(reason["id"])
        for observation in credit_data.get("five_cs_evidence", []):
            if observation.get("impact") in {"POSITIVE", "NEGATIVE"}:
                target = strengths if observation["impact"] == "POSITIVE" else risks
                target.append(observation["description"])
                summary_references.append(observation["id"])
        for anomaly in financial_data.get("anomalies", []):
            if anomaly.get("severity") in {"HIGH", "MODERATE", "CRITICAL"}:
                risks.append(anomaly["description"])
                summary_references.append(anomaly["id"])
        if score and score.top_positive_drivers:
            strengths.extend(
                f"Stock driver: {item.get('component', 'UNSPECIFIED')}"
                for item in score.top_positive_drivers[:3]
            )
        if score and score.top_negative_drivers:
            risks.extend(
                f"Stock driver: {item.get('component', 'UNSPECIFIED')}"
                for item in score.top_negative_drivers[:3]
            )
        if governance and governance.reasons_for_review:
            risks.extend(governance.reasons_for_review)
        strengths = list(dict.fromkeys(strengths))[:12]
        risks = list(dict.fromkeys(risks))[:12]
        missing = [key for key, status in statuses.items() if status in {"UNAVAILABLE", "PARTIAL"}]
        missing.extend(
            f"{key}.{child}"
            for key, section in sections.items()
            for child, status in section.get("subsection_statuses", {}).items()
            if status == "UNAVAILABLE"
        )
        source_ids = sorted({str(item[1]) for item in links})
        payload = {
            "schema_version": SCHEMA_VERSION,
            "manifest": {
                "report_version": REPORT_VERSION,
                "policy_version": POLICY_VERSION,
                "renderer_version": RENDERER_VERSION,
                "company_id": str(company.id),
                "analysis_job_id": str(resolved["job"].id) if resolved["job"] else None,
                "analytical_as_of_date": str(as_of),
                "generated_at": None,
                "include_credit": include_credit,
                "include_stock": include_stock,
                "source_ids": source_ids,
                "section_statuses": statuses,
                "completeness_ratio": str(completeness),
                "evidence_coverage": str(evidence_coverage),
            },
            "executive_summary": {
                "company": company.legal_name,
                "business_profile": sections["company_profile"]["data"],
                "financial_condition": sections["financials"]["status"],
                "credit_view": _row(credit),
                "equity_research_view": _row(score),
                "key_strengths": strengths,
                "key_risks": risks,
                "data_quality_limitations": missing,
                "governance_warnings": governance.reasons_for_review if governance else [],
                "source_references": sorted(
                    set(
                        summary_references
                        + ([str(score.id)] if score else [])
                        + ([str(governance.id)] if governance else [])
                    )
                ),
            },
            "sections": sections,
            "section_completeness": {
                "available_sections": available,
                "partial_sections": partial,
                "unavailable_sections": unavailable,
                "review_sections": review_count,
                "not_applicable_sections": sum(
                    status == "NOT_APPLICABLE" for status in statuses.values()
                ),
                "completeness_ratio": str(completeness),
                "readiness": readiness,
            },
            "evidence": {
                "coverage": str(evidence_coverage),
                "source_count": evidenced,
                "included_record_claims": len(claim_ids),
                "traceable_record_claims": evidenced,
                "coverage_definition": (
                    "Fraction of included persisted record claims with source links; "
                    "this is not analytical confidence."
                ),
                "authority_order": [
                    "ORIGINAL_EVIDENCE",
                    "EXTRACTED_FIELD",
                    "DERIVED_ANALYTICS",
                    "SYNTHESIZED_REPORT_TEXT",
                ],
                "circular_report_citation": False,
            },
            "key_strengths": strengths,
            "key_risks": risks,
            "missing_information": missing,
            "conflicts": resolved["conflicts"],
            "credit_stock_separation": SEPARATION,
            "no_master_score": True,
            "disclaimers": {
                "credit": CREDIT_DISCLAIMER,
                "stock": STOCK_DISCLAIMER,
                "historical_validation": VALIDATION_DISCLAIMER,
            },
        }
        payload["freshness"] = {key: section.get("freshness") for key, section in sections.items()}
        validate(payload, self.schema)
        if len(json.dumps(_jsonable(payload)).encode()) > int(self.policy["max_snapshot_bytes"]):
            raise AppError(
                "REPORT_SCOPE_TOO_LARGE",
                "Report payload limit exceeded; select a narrower analysis job",
                422,
            )
        meta = {
            **resolved,
            "company": company,
            "readiness": readiness,
            "completeness": completeness,
            "evidence_coverage": evidence_coverage,
        }
        return payload, links, meta

    def generate(
        self,
        company_id: UUID,
        actor_id: UUID,
        analysis_job_id: UUID | None = None,
        as_of: date | None = None,
        include_stock: bool = True,
        include_credit: bool = True,
    ) -> GeneratedReport:
        self._written_paths: list[Path] = []
        try:
            with self.s.begin_nested():
                return self._generate(
                    company_id, actor_id, analysis_job_id, as_of, include_stock, include_credit
                )
        except Exception:
            for path in self._written_paths:
                if path.resolve().is_relative_to(self.storage_root):
                    path.unlink(missing_ok=True)
            raise

    def _generate(
        self,
        company_id: UUID,
        actor_id: UUID,
        analysis_job_id: UUID | None = None,
        as_of: date | None = None,
        include_stock: bool = True,
        include_credit: bool = True,
    ) -> GeneratedReport:
        actor = self._user(actor_id)
        if actor.reviewer_role not in {
            "CREDIT_ANALYST",
            "SENIOR_CREDIT_REVIEWER",
            "CREDIT_MANAGER",
            "CREDIT_COMMITTEE_MEMBER",
            "ADMIN",
        }:
            raise AppError("REPORT_GENERATION_FORBIDDEN", "Role cannot generate reports", 403)
        report_as_of = as_of or _now().date()
        self.s.scalar(select(Company).where(Company.id == company_id).with_for_update())
        payload, links, meta = self.build_snapshot(
            company_id, analysis_job_id, report_as_of, include_credit, include_stock
        )
        input_hash = _digest(
            {
                "manifest": payload["manifest"],
                "sections": payload["sections"],
                "policy": self.policy,
            }
        )
        existing = self.s.scalar(
            select(GeneratedReport).where(
                GeneratedReport.company_id == company_id,
                GeneratedReport.report_type == REPORT_TYPE,
                GeneratedReport.input_hash == input_hash,
                GeneratedReport.template_version == REPORT_VERSION,
                GeneratedReport.renderer_version == RENDERER_VERSION,
            )
        )
        if existing:
            write_audit_log(
                self.s,
                entity_type="generated_report",
                entity_id=existing.id,
                action="COMPANY_INTELLIGENCE_REPORT_REUSED",
                event_type="COMPANY_INTELLIGENCE_REPORT_REUSED",
                company_id=company_id,
                user_id=actor.id,
            )
            return existing
        version = (
            self.s.scalar(
                select(GeneratedReport.report_version)
                .where(
                    GeneratedReport.company_id == company_id,
                    GeneratedReport.report_type == REPORT_TYPE,
                )
                .order_by(desc(GeneratedReport.report_version))
                .limit(1)
            )
            or 0
        ) + 1
        document = meta["document"]
        job = meta["job"]
        review = meta["review"]
        support = meta["support"]
        human = meta["human"]
        committee = meta["committee"]
        report = GeneratedReport(
            company_id=company_id,
            document_id=document.id if document else None,
            analysis_job_id=job.id if job else None,
            review_case_id=review.id if review else None,
            decision_support_id=support.id if support else None,
            human_decision_id=human.id if human else None,
            committee_package_id=committee.id if committee else None,
            report_type=REPORT_TYPE,
            status="DRAFT",
            report_version=version,
            template_version=REPORT_VERSION,
            renderer_version=RENDERER_VERSION,
            policy_version=POLICY_VERSION,
            schema_version=SCHEMA_VERSION,
            readiness_status=meta["readiness"],
            analytical_as_of_date=report_as_of,
            include_credit=include_credit,
            include_stock=include_stock,
            completeness_ratio=meta["completeness"],
            evidence_coverage=meta["evidence_coverage"],
            input_hash=input_hash,
            confidentiality_label="CONFIDENTIAL RESEARCH",
            generated_by_user_id=actor.id,
            generated_at=_now(),
        )
        self.s.add(report)
        self.s.flush()
        payload["manifest"]["generated_at"] = str(report.generated_at)
        payload["manifest"]["report_id"] = str(report.id)
        payload["manifest"]["report_sequence"] = version
        snapshot_hash = _digest(payload)
        self.s.add(
            ReportSnapshot(
                generated_report_id=report.id,
                snapshot_version=1,
                payload_json=_jsonable(payload),
                payload_hash=snapshot_hash,
                created_at=_now(),
            )
        )
        for source_type, source_id, role, metadata in links:
            self.s.add(
                ReportSourceLink(
                    generated_report_id=report.id,
                    source_type=source_type,
                    source_reference_id=source_id,
                    lineage_role=role,
                    source_metadata_json=metadata,
                    created_at=_now(),
                )
            )
        self.s.flush()
        for fmt in ("JSON", "PDF"):
            self.s.add(self._write_artifact(report, payload, fmt))
            write_audit_log(
                self.s,
                entity_type="generated_report",
                entity_id=report.id,
                action="COMPANY_INTELLIGENCE_REPORT_EXPORT_GENERATED",
                event_type="COMPANY_INTELLIGENCE_REPORT_EXPORT_GENERATED",
                company_id=company_id,
                user_id=actor.id,
                metadata_json={"format": fmt},
            )
        report.status = "NEEDS_REVIEW" if meta["readiness"] == "NEEDS_REVIEW" else "READY"
        write_audit_log(
            self.s,
            entity_type="generated_report",
            entity_id=report.id,
            action="COMPANY_INTELLIGENCE_REPORT_CREATED",
            event_type="COMPANY_INTELLIGENCE_REPORT_CREATED",
            company_id=company_id,
            analysis_job_id=job.id if job else None,
            user_id=actor.id,
            metadata_json={"snapshot_hash": snapshot_hash, "version": version},
        )
        return report

    def _write_artifact(
        self, report: GeneratedReport, payload: dict[str, Any], fmt: str
    ) -> ReportArtifact:
        directory = (
            self.storage_root
            / "reports"
            / report.company_id.hex[:12]
            / "company-intelligence-360"
            / report.id.hex[:20]
        ).resolve()
        if not directory.is_relative_to(self.storage_root):
            raise AppError("REPORT_STORAGE_PATH_INVALID", "Unsafe report storage path", 500)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (
            "company-intelligence-360.json" if fmt == "JSON" else "company-intelligence-360.pdf"
        )
        self._written_paths.append(target)
        if fmt == "JSON":
            target.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True), "utf-8")
        else:
            self._render_pdf(target, report, payload)
        data = target.read_bytes()
        if not data:
            raise AppError("REPORT_ARTIFACT_SIZE_INVALID", "Empty report artifact", 500)
        return ReportArtifact(
            generated_report_id=report.id,
            artifact_type="SNAPSHOT" if fmt == "JSON" else "REPORT",
            format=fmt,
            storage_path=target.relative_to(self.storage_root).as_posix(),
            mime_type="application/json" if fmt == "JSON" else "application/pdf",
            file_size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            created_at=_now(),
        )

    def _render_pdf(self, target: Path, report: GeneratedReport, payload: dict[str, Any]) -> None:
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "CI360Title",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17324D"),
        )
        heading = ParagraphStyle(
            "CI360Heading", parent=styles["Heading2"], textColor=colors.HexColor("#17324D")
        )
        body = ParagraphStyle("CI360Body", parent=styles["BodyText"], fontSize=8, leading=10)

        def footer(canvas: Any, doc: Any) -> None:
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.drawString(18 * mm, 10 * mm, f"CONFIDENTIAL RESEARCH | {report.id}")
            canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
            canvas.restoreState()

        doc = SimpleDocTemplate(
            str(target),
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title="360° Company Intelligence Report",
        )
        manifest = cast(dict[str, Any], payload["manifest"])
        summary = cast(dict[str, Any], payload["executive_summary"])
        story: list[Any] = [
            Paragraph("360° Company Intelligence Report", title),
            Spacer(1, 8),
            Paragraph(escape(str(summary["company"])), styles["Heading2"]),
            Paragraph(
                f"Report {REPORT_VERSION} | As of {manifest['analytical_as_of_date']} | "
                "Confidential / Research",
                body,
            ),
            Paragraph(f"Generated: {escape(str(manifest['generated_at']))}", body),
            Spacer(1, 10),
            Paragraph("Executive Summary", heading),
            Paragraph(SEPARATION, body),
        ]
        for label, key in (
            ("Financial condition", "financial_condition"),
            ("Key strengths", "key_strengths"),
            ("Key risks", "key_risks"),
            ("Data limitations", "data_quality_limitations"),
        ):
            story.append(
                Paragraph(f"<b>{label}:</b> {escape(str(summary.get(key) or 'Unavailable'))}", body)
            )

        def display_value(key: str, value: Any) -> str:
            labels = {
                "development_fixture_provider": "Development market data provider",
                "development_fixture_fundamentals_provider": "Development fundamentals provider",
                "fixture_research_provider": "Development research provider",
            }
            if "provider" in key and isinstance(value, str):
                return labels.get(
                    value, "Development research provider" if "fixture" in value else value
                )
            return str(value)

        def render_value(value: Any, depth: int = 0) -> None:
            if value is None:
                story.append(Paragraph("Unavailable", body))
            elif isinstance(value, list):
                for item in value[:12]:
                    render_value(item, depth + 1)
                    story.append(Spacer(1, 3))
                if len(value) > 12:
                    story.append(
                        Paragraph(
                            f"Showing 12 of {len(value)} records. "
                            "All records are available in the JSON snapshot.",
                            body,
                        )
                    )
                elif not value:
                    story.append(Paragraph("No records", body))
            elif isinstance(value, dict):
                if value.get("id"):
                    hidden = {
                        "input_hash",
                        "raw_value",
                        "raw_numeric_value",
                        "unit_multiplier",
                        "text_content",
                    }
                    parts = []
                    for key, item in value.items():
                        if item is None or isinstance(item, (dict, list)) or key in hidden:
                            continue
                        if (
                            key.startswith("recorded_")
                            or key == "id"
                            or key.endswith(("_id", "_hash", "_path", "_at", "_version"))
                        ):
                            continue
                        text = display_value(key, item)
                        if len(text) > 350:
                            text = text[:350] + " [full text in JSON]"
                        parts.append(
                            f"<b>{escape(key.replace('_', ' ').title())}:</b> {escape(text)}"
                        )
                    for start in range(0, len(parts), 5):
                        story.append(Paragraph(" · ".join(parts[start : start + 5]), body))
                    story.append(Paragraph(f"Source: {escape(str(value['id']))}", body))
                    return
                for key, item in value.items():
                    if key.endswith(("_hash", "_path")) or key in {"updated_at", "created_at"}:
                        continue
                    title_text = escape(key.replace("_", " ").title())
                    if isinstance(item, (list, dict)):
                        story.append(Paragraph(title_text, styles["Heading3"]))
                        if depth < 5:
                            render_value(item, depth + 1)
                        else:
                            story.append(
                                Paragraph(
                                    "Detailed source structure is available in the JSON snapshot.",
                                    body,
                                )
                            )
                    else:
                        rendered = escape(
                            display_value(key, item) if item is not None else "Unavailable"
                        )
                        if len(rendered) > 1800:
                            rendered = rendered[:1800] + " [Full text in JSON snapshot]"
                        story.append(Paragraph(f"<b>{title_text}:</b> {rendered}", body))
            else:
                story.append(Paragraph(escape(str(value)), body))

        sections = cast(dict[str, dict[str, Any]], payload["sections"])
        for name in (
            "company_profile",
            "documents",
            "financials",
            "credit",
            "stock",
            "validation",
            "monitoring",
        ):
            section = sections[name]
            story += [Spacer(1, 8), Paragraph(name.replace("_", " ").title(), heading)]
            story.append(Paragraph(f"Status: {section['status']}", body))
            data = section.get("data")
            if not data:
                story.append(Paragraph("Unavailable / Not applicable", body))
                continue
            if name == "stock" and data.get("components"):
                rows = [
                    [
                        Paragraph(label, body)
                        for label in ("Score component", "Score", "Weight", "Status")
                    ]
                ]
                rows.extend(
                    [
                        Paragraph(escape(str(item.get(key, "Unavailable"))), body)
                        for key in (
                            "component_name",
                            "normalized_score",
                            "effective_weight",
                            "status",
                        )
                    ]
                    for item in data["components"]
                )
                table = Table(rows, colWidths=[65 * mm, 30 * mm, 30 * mm, 45 * mm], repeatRows=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCD5DF")),
                        ]
                    )
                )
                story.append(table)
            render_value(data)
            story.append(
                Paragraph(
                    "Source IDs: "
                    + escape(", ".join(section.get("source_references", [])[:15]))
                    + ". Complete source references are included in the JSON snapshot.",
                    body,
                )
            )
        story += [PageBreak(), Paragraph("Conflicts and Missing Evidence", heading)]
        render_value(payload["conflicts"])
        render_value(payload["missing_information"])
        story += [
            PageBreak(),
            Paragraph("Evidence Appendix", heading),
            Paragraph(
                f"Traceable source records: {payload['evidence']['source_count']} | "
                f"Evidence coverage: {payload['evidence']['coverage']}",
                body,
            ),
            Paragraph("Limitations and Disclaimers", heading),
            Paragraph(CREDIT_DISCLAIMER, body),
            Paragraph(STOCK_DISCLAIMER, body),
            Paragraph(VALIDATION_DISCLAIMER, body),
            Spacer(1, 12),
            Paragraph("Lineage Manifest", heading),
            Paragraph(
                f"Schema: {SCHEMA_VERSION}<br/>Policy: {POLICY_VERSION}<br/>"
                f"Renderer: {RENDERER_VERSION}<br/>Input hash: {report.input_hash}",
                body,
            ),
            Paragraph(
                "Complete source identifiers and section citations are included in the "
                "authoritative JSON snapshot. Export hashes are persisted separately "
                "to avoid self-referential hashes.",
                body,
            ),
        ]
        doc.build(story, onFirstPage=footer, onLaterPages=footer)

    def finalize(self, report_id: UUID, actor_id: UUID, rationale: str | None) -> GeneratedReport:
        report = self.s.get(GeneratedReport, report_id)
        if report is None or report.report_type != REPORT_TYPE:
            raise AppError("REPORT_NOT_FOUND", "360 report not found", 404)
        actor = self._user(actor_id)
        if actor.reviewer_role not in {
            "SENIOR_CREDIT_REVIEWER",
            "CREDIT_MANAGER",
            "CREDIT_COMMITTEE_MEMBER",
            "ADMIN",
        }:
            raise AppError("REPORT_FINALIZATION_FORBIDDEN", "Role cannot finalize report", 403)
        if report.status == "FINALIZED":
            return report
        if report.status not in {"READY", "NEEDS_REVIEW"}:
            raise AppError("REPORT_NOT_READY", "Only a ready report can be finalized", 409)
        report.status = "FINALIZED"
        report.finalized_by_user_id = actor.id
        report.finalized_at = _now()
        self.s.add(
            ReportFinalizationAction(
                generated_report_id=report.id,
                actor_user_id=actor.id,
                action="FINALIZED",
                rationale=rationale,
                created_at=_now(),
            )
        )
        write_audit_log(
            self.s,
            entity_type="generated_report",
            entity_id=report.id,
            action="COMPANY_INTELLIGENCE_REPORT_FINALIZED",
            event_type="COMPANY_INTELLIGENCE_REPORT_FINALIZED",
            company_id=report.company_id,
            user_id=actor.id,
        )
        return report

    def supersede(
        self, report_id: UUID, successor_id: UUID, actor_id: UUID, rationale: str
    ) -> GeneratedReport:
        report = self.s.get(GeneratedReport, report_id)
        successor = self.s.get(GeneratedReport, successor_id)
        actor = self._user(actor_id)
        if report is None or successor is None:
            raise AppError("REPORT_NOT_FOUND", "Report or successor not found", 404)
        if report.report_type != REPORT_TYPE or successor.status not in {
            "READY",
            "NEEDS_REVIEW",
            "FINALIZED",
        }:
            raise AppError("REPORT_SUCCESSOR_INVALID", "Invalid report or successor state", 409)
        if actor.reviewer_role not in {
            "SENIOR_CREDIT_REVIEWER",
            "CREDIT_MANAGER",
            "CREDIT_COMMITTEE_MEMBER",
            "ADMIN",
        }:
            raise AppError("REPORT_SUPERSESSION_FORBIDDEN", "Role cannot supersede report", 403)
        if report.status != "FINALIZED":
            raise AppError("REPORT_NOT_FINALIZED", "Only finalized reports can be superseded", 409)
        if (
            report.company_id != successor.company_id
            or successor.report_type != REPORT_TYPE
            or successor.report_version <= report.report_version
        ):
            raise AppError("REPORT_SUCCESSOR_INVALID", "Invalid successor report", 409)
        report.status = "SUPERSEDED"
        report.superseded_by_report_id = successor.id
        successor.supersedes_report_id = report.id
        self.s.add(
            ReportFinalizationAction(
                generated_report_id=report.id,
                actor_user_id=actor.id,
                action="SUPERSEDED",
                rationale=rationale,
                created_at=_now(),
            )
        )
        write_audit_log(
            self.s,
            entity_type="generated_report",
            entity_id=report.id,
            action="COMPANY_INTELLIGENCE_REPORT_SUPERSEDED",
            event_type="COMPANY_INTELLIGENCE_REPORT_SUPERSEDED",
            company_id=report.company_id,
            user_id=actor.id,
            metadata_json={"successor_report_id": str(successor.id)},
        )
        return report
