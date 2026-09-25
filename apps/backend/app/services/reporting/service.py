from __future__ import annotations

# ruff: noqa: E501, E701, E702
import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import desc, select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.company import Company
from app.models.company_profile import CompanyProfile
from app.models.credit import CreditAssessment, CreditRuleResult, CreditSubscore
from app.models.decision import (
    CreditDecisionGate,
    CreditDecisionReviewItem,
    CreditDecisionSupport,
    CreditLimitMethod,
    CreditLimitPreparation,
    CreditPolicyException,
)
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.domain_classification import DomainClassification
from app.models.financial import FinancialLineItem, FinancialStatement
from app.models.financial_analysis import FinancialRatio, NormalizedFinancialValue
from app.models.financial_trend import FinancialAnomaly, FinancialTrend
from app.models.five_cs import FiveCsAssessment, FiveCsSection
from app.models.recommendation import (
    CreditRecommendationFactor,
    CreditRecommendationPreparation,
    CreditRecommendationReviewItem,
)
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
    CreditDecisionOverride,
    CreditHumanDecision,
    CreditInformationRequest,
    CreditPolicyExceptionAction,
    CreditReviewCase,
    CreditReviewChecklistAction,
    CreditReviewComment,
    CreditReviewEvidenceAcknowledgement,
)
from app.models.user import User

RENDERER_VERSION = "report_renderer_v1"
TEMPLATES = {
    "CAM": "cam_report_v1",
    "CREDIT_COMMITTEE_MEMO": "credit_committee_memo_v1",
    "DECISION_EVIDENCE_PACK": "decision_evidence_pack_v1",
    "STRUCTURED_JSON_EXPORT": "decision_evidence_pack_v1",
}
DISCLAIMER = "This report summarizes persisted analytical and human-review records for internal commercial credit review. Automated outputs are decision-support information. Final lending decisions are human governance actions and downstream facility booking, pricing, sanction documentation, and disbursement are outside this report."


def _now() -> datetime:
    return datetime.now(UTC)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (UUID, date, datetime, Decimal)):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _row(row: object | None) -> dict[str, Any] | None:
    if row is None:
        return None
    inspected = cast(Any, sa_inspect(row))
    return {a.key: _jsonable(getattr(row, a.key)) for a in inspected.mapper.column_attrs}


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class CreditReportService:
    def __init__(self, session: Session, storage_root: Path):
        self.session = session
        self.storage_root = storage_root.resolve()

    def _user(self, user_id: UUID) -> User:
        user = self.session.get(User, user_id)
        if user is None or not user.is_active:
            raise AppError("REPORT_ACTOR_NOT_AUTHORIZED", "Active report actor not found", 403)
        return user

    def _case(self, case_id: UUID) -> CreditReviewCase:
        case = self.session.get(CreditReviewCase, case_id)
        if case is None:
            raise AppError("CREDIT_REVIEW_CASE_NOT_FOUND", "Credit review case not found", 404)
        return case

    def _policy(self, name: str) -> dict[str, Any]:
        return json.loads(Path(__file__).with_name(name).read_text(encoding="utf-8"))

    def _gather(
        self, case: CreditReviewCase, committee_id: UUID | None
    ) -> tuple[dict[str, object], list[tuple[str, UUID, str]]]:
        support = self.session.get(CreditDecisionSupport, case.decision_support_id)
        assert support is not None
        committee = (
            self.session.get(CreditCommitteePackage, committee_id)
            if committee_id
            else self.session.scalar(
                select(CreditCommitteePackage)
                .where(CreditCommitteePackage.review_case_id == case.id)
                .order_by(desc(CreditCommitteePackage.package_version))
                .limit(1)
            )
        )
        if committee and committee.review_case_id != case.id:
            raise AppError(
                "REPORT_LINEAGE_MISMATCH", "Committee package does not belong to review case", 409
            )
        human = self.session.scalar(
            select(CreditHumanDecision).where(
                CreditHumanDecision.review_case_id == case.id,
                CreditHumanDecision.is_current.is_(True),
            )
        )
        profile = self.session.scalar(
            select(CompanyProfile)
            .where(CompanyProfile.document_id == case.document_id)
            .order_by(desc(CompanyProfile.created_at))
            .limit(1)
        )
        company = self.session.get(Company, case.company_id)
        document = self.session.get(Document, case.document_id)
        credit = self.session.get(CreditAssessment, support.credit_assessment_id)
        five = self.session.get(FiveCsAssessment, support.five_cs_assessment_id)
        research = (
            self.session.get(ResearchRun, support.research_run_id)
            if support.research_run_id
            else None
        )
        recommendation = self.session.get(
            CreditRecommendationPreparation, support.recommendation_preparation_id
        )
        domain = self.session.scalar(
            select(DomainClassification)
            .where(DomainClassification.document_id == case.document_id)
            .order_by(desc(DomainClassification.created_at))
            .limit(1)
        )
        reviewer = (
            self.session.get(User, case.primary_reviewer_id) if case.primary_reviewer_id else None
        )

        def rows(model: Any, *criteria: Any) -> list[dict[str, Any]]:
            statement = select(model).where(*criteria).order_by(model.id)
            return [_row(x) or {} for x in self.session.scalars(statement)]

        latest_support = self.session.scalar(
            select(CreditDecisionSupport.id)
            .where(
                CreditDecisionSupport.document_id == case.document_id,
                CreditDecisionSupport.created_at > support.created_at,
            )
            .limit(1)
        )
        payload: dict[str, object] = {
            "classification": "INTERNAL CREDIT REVIEW",
            "updated_analysis_available": bool(latest_support),
            "company": _row(company),
            "company_profile": _row(profile),
            "document": {
                "id": str(document.id),
                "original_filename": document.original_filename,
                "file_type": document.file_type,
                "page_count": document.page_count,
                "parser_version": document.parser_version,
            }
            if document
            else None,
            "domain_classification": _row(domain),
            "basis": {
                "credit_assessment_id": str(support.credit_assessment_id),
                "five_cs_assessment_id": str(support.five_cs_assessment_id),
                "research_run_id": str(support.research_run_id)
                if support.research_run_id
                else None,
                "recommendation_preparation_id": str(support.recommendation_preparation_id),
                "decision_support_id": str(support.id),
                "review_case_id": str(case.id),
                "human_decision_id": str(human.id) if human else None,
                "committee_package_id": str(committee.id) if committee else None,
            },
            "credit_assessment": _row(credit),
            "credit_subscores": rows(
                CreditSubscore, CreditSubscore.credit_assessment_id == support.credit_assessment_id
            ),
            "credit_reasons": rows(
                CreditRuleResult,
                CreditRuleResult.credit_assessment_id == support.credit_assessment_id,
            ),
            "financial_ratios": rows(
                FinancialRatio, FinancialRatio.document_id == case.document_id
            ),
            "financial_statements": rows(
                FinancialStatement, FinancialStatement.document_id == case.document_id
            ),
            "normalized_financial_values": rows(
                NormalizedFinancialValue,
                NormalizedFinancialValue.document_id == case.document_id,
            ),
            "financial_line_items": rows(
                FinancialLineItem, FinancialLineItem.document_id == case.document_id
            ),
            "financial_trends": rows(
                FinancialTrend, FinancialTrend.document_id == case.document_id
            ),
            "financial_anomalies": rows(
                FinancialAnomaly, FinancialAnomaly.document_id == case.document_id
            ),
            "document_pages": [
                {
                    "id": str(page.id),
                    "document_id": str(page.document_id),
                    "page_number": page.page_number,
                    "extraction_method": _jsonable(page.extraction_method),
                    "text_quality_score": page.text_quality_score,
                    "parser_version": page.parser_version,
                }
                for page in self.session.scalars(
                    select(DocumentPage)
                    .where(DocumentPage.document_id == case.document_id)
                    .order_by(DocumentPage.page_number)
                )
            ],
            "five_cs": _row(five),
            "five_cs_sections": rows(
                FiveCsSection, FiveCsSection.five_cs_assessment_id == support.five_cs_assessment_id
            ),
            "research_run": _row(research),
            "research_findings": rows(
                ResearchFinding, ResearchFinding.research_run_id == support.research_run_id
            )
            if support.research_run_id
            else [],
            "research_sources": rows(
                ResearchSource, ResearchSource.research_run_id == support.research_run_id
            )
            if support.research_run_id
            else [],
            "decision_support": _row(support),
            "recommendation_preparation": _row(recommendation),
            "recommendation_factors": rows(
                CreditRecommendationFactor,
                CreditRecommendationFactor.recommendation_preparation_id
                == support.recommendation_preparation_id,
            ),
            "recommendation_review_items": rows(
                CreditRecommendationReviewItem,
                CreditRecommendationReviewItem.recommendation_preparation_id
                == support.recommendation_preparation_id,
            ),
            "policy_gates": rows(
                CreditDecisionGate, CreditDecisionGate.credit_decision_support_id == support.id
            ),
            "policy_exceptions": rows(
                CreditPolicyException,
                CreditPolicyException.credit_decision_support_id == support.id,
            ),
            "review_items": rows(
                CreditDecisionReviewItem,
                CreditDecisionReviewItem.credit_decision_support_id == support.id,
            ),
            "analytical_limit": _row(
                self.session.scalar(
                    select(CreditLimitPreparation).where(
                        CreditLimitPreparation.credit_decision_support_id == support.id
                    )
                )
            ),
            "limit_methods": rows(
                CreditLimitMethod, CreditLimitMethod.credit_decision_support_id == support.id
            ),
            "review_case": _row(case),
            "assigned_reviewer_role": reviewer.reviewer_role if reviewer else None,
            "review_comments": rows(
                CreditReviewComment, CreditReviewComment.review_case_id == case.id
            ),
            "information_requests": rows(
                CreditInformationRequest, CreditInformationRequest.review_case_id == case.id
            ),
            "checklist_actions": rows(
                CreditReviewChecklistAction, CreditReviewChecklistAction.review_case_id == case.id
            ),
            "evidence_acknowledgements": rows(
                CreditReviewEvidenceAcknowledgement,
                CreditReviewEvidenceAcknowledgement.review_case_id == case.id,
            ),
            "exception_actions": rows(
                CreditPolicyExceptionAction, CreditPolicyExceptionAction.review_case_id == case.id
            ),
            "human_decision": _row(human),
            "decision_history": rows(
                CreditHumanDecision, CreditHumanDecision.review_case_id == case.id
            ),
            "overrides": rows(
                CreditDecisionOverride,
                CreditDecisionOverride.human_decision_id.in_(
                    select(CreditHumanDecision.id).where(
                        CreditHumanDecision.review_case_id == case.id
                    )
                ),
            ),
            "committee_package": _row(committee),
            "experimental_ml_context": {
                "lifecycle": "PIPELINE_VALIDATION_ONLY",
                "production_use_permitted": False,
                "fusion": "EXPERIMENTAL",
                "decision_weight": 0,
            },
            "disclaimer": DISCLAIMER,
        }
        links = [
            ("credit_assessment", support.credit_assessment_id, "CREDIT_ANALYSIS"),
            ("five_cs_assessment", support.five_cs_assessment_id, "FIVE_CS"),
            ("recommendation_preparation", support.recommendation_preparation_id, "RECOMMENDATION"),
            ("decision_support", support.id, "DECISION_SUPPORT"),
            ("credit_review_case", case.id, "HUMAN_REVIEW"),
        ]
        if support.research_run_id:
            links.append(("research_run", support.research_run_id, "EXTERNAL_RESEARCH"))
        if human:
            links.append(("human_decision", human.id, "HUMAN_DECISION"))
        if committee:
            links.append(("committee_package", committee.id, "COMMITTEE"))
        linked_rows = {
            "document_page": payload["document_pages"],
            "financial_statement": payload["financial_statements"],
            "normalized_financial_value": payload["normalized_financial_values"],
            "financial_line_item": payload["financial_line_items"],
            "financial_ratio": payload["financial_ratios"],
            "financial_trend": payload["financial_trends"],
            "financial_anomaly": payload["financial_anomalies"],
            "research_source": payload["research_sources"],
            "research_finding": payload["research_findings"],
            "policy_gate": payload["policy_gates"],
            "policy_exception": payload["policy_exceptions"],
            "recommendation_factor": payload["recommendation_factors"],
            "recommendation_review_item": payload["recommendation_review_items"],
        }
        for source_type, source_rows in linked_rows.items():
            for source_row in cast(list[dict[str, Any]], source_rows):
                source_id = source_row.get("id")
                if source_id:
                    links.append((source_type, UUID(str(source_id)), "SUPPORTING_EVIDENCE"))
        return payload, links

    def generate(
        self,
        case_id: UUID,
        actor_id: UUID,
        report_type: str,
        artifact_format: str = "PDF",
        committee_id: UUID | None = None,
    ) -> GeneratedReport:
        actor = self._user(actor_id)
        policy = self._policy("report_authority_policy_v1.json")
        if actor.reviewer_role not in policy["generate_roles"]:
            raise AppError("REPORT_GENERATION_FORBIDDEN", "Role cannot generate reports", 403)
        if report_type not in TEMPLATES or artifact_format not in {"PDF", "JSON"}:
            raise AppError(
                "REPORT_TYPE_OR_FORMAT_INVALID", "Unsupported report type or format", 422
            )
        if report_type == "CREDIT_COMMITTEE_MEMO" and committee_id is None:
            raise AppError(
                "COMMITTEE_PACKAGE_REQUIRED", "Committee memo requires a committee package", 422
            )
        case = self._case(case_id)
        payload, links = self._gather(case, committee_id)
        template = TEMPLATES[report_type]
        input_hash = _digest(
            {
                "payload": payload,
                "template": template,
                "renderer": RENDERER_VERSION,
                "format": artifact_format,
            }
        )
        existing = self.session.scalar(
            select(GeneratedReport).where(
                GeneratedReport.review_case_id == case.id,
                GeneratedReport.report_type == report_type,
                GeneratedReport.input_hash == input_hash,
                GeneratedReport.template_version == template,
                GeneratedReport.renderer_version == RENDERER_VERSION,
            )
        )
        if existing:
            return existing
        version = (
            self.session.scalar(
                select(GeneratedReport.report_version)
                .where(
                    GeneratedReport.review_case_id == case.id,
                    GeneratedReport.report_type == report_type,
                )
                .order_by(desc(GeneratedReport.report_version))
                .limit(1)
            )
            or 0
        ) + 1
        current = self.session.scalar(
            select(CreditHumanDecision).where(
                CreditHumanDecision.review_case_id == case.id,
                CreditHumanDecision.is_current.is_(True),
            )
        )
        report = GeneratedReport(
            company_id=case.company_id,
            document_id=case.document_id,
            analysis_job_id=case.analysis_job_id,
            review_case_id=case.id,
            decision_support_id=case.decision_support_id,
            human_decision_id=current.id if current else None,
            committee_package_id=committee_id,
            report_type=report_type,
            status="DRAFT",
            report_version=version,
            template_version=template,
            renderer_version=RENDERER_VERSION,
            input_hash=input_hash,
            confidentiality_label="CREDIT COMMITTEE"
            if report_type == "CREDIT_COMMITTEE_MEMO"
            else "INTERNAL",
            generated_by_user_id=actor.id,
            generated_at=_now(),
        )
        self.session.add(report)
        self.session.flush()
        write_audit_log(
            self.session,
            entity_type="generated_report",
            entity_id=report.id,
            action="CREDIT_REPORT_GENERATION_STARTED",
            event_type="CREDIT_REPORT_GENERATION_STARTED",
            company_id=case.company_id,
            analysis_job_id=case.analysis_job_id,
            user_id=actor.id,
            metadata_json={"report_type": report_type, "format": artifact_format},
        )
        payload["report"] = {
            "id": str(report.id),
            "type": report_type,
            "version": version,
            "generated_at": str(report.generated_at),
            "template_version": template,
            "renderer_version": RENDERER_VERSION,
        }
        snapshot_hash = _digest(payload)
        self.session.add(
            ReportSnapshot(
                generated_report_id=report.id,
                snapshot_version=1,
                payload_json=_jsonable(payload),
                payload_hash=snapshot_hash,
                created_at=_now(),
            )
        )
        for source_type, source_id, role in links:
            self.session.add(
                ReportSourceLink(
                    generated_report_id=report.id,
                    source_type=source_type,
                    source_reference_id=source_id,
                    lineage_role=role,
                    created_at=_now(),
                )
            )
        write_audit_log(
            self.session,
            entity_type="generated_report",
            entity_id=report.id,
            action="CREDIT_REPORT_SNAPSHOT_CREATED",
            event_type="CREDIT_REPORT_SNAPSHOT_CREATED",
            company_id=case.company_id,
            analysis_job_id=case.analysis_job_id,
            user_id=actor.id,
            metadata_json={"report_type": report_type, "snapshot_hash": snapshot_hash},
        )
        try:
            artifact = self._write_artifact(report, payload, artifact_format)
        except Exception as error:
            report.status = "FAILED"
            write_audit_log(
                self.session,
                entity_type="generated_report",
                entity_id=report.id,
                action="CREDIT_REPORT_GENERATION_FAILED",
                event_type="CREDIT_REPORT_GENERATION_FAILED",
                company_id=case.company_id,
                analysis_job_id=case.analysis_job_id,
                user_id=actor.id,
                metadata_json={
                    "report_type": report_type,
                    "format": artifact_format,
                    "error_type": type(error).__name__,
                },
            )
            return report
        report.status = "GENERATED"
        self.session.add(artifact)
        write_audit_log(
            self.session,
            entity_type="generated_report",
            entity_id=report.id,
            action="CREDIT_REPORT_GENERATED",
            event_type="CREDIT_REPORT_GENERATED",
            company_id=case.company_id,
            analysis_job_id=case.analysis_job_id,
            user_id=actor.id,
            metadata_json={
                "format": artifact_format,
                "sha256": artifact.sha256,
                "file_size_bytes": artifact.file_size_bytes,
            },
        )
        return report

    def _write_artifact(
        self, report: GeneratedReport, payload: dict[str, object], fmt: str
    ) -> ReportArtifact:
        storage_policy = self._policy("report_storage_policy_v1.json")
        filename = storage_policy["safe_filenames"][report.report_type] + (
            ".pdf" if fmt == "PDF" else ".json"
        )
        directory = (
            self.storage_root
            / "reports"
            / report.company_id.hex[:12]
            / storage_policy["safe_filenames"][report.report_type]
            / report.id.hex[:20]
        ).resolve()
        if not directory.is_relative_to(self.storage_root):
            raise AppError("REPORT_STORAGE_PATH_INVALID", "Unsafe report storage path", 500)
        directory.mkdir(parents=True, exist_ok=False)
        target = directory / filename
        try:
            if fmt == "JSON":
                target.write_text(
                    json.dumps(_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8"
                )
            else:
                self._render_pdf(target, report, payload)
            data = target.read_bytes()
            if not data or len(data) > int(storage_policy["maximum_file_size_bytes"]):
                raise AppError(
                    "REPORT_ARTIFACT_SIZE_INVALID", "Generated artifact size is invalid", 500
                )
        except Exception:
            target.unlink(missing_ok=True)
            directory.rmdir()
            raise
        relative = target.relative_to(self.storage_root).as_posix()
        return ReportArtifact(
            generated_report_id=report.id,
            artifact_type="REPORT",
            format=fmt,
            storage_path=relative,
            mime_type="application/pdf" if fmt == "PDF" else "application/json",
            file_size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            created_at=_now(),
        )

    def _render_pdf(
        self, target: Path, report: GeneratedReport, payload: dict[str, object]
    ) -> None:
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17324D"),
            spaceAfter=12,
        )
        heading = ParagraphStyle(
            "H",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#17324D"),
            spaceBefore=10,
            spaceAfter=5,
        )
        body = ParagraphStyle("B", parent=styles["BodyText"], fontSize=8.5, leading=11)

        def footer(canvas: Any, doc: Any) -> None:
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#536273"))
            canvas.drawString(
                18 * mm,
                10 * mm,
                f"INTERNAL CREDIT REVIEW | Report {report.id} | v{report.report_version}",
            )
            canvas.drawRightString(
                192 * mm,
                10 * mm,
                f"Generated {report.generated_at.isoformat()} | Page {doc.page}",
            )
            canvas.restoreState()

        doc = SimpleDocTemplate(
            str(target),
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=17 * mm,
            title=report.report_type,
        )
        story: list[Any] = [
            Paragraph(report.report_type.replace("_", " "), title),
            Paragraph(
                f"Report Version {report.report_version} | {report.confidentiality_label}",
                styles["Heading3"],
            ),
            Spacer(1, 8),
        ]
        company = cast(
            dict[str, Any], payload.get("company_profile") or payload.get("company") or {}
        )
        support = cast(dict[str, Any], payload.get("decision_support") or {})
        human = cast(dict[str, Any], payload.get("human_decision") or {})
        limit = cast(dict[str, Any], payload.get("analytical_limit") or {})
        summary = [
            ["Company", str(company.get("legal_name") or company.get("name") or "Unavailable")],
            ["System Recommendation", str(support.get("system_recommendation") or "Unavailable")],
            ["Human Decision", str(human.get("decision") or "NOT RECORDED")],
            [
                "Analytical Exposure Ceiling",
                f"{limit.get('currency') or ''} {limit.get('analytical_ceiling') or 'Unavailable'}",
            ],
            [
                "Human Approved Limit",
                f"{human.get('currency') or ''} {human.get('approved_limit') or 'NOT RECORDED'}",
            ],
            [
                "Updated Analysis",
                "UPDATED_ANALYSIS_AVAILABLE" if payload.get("updated_analysis_available") else "No",
            ],
        ]
        table = Table(
            [[Paragraph(str(a), body), Paragraph(str(b), body)] for a, b in summary],
            colWidths=[55 * mm, 105 * mm],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF0F5")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#A9B6C2")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story += [table, Spacer(1, 8)]
        section_order = [
            "basis",
            "credit_assessment",
            "credit_subscores",
            "domain_classification",
            "financial_statements",
            "normalized_financial_values",
            "financial_line_items",
            "financial_ratios",
            "financial_trends",
            "financial_anomalies",
            "five_cs_sections",
            "research_findings",
            "research_sources",
            "recommendation_preparation",
            "recommendation_factors",
            "recommendation_review_items",
            "policy_gates",
            "policy_exceptions",
            "analytical_limit",
            "limit_methods",
            "review_comments",
            "information_requests",
            "checklist_actions",
            "exception_actions",
            "human_decision",
            "decision_history",
            "overrides",
            "committee_package",
            "experimental_ml_context",
        ]
        if report.report_type == "CREDIT_COMMITTEE_MEMO":
            section_order = [
                "basis",
                "credit_assessment",
                "five_cs_sections",
                "research_findings",
                "policy_gates",
                "policy_exceptions",
                "analytical_limit",
                "review_comments",
                "information_requests",
                "human_decision",
                "decision_history",
                "committee_package",
            ]
        for key in section_order:
            story.append(Paragraph(key.replace("_", " ").title(), heading))
            value = payload.get(key)
            if not value:
                story.append(Paragraph("Unavailable / Not Recorded", body))
                continue
            items = value if isinstance(value, list) else [value]
            rows = []
            for item in items:
                if isinstance(item, dict):
                    rows.append(
                        [
                            [
                                Paragraph(str(k).replace("_", " ").title(), body),
                                Paragraph(str(v) if v is not None else "Unavailable", body),
                            ]
                            for k, v in item.items()
                        ]
                    )
                else:
                    rows.append([[Paragraph("Value", body), Paragraph(str(item), body)]])
            for group in rows:
                t = Table(group, colWidths=[50 * mm, 110 * mm], repeatRows=0)
                t.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C4CDD5")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F7F9")),
                        ]
                    )
                )
                story += [t, Spacer(1, 4)]
        story += [
            PageBreak(),
            Paragraph("Limitations and Disclaimer", heading),
            Paragraph(DISCLAIMER, body),
        ]
        doc.build(story, onFirstPage=footer, onLaterPages=footer)

    def finalize(
        self, report_id: UUID, actor_id: UUID, rationale: str | None = None
    ) -> GeneratedReport:
        report = self.session.get(GeneratedReport, report_id)
        if report is None:
            raise AppError("REPORT_NOT_FOUND", "Report not found", 404)
        actor = self._user(actor_id)
        roles = self._policy("report_authority_policy_v1.json")["finalize"][report.report_type]
        if actor.reviewer_role not in roles:
            raise AppError(
                "REPORT_FINALIZATION_FORBIDDEN", "Role cannot finalize this report type", 403
            )
        if report.status == "FINALIZED":
            return report
        if report.status != "GENERATED":
            raise AppError("REPORT_NOT_GENERATED", "Only a generated report can be finalized", 409)
        report.status = "FINALIZED"
        report.finalized_by_user_id = actor.id
        report.finalized_at = _now()
        self.session.add(
            ReportFinalizationAction(
                generated_report_id=report.id,
                actor_user_id=actor.id,
                action="FINALIZED",
                rationale=rationale,
                created_at=_now(),
            )
        )
        write_audit_log(
            self.session,
            entity_type="generated_report",
            entity_id=report.id,
            action="CREDIT_REPORT_FINALIZED",
            event_type="CREDIT_REPORT_FINALIZED",
            company_id=report.company_id,
            analysis_job_id=report.analysis_job_id,
            user_id=actor.id,
            metadata_json={"report_type": report.report_type, "version": report.report_version},
        )
        return report

    def supersede(
        self,
        report_id: UUID,
        successor_report_id: UUID,
        actor_id: UUID,
        rationale: str,
    ) -> GeneratedReport:
        report = self.session.get(GeneratedReport, report_id)
        successor = self.session.get(GeneratedReport, successor_report_id)
        if report is None or successor is None:
            raise AppError("REPORT_NOT_FOUND", "Report or successor report not found", 404)
        actor = self._user(actor_id)
        roles = self._policy("report_authority_policy_v1.json")["finalize"][report.report_type]
        if actor.reviewer_role not in roles:
            raise AppError(
                "REPORT_SUPERSESSION_FORBIDDEN", "Role cannot supersede this report type", 403
            )
        if report.status != "FINALIZED":
            raise AppError("REPORT_NOT_FINALIZED", "Only a finalized report can be superseded", 409)
        if (
            report.review_case_id != successor.review_case_id
            or report.report_type != successor.report_type
            or successor.report_version <= report.report_version
        ):
            raise AppError(
                "REPORT_SUCCESSOR_INVALID",
                "Successor must be a newer report version for the same case and type",
                409,
            )
        if successor.status not in {"GENERATED", "FINALIZED"}:
            raise AppError(
                "REPORT_SUCCESSOR_NOT_ISSUABLE",
                "Successor must be generated or finalized",
                409,
            )
        report.status = "SUPERSEDED"
        report.superseded_by_report_id = successor.id
        successor.supersedes_report_id = report.id
        self.session.add(
            ReportFinalizationAction(
                generated_report_id=report.id,
                actor_user_id=actor.id,
                action="SUPERSEDED",
                rationale=rationale,
                created_at=_now(),
            )
        )
        write_audit_log(
            self.session,
            entity_type="generated_report",
            entity_id=report.id,
            action="CREDIT_REPORT_SUPERSEDED",
            event_type="CREDIT_REPORT_SUPERSEDED",
            company_id=report.company_id,
            analysis_job_id=report.analysis_job_id,
            user_id=actor.id,
            metadata_json={
                "report_type": report.report_type,
                "version": report.report_version,
                "successor_report_id": str(successor.id),
                "successor_version": successor.report_version,
            },
        )
        return report

    def authorized_artifact(
        self, report_id: UUID, actor_id: UUID
    ) -> tuple[GeneratedReport, ReportArtifact, Path]:
        report = self.session.get(GeneratedReport, report_id)
        if report is None:
            raise AppError("REPORT_NOT_FOUND", "Report not found", 404)
        actor = self._user(actor_id)
        if (
            actor.reviewer_role
            not in self._policy("report_authority_policy_v1.json")["download_roles"]
        ):
            raise AppError("REPORT_DOWNLOAD_FORBIDDEN", "Role cannot download reports", 403)
        artifact = self.session.scalar(
            select(ReportArtifact).where(ReportArtifact.generated_report_id == report.id)
        )
        if artifact is None:
            raise AppError("REPORT_ARTIFACT_NOT_FOUND", "Report artifact not found", 404)
        path = (self.storage_root / artifact.storage_path).resolve()
        if not path.is_relative_to(self.storage_root) or not path.is_file():
            raise AppError("REPORT_ARTIFACT_UNAVAILABLE", "Report artifact is unavailable", 404)
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256:
            raise AppError("REPORT_ARTIFACT_INTEGRITY_FAILED", "Report artifact hash mismatch", 409)
        return report, artifact, path


def report_payload(session: Session, report: GeneratedReport) -> dict[str, object]:
    artifact = session.scalar(
        select(ReportArtifact).where(ReportArtifact.generated_report_id == report.id)
    )
    snapshot = session.scalar(
        select(ReportSnapshot).where(ReportSnapshot.generated_report_id == report.id)
    )
    return {
        "id": report.id,
        "review_case_id": report.review_case_id,
        "decision_support_id": report.decision_support_id,
        "human_decision_id": report.human_decision_id,
        "committee_package_id": report.committee_package_id,
        "report_type": report.report_type,
        "status": report.status,
        "report_version": report.report_version,
        "template_version": report.template_version,
        "renderer_version": report.renderer_version,
        "input_hash": report.input_hash,
        "confidentiality_label": report.confidentiality_label,
        "generated_by_user_id": report.generated_by_user_id,
        "finalized_by_user_id": report.finalized_by_user_id,
        "generated_at": report.generated_at,
        "finalized_at": report.finalized_at,
        "supersedes_report_id": report.supersedes_report_id,
        "superseded_by_report_id": report.superseded_by_report_id,
        "artifact": {
            "id": artifact.id,
            "format": artifact.format,
            "mime_type": artifact.mime_type,
            "file_size_bytes": artifact.file_size_bytes,
            "sha256": artifact.sha256,
            "download_available": True,
        }
        if artifact
        else None,
        "snapshot_hash": snapshot.payload_hash if snapshot else None,
    }
