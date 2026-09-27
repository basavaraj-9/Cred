from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
import math
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import desc, func, select, update
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.company import Company
from app.models.company_profile import CompanyProfile
from app.models.credit import CreditAssessment, CreditSubscore
from app.models.decision import (
    CreditDecisionGate,
    CreditDecisionSupport,
    CreditLimitPreparation,
    CreditPolicyException,
)
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.domain_classification import DomainClassification
from app.models.extracted_field import ExtractedField
from app.models.financial import FinancialLineItem, FinancialStatement
from app.models.financial_analysis import FinancialRatio, NormalizedFinancialValue
from app.models.financial_trend import FinancialAnomaly, FinancialTrend
from app.models.five_cs import FiveCsAssessment, FiveCsEvidence, FiveCsSection
from app.models.rag import (
    AnalystChatMessage,
    AnalystChatSession,
    RagAnswer,
    RagAnswerCitation,
    RagChunk,
    RagEmbedding,
    RagIndexRun,
    RagQueryRun,
    RagRetrievalResult,
)
from app.models.recommendation import CreditRecommendationFactor, CreditRecommendationPreparation
from app.models.reporting import GeneratedReport, ReportSnapshot
from app.models.research import ResearchEvidence, ResearchFinding, ResearchRun
from app.models.review import (
    CreditCommitteePackage,
    CreditHumanDecision,
    CreditInformationRequest,
    CreditReviewCase,
    CreditReviewComment,
)
from app.models.user import User

INDEX_VERSION = "credit_rag_index_v1"
CHUNK_BUILDER_VERSION = "credit_rag_chunk_builder_v1"
QUERY_CLASSIFIER_VERSION = "credit_analyst_query_classifier_v1"
PROMPT_VERSION = "credit_analyst_prompt_v1"
EMBEDDING_VERSION = "deterministic_hash_embedding_v1"


def _now() -> datetime:
    return datetime.now(UTC)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _enum(value: object) -> object:
    return getattr(value, "value", value)


def _record(row: object) -> dict[str, object]:
    excluded = {"input_hash", "payload_json", "storage_uri", "stored_filename", "email"}
    inspected = cast(Any, sa_inspect(row))
    result: dict[str, object] = {}
    for attribute in inspected.mapper.column_attrs:
        key = attribute.key
        if key in excluded or any(
            term in key.lower() for term in ("password", "secret", "token", "api_key")
        ):
            continue
        value = _enum(getattr(row, key))
        if isinstance(value, (UUID, datetime, date, Decimal)):
            value = str(value)
        if isinstance(value, (dict, list)):
            value = json.dumps(value, sort_keys=True, default=str)
        result[key] = value
    return result


def _structured_text(title: str, row: object) -> str:
    values = _record(row)
    return (
        title
        + "\n"
        + "\n".join(
            f"{key.replace('_', ' ').title()}: {value if value is not None else 'UNAVAILABLE'}"
            for key, value in values.items()
        )
    )


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimension: int
    version: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class DeterministicEmbeddingProvider:
    provider_name = "deterministic-local"
    model_name = "hash-token-embedding"
    dimension = 64
    version = EMBEDDING_VERSION

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _tokens(text):
            raw = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(raw[:4], "big") % self.dimension
            vector[index] += 1.0 if raw[4] % 2 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 10) for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class AnalystAnswerProvider(Protocol):
    provider_name: str
    model_name: str


class DeterministicAnalystAnswerProvider:
    """Offline answer provider marker; rendering remains policy controlled by the service."""

    provider_name = "deterministic-local"
    model_name = "structured-template-provider"


@dataclass
class ChunkPlan:
    source_type: str
    source_id: UUID
    version: str
    section: str
    text: str
    document_id: UUID | None = None
    page_number: int | None = None
    confidence: float | None = None
    status: str | None = None
    scope: str | None = None
    currency: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    published_at: date | None = None
    event_date: date | None = None
    metadata: dict[str, object] | None = None
    is_current: bool = True


class CreditRagIndexService:
    def __init__(self, session: Session, provider: EmbeddingProvider | None = None):
        self.session = session
        self.provider = provider or DeterministicEmbeddingProvider()
        self.retrieval_policy = self._policy("credit_rag_retrieval_policy_v1.json")
        self.security_policy = self._policy("rag_security_policy_v1.json")

    def _policy(self, filename: str) -> dict[str, Any]:
        return json.loads(Path(__file__).with_name(filename).read_text(encoding="utf-8"))

    def _user(self, user_id: UUID, *, admin: bool = False) -> User:
        user = self.session.get(User, user_id)
        roles = self.security_policy["retrieval_debug_roles" if admin else "authorized_roles"]
        if user is None or not user.is_active or user.reviewer_role not in roles:
            raise AppError(
                "RAG_ACTOR_NOT_AUTHORIZED", "Actor is not authorized for this RAG action", 403
            )
        return user

    def _sanitize(self, text: str) -> str:
        clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
        clean = re.sub(r"<script\b[^>]*>.*?</script>", "[SCRIPT REMOVED]", clean, flags=re.I | re.S)
        for phrase in self.security_policy["prompt_injection_phrases"]:
            clean = re.sub(re.escape(phrase), "[UNTRUSTED INSTRUCTION REMOVED]", clean, flags=re.I)
        return re.sub(r"\s+", " ", clean).strip()

    def _safe(self, text: str) -> bool:
        lowered = text.lower()
        return not any(term in lowered for term in self.security_policy["blocked_terms"])

    def _add_rows(
        self,
        plans: list[ChunkPlan],
        source_type: str,
        section: str,
        rows: Sequence[Any],
        *,
        document_attr: str = "document_id",
    ) -> None:
        for row in rows:
            text = self._sanitize(_structured_text(section, row))
            if not self._safe(text):
                continue
            value = _record(row)
            version = str(
                getattr(row, "input_hash", None)
                or getattr(row, "updated_at", None)
                or getattr(row, "created_at", None)
                or 1
            )
            current = (
                bool(getattr(row, "is_current", True))
                and str(getattr(row, "status", "")) != "SUPERSEDED"
            )
            plans.append(
                ChunkPlan(
                    source_type,
                    row.id,
                    version,
                    section,
                    text,
                    getattr(row, document_attr, None),
                    getattr(row, "page_number", None),
                    getattr(row, "confidence_score", getattr(row, "confidence", None)),
                    str(_enum(getattr(row, "status", ""))) or None,
                    str(_enum(getattr(row, "statement_scope", ""))) or None,
                    getattr(row, "currency", None),
                    getattr(row, "period_start", None),
                    getattr(row, "period_end", None),
                    getattr(row, "publication_date", None),
                    getattr(row, "event_date", None),
                    value,
                    current,
                )
            )

    def _discover(self, company_id: UUID) -> list[ChunkPlan]:
        if self.session.get(Company, company_id) is None:
            raise AppError("COMPANY_NOT_FOUND", "Company not found", 404)
        plans: list[ChunkPlan] = []
        documents = list(
            self.session.scalars(
                select(Document).where(Document.company_id == company_id).order_by(Document.id)
            )
        )
        for document in documents:
            for page in self.session.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == document.id)
                .order_by(DocumentPage.page_number)
            ):
                clean = self._sanitize(page.text_content)
                if not clean or not self._safe(clean):
                    continue
                starts = list(range(0, len(clean), 2100))
                for number, start in enumerate(starts, 1):
                    text = clean[max(0, start - 300) : start + 2400]
                    version = f"{page.parser_version}:{page.updated_at.isoformat()}:{number}"
                    plans.append(
                        ChunkPlan(
                            "DOCUMENT_PAGE",
                            page.id,
                            version,
                            "DOCUMENT_PAGE",
                            f"Document: {document.original_filename}\nPage: {page.page_number}\n{text}",
                            document.id,
                            page.page_number,
                            page.text_quality_score,
                            str(_enum(page.extraction_method)),
                            metadata={"filename": document.original_filename, "part": number},
                        )
                    )

        def direct(model: Any) -> list[Any]:
            return list(
                self.session.scalars(
                    select(model).where(model.company_id == company_id).order_by(model.id)
                )
            )

        profiles = direct(CompanyProfile)
        self._add_rows(plans, "COMPANY_PROFILE", "COMPANY_PROFILE", profiles)
        profile_ids = [row.id for row in profiles]
        if profile_ids:
            self._add_rows(
                plans,
                "COMPANY_PROFILE",
                "EXTRACTED_FIELD",
                list(
                    self.session.scalars(
                        select(ExtractedField)
                        .where(ExtractedField.company_profile_id.in_(profile_ids))
                        .order_by(ExtractedField.id)
                    )
                ),
            )
        self._add_rows(
            plans, "COMPANY_PROFILE", "DOMAIN_CLASSIFICATION", direct(DomainClassification)
        )
        self._add_rows(plans, "FINANCIAL_VALUE", "FINANCIAL_STATEMENT", direct(FinancialStatement))
        self._add_rows(plans, "FINANCIAL_VALUE", "FINANCIAL_LINE_ITEM", direct(FinancialLineItem))
        self._add_rows(
            plans, "FINANCIAL_VALUE", "NORMALIZED_FINANCIAL_VALUE", direct(NormalizedFinancialValue)
        )
        self._add_rows(plans, "FINANCIAL_RATIO", "FINANCIAL_RATIO", direct(FinancialRatio))
        self._add_rows(plans, "FINANCIAL_TREND", "FINANCIAL_TREND", direct(FinancialTrend))
        self._add_rows(plans, "FINANCIAL_ANOMALY", "FINANCIAL_ANOMALY", direct(FinancialAnomaly))
        assessments = direct(CreditAssessment)
        self._add_rows(plans, "CREDIT_ASSESSMENT", "CREDIT_ASSESSMENT", assessments)
        assessment_ids = [row.id for row in assessments]
        if assessment_ids:
            self._add_rows(
                plans,
                "CREDIT_ASSESSMENT",
                "CREDIT_SUBSCORE",
                list(
                    self.session.scalars(
                        select(CreditSubscore)
                        .where(CreditSubscore.credit_assessment_id.in_(assessment_ids))
                        .order_by(CreditSubscore.id)
                    )
                ),
            )
        five = direct(FiveCsAssessment)
        self._add_rows(plans, "FIVE_CS", "FIVE_CS_ASSESSMENT", five)
        five_ids = [row.id for row in five]
        if five_ids:
            sections = list(
                self.session.scalars(
                    select(FiveCsSection)
                    .where(FiveCsSection.five_cs_assessment_id.in_(five_ids))
                    .order_by(FiveCsSection.id)
                )
            )
            self._add_rows(plans, "FIVE_CS", "FIVE_CS_SECTION", sections)
            section_ids = [row.id for row in sections]
            if section_ids:
                self._add_rows(
                    plans,
                    "FIVE_CS",
                    "FIVE_CS_EVIDENCE",
                    list(
                        self.session.scalars(
                            select(FiveCsEvidence)
                            .where(FiveCsEvidence.five_cs_section_id.in_(section_ids))
                            .order_by(FiveCsEvidence.id)
                        )
                    ),
                )
        research_runs = direct(ResearchRun)
        run_ids = [row.id for row in research_runs]
        if run_ids:
            self._add_rows(
                plans,
                "RESEARCH_EVIDENCE",
                "RESEARCH_EVIDENCE",
                list(
                    self.session.scalars(
                        select(ResearchEvidence)
                        .where(ResearchEvidence.research_run_id.in_(run_ids))
                        .order_by(ResearchEvidence.id)
                    )
                ),
            )
            self._add_rows(
                plans,
                "RESEARCH_FINDING",
                "RESEARCH_FINDING",
                list(
                    self.session.scalars(
                        select(ResearchFinding)
                        .where(ResearchFinding.research_run_id.in_(run_ids))
                        .order_by(ResearchFinding.id)
                    )
                ),
            )
        recommendations = direct(CreditRecommendationPreparation)
        self._add_rows(plans, "RECOMMENDATION", "RECOMMENDATION", recommendations)
        recommendation_ids = [row.id for row in recommendations]
        if recommendation_ids:
            self._add_rows(
                plans,
                "RECOMMENDATION",
                "RECOMMENDATION_FACTOR",
                list(
                    self.session.scalars(
                        select(CreditRecommendationFactor)
                        .where(
                            CreditRecommendationFactor.recommendation_preparation_id.in_(
                                recommendation_ids
                            )
                        )
                        .order_by(CreditRecommendationFactor.id)
                    )
                ),
            )
        decisions = direct(CreditDecisionSupport)
        self._add_rows(plans, "DECISION_SUPPORT", "DECISION_SUPPORT", decisions)
        decision_ids = [row.id for row in decisions]
        if decision_ids:
            self._add_rows(
                plans,
                "POLICY_GATE",
                "POLICY_GATE",
                list(
                    self.session.scalars(
                        select(CreditDecisionGate)
                        .where(CreditDecisionGate.credit_decision_support_id.in_(decision_ids))
                        .order_by(CreditDecisionGate.id)
                    )
                ),
            )
            self._add_rows(
                plans,
                "POLICY_EXCEPTION",
                "POLICY_EXCEPTION",
                list(
                    self.session.scalars(
                        select(CreditPolicyException)
                        .where(CreditPolicyException.credit_decision_support_id.in_(decision_ids))
                        .order_by(CreditPolicyException.id)
                    )
                ),
            )
            self._add_rows(
                plans,
                "DECISION_SUPPORT",
                "ANALYTICAL_LIMIT",
                list(
                    self.session.scalars(
                        select(CreditLimitPreparation)
                        .where(CreditLimitPreparation.credit_decision_support_id.in_(decision_ids))
                        .order_by(CreditLimitPreparation.id)
                    )
                ),
            )
        cases = direct(CreditReviewCase)
        case_ids = [row.id for row in cases]
        if case_ids:
            self._add_rows(plans, "REVIEW_COMMENT", "REVIEW_CASE", cases)
            self._add_rows(
                plans,
                "REVIEW_COMMENT",
                "REVIEW_COMMENT",
                list(
                    self.session.scalars(
                        select(CreditReviewComment)
                        .where(CreditReviewComment.review_case_id.in_(case_ids))
                        .order_by(CreditReviewComment.id)
                    )
                ),
            )
            self._add_rows(
                plans,
                "RFI",
                "INFORMATION_REQUEST",
                list(
                    self.session.scalars(
                        select(CreditInformationRequest)
                        .where(CreditInformationRequest.review_case_id.in_(case_ids))
                        .order_by(CreditInformationRequest.id)
                    )
                ),
            )
            self._add_rows(
                plans,
                "HUMAN_DECISION",
                "HUMAN_DECISION",
                list(
                    self.session.scalars(
                        select(CreditHumanDecision)
                        .where(CreditHumanDecision.review_case_id.in_(case_ids))
                        .order_by(CreditHumanDecision.id)
                    )
                ),
            )
            self._add_rows(
                plans,
                "COMMITTEE_PACKAGE",
                "COMMITTEE_PACKAGE",
                list(
                    self.session.scalars(
                        select(CreditCommitteePackage)
                        .where(CreditCommitteePackage.review_case_id.in_(case_ids))
                        .order_by(CreditCommitteePackage.id)
                    )
                ),
            )
        reports = list(
            self.session.scalars(
                select(GeneratedReport)
                .where(GeneratedReport.company_id == company_id)
                .order_by(GeneratedReport.id)
            )
        )
        report_ids = [row.id for row in reports]
        if report_ids:
            snapshots = list(
                self.session.scalars(
                    select(ReportSnapshot)
                    .where(ReportSnapshot.generated_report_id.in_(report_ids))
                    .order_by(ReportSnapshot.id)
                )
            )
            for snapshot in snapshots:
                report = next(row for row in reports if row.id == snapshot.generated_report_id)
                navigation = {
                    "report_type": report.report_type,
                    "status": report.status,
                    "version": report.report_version,
                    "basis": snapshot.payload_json.get("basis"),
                    "disclaimer": snapshot.payload_json.get("disclaimer"),
                }
                plans.append(
                    ChunkPlan(
                        "REPORT_SNAPSHOT",
                        snapshot.id,
                        snapshot.payload_hash,
                        "REPORT_SNAPSHOT",
                        self._sanitize(
                            "Report snapshot navigation\n"
                            + json.dumps(navigation, sort_keys=True, default=str)
                        ),
                        report.document_id,
                        status=report.status,
                        metadata=navigation,
                        is_current=str(report.status) != "SUPERSEDED",
                    )
                )
        return sorted(
            plans, key=lambda item: (item.source_type, str(item.source_id), item.version, item.text)
        )

    def build(self, company_id: UUID, actor_id: UUID) -> RagIndexRun:
        actor = self._user(actor_id)
        plans = self._discover(company_id)
        manifest = [(p.source_type, str(p.source_id), p.version, _digest(p.text)) for p in plans]
        input_hash = _digest(
            {
                "manifest": manifest,
                "index": INDEX_VERSION,
                "builder": CHUNK_BUILDER_VERSION,
                "embedding": self.provider.version,
            }
        )
        existing = self.session.scalar(
            select(RagIndexRun).where(
                RagIndexRun.company_id == company_id,
                RagIndexRun.index_version == INDEX_VERSION,
                RagIndexRun.embedding_version == self.provider.version,
                RagIndexRun.input_hash == input_hash,
            )
        )
        if existing:
            return existing
        run = RagIndexRun(
            company_id=company_id,
            index_version=INDEX_VERSION,
            chunk_builder_version=CHUNK_BUILDER_VERSION,
            embedding_provider=self.provider.provider_name,
            embedding_model=self.provider.model_name,
            embedding_version=self.provider.version,
            status="BUILDING",
            source_count=len({(p.source_type, p.source_id) for p in plans}),
            chunk_count=0,
            new_chunk_count=0,
            input_hash=input_hash,
            started_at=_now(),
        )
        self.session.add(run)
        self.session.flush()
        write_audit_log(
            self.session,
            entity_type="rag_index_run",
            entity_id=run.id,
            action="RAG_INDEX_STARTED",
            event_type="RAG_INDEX_STARTED",
            company_id=company_id,
            user_id=actor.id,
            metadata_json={"index_version": INDEX_VERSION},
        )
        new_count = 0
        for plan in plans:
            chunk_hash = _digest(plan.text)
            chunk = self.session.scalar(
                select(RagChunk).where(
                    RagChunk.company_id == company_id,
                    RagChunk.source_type == plan.source_type,
                    RagChunk.source_reference_id == plan.source_id,
                    RagChunk.source_version == plan.version,
                    RagChunk.chunk_hash == chunk_hash,
                    RagChunk.index_version == INDEX_VERSION,
                )
            )
            if chunk is None:
                self.session.execute(
                    update(RagChunk)
                    .where(
                        RagChunk.company_id == company_id,
                        RagChunk.source_type == plan.source_type,
                        RagChunk.source_reference_id == plan.source_id,
                        RagChunk.is_current.is_(True),
                    )
                    .values(is_current=False)
                )
                priority = int(self.retrieval_policy["source_priorities"].get(plan.source_type, 9))
                chunk = RagChunk(
                    index_run_id=run.id,
                    company_id=company_id,
                    document_id=plan.document_id,
                    source_type=plan.source_type,
                    source_reference_id=plan.source_id,
                    source_version=plan.version,
                    section_type=plan.section,
                    chunk_text=plan.text,
                    chunk_hash=chunk_hash,
                    token_count=len(_tokens(plan.text)),
                    page_number=plan.page_number,
                    published_at=plan.published_at,
                    event_date=plan.event_date,
                    confidence_score=plan.confidence,
                    status=plan.status,
                    statement_scope=plan.scope,
                    currency=plan.currency,
                    period_start=plan.period_start,
                    period_end=plan.period_end,
                    source_priority=priority,
                    is_current=plan.is_current,
                    source_metadata_json=plan.metadata,
                    index_version=INDEX_VERSION,
                    created_at=_now(),
                )
                self.session.add(chunk)
                self.session.flush()
                new_count += 1
            embedding = self.session.scalar(
                select(RagEmbedding).where(
                    RagEmbedding.rag_chunk_id == chunk.id,
                    RagEmbedding.embedding_version == self.provider.version,
                )
            )
            if embedding is None:
                vector = self.provider.embed_documents([chunk.chunk_text])[0]
                self.session.add(
                    RagEmbedding(
                        rag_chunk_id=chunk.id,
                        embedding_provider=self.provider.provider_name,
                        embedding_model=self.provider.model_name,
                        embedding_version=self.provider.version,
                        dimension=self.provider.dimension,
                        embedding_json=vector,
                        embedding_hash=_digest(vector),
                        created_at=_now(),
                    )
                )
        run.new_chunk_count = new_count
        run.chunk_count = (
            self.session.scalar(
                select(func.count())
                .select_from(RagChunk)
                .where(RagChunk.company_id == company_id, RagChunk.is_current.is_(True))
            )
            or 0
        )
        run.status = "COMPLETED"
        run.completed_at = _now()
        write_audit_log(
            self.session,
            entity_type="rag_index_run",
            entity_id=run.id,
            action="RAG_INDEX_COMPLETED",
            event_type="RAG_INDEX_COMPLETED",
            company_id=company_id,
            user_id=actor.id,
            metadata_json={
                "source_count": run.source_count,
                "chunk_count": run.chunk_count,
                "new_chunk_count": new_count,
            },
        )
        return run


def classify_query(question: str) -> str:
    text = question.lower()
    patterns = [
        ("HUMAN_DECISION", ("approved", "declined", "human decision")),
        ("LIMIT", ("limit", "exposure ceiling", "loan amount")),
        ("LEGAL_REGULATORY", ("legal", "regulatory", "fraud", "investigation", "penalty")),
        ("RATING", ("rating", "downgrade", "upgrade")),
        ("FIVE_CS", ("capacity", "capital", "character", "collateral", "conditions", "five cs")),
        ("FINANCIAL_TREND", ("trend", "changed", "declined", "increased", "leverage")),
        ("FINANCIAL_METRIC", ("revenue", "ebitda", "debt", "equity", "interest coverage", "ratio")),
        ("REVIEW_WORKFLOW", ("review", "rfi", "unresolved", "exception")),
        ("COMMITTEE", ("committee",)),
        ("REPORT", ("cam", "report", "memorandum")),
        ("CREDIT_RISK", ("risk", "recommendation", "score")),
    ]
    return next(
        (kind for kind, words in patterns if any(word in text for word in words)),
        "GENERAL_COMPANY_INTELLIGENCE",
    )


def source_types_for_query(query_type: str) -> list[str] | None:
    mapping = {
        "HUMAN_DECISION": ["HUMAN_DECISION", "DECISION_SUPPORT"],
        "LIMIT": ["DECISION_SUPPORT", "HUMAN_DECISION"],
        "LEGAL_REGULATORY": ["RESEARCH_EVIDENCE", "RESEARCH_FINDING"],
        "RATING": ["RESEARCH_EVIDENCE", "RESEARCH_FINDING"],
        "FIVE_CS": ["FIVE_CS"],
        "FINANCIAL_TREND": ["FINANCIAL_TREND", "FINANCIAL_RATIO"],
        "FINANCIAL_METRIC": ["FINANCIAL_VALUE", "FINANCIAL_RATIO"],
        "REVIEW_WORKFLOW": ["REVIEW_COMMENT", "RFI", "POLICY_GATE", "POLICY_EXCEPTION"],
        "COMMITTEE": ["COMMITTEE_PACKAGE"],
        "REPORT": ["REPORT_SNAPSHOT"],
        "CREDIT_RISK": ["CREDIT_ASSESSMENT", "FIVE_CS", "RECOMMENDATION", "DECISION_SUPPORT"],
    }
    return mapping.get(query_type)


def _cosine(left: list[float], right: list[float]) -> float:
    return max(0.0, sum(a * b for a, b in zip(left, right, strict=True)))


class CreditAnalystAssistantService(CreditRagIndexService):
    def __init__(
        self,
        session: Session,
        provider: EmbeddingProvider | None = None,
        answer_provider: AnalystAnswerProvider | None = None,
    ):
        super().__init__(session, provider)
        self.answer_provider = answer_provider or DeterministicAnalystAnswerProvider()

    def retrieve(
        self,
        company_id: UUID,
        question: str,
        *,
        scope: str | None = None,
        period: str | None = None,
        source_types: list[str] | None = None,
    ) -> list[tuple[RagChunk, float, float, float]]:
        latest = self.session.scalar(
            select(RagIndexRun)
            .where(RagIndexRun.company_id == company_id, RagIndexRun.status == "COMPLETED")
            .order_by(desc(RagIndexRun.created_at))
            .limit(1)
        )
        if latest is None:
            raise AppError(
                "RAG_INDEX_NOT_FOUND", "Build the company RAG index before asking questions", 409
            )
        query = (
            select(RagChunk, RagEmbedding)
            .join(RagEmbedding, RagEmbedding.rag_chunk_id == RagChunk.id)
            .where(
                RagChunk.company_id == company_id,
                RagChunk.index_version == latest.index_version,
                RagEmbedding.embedding_version == latest.embedding_version,
            )
        )
        if scope:
            query = query.where(
                (RagChunk.statement_scope == scope) | (RagChunk.statement_scope.is_(None))
            )
        source_types = source_types or source_types_for_query(classify_query(question))
        if source_types:
            query = query.where(RagChunk.source_type.in_(source_types))
        rows = list(self.session.execute(query.order_by(RagChunk.id)))
        qvec = self.provider.embed_query(question)
        qtokens = set(_tokens(question))
        scored = []
        for chunk, embedding in rows:
            semantic = _cosine(qvec, embedding.embedding_json)
            ctokens = set(_tokens(chunk.chunk_text))
            keyword = len(qtokens & ctokens) / max(1, len(qtokens))
            priority = 1 - (chunk.source_priority - 1) / 9
            confidence = chunk.confidence_score if chunk.confidence_score is not None else 0.5
            current = 1.0 if chunk.is_current else 0.0
            combined = (
                0.45 * semantic
                + 0.35 * keyword
                + 0.10 * priority
                + 0.05 * confidence
                + 0.05 * current
            )
            if period and period.lower() not in chunk.chunk_text.lower():
                combined *= 0.5
            if combined >= float(self.retrieval_policy["minimum_relevance"]):
                scored.append((chunk, semantic, keyword, combined))
        scored.sort(key=lambda item: (-item[3], item[0].source_priority, str(item[0].id)))
        selected: list[tuple[RagChunk, float, float, float]] = []
        counts: dict[str, int] = {}
        for item in scored:
            source_type = item[0].source_type
            if counts.get(source_type, 0) >= int(
                self.retrieval_policy["max_chunks_per_source_type"]
            ):
                continue
            selected.append(item)
            counts[source_type] = counts.get(source_type, 0) + 1
            if len(selected) >= int(self.retrieval_policy["top_k"]):
                break
        return selected

    def ask(
        self,
        company_id: UUID,
        actor_id: UUID,
        question: str,
        *,
        scope: str | None = None,
        period: str | None = None,
        session_id: UUID | None = None,
    ) -> RagAnswer:
        started = time.perf_counter()
        actor = self._user(actor_id)
        if not question.strip() or len(question) > int(
            self.security_policy["max_question_characters"]
        ):
            raise AppError("RAG_QUESTION_INVALID", "Question is empty or too long", 422)
        chat = self.session.get(AnalystChatSession, session_id) if session_id else None
        if chat and (chat.user_id != actor.id or chat.company_id not in {None, company_id}):
            raise AppError(
                "ANALYST_SESSION_FORBIDDEN",
                "Session does not belong to this actor and company",
                403,
            )
        query_type = classify_query(question)
        user_message = None
        if chat:
            user_message = AnalystChatMessage(
                session_id=chat.id,
                role="USER",
                content=question.strip(),
                query_type=query_type,
                created_at=_now(),
            )
            self.session.add(user_message)
            self.session.flush()
        retrieved = self.retrieve(company_id, question, scope=scope, period=period)
        query_run = RagQueryRun(
            session_id=chat.id if chat else None,
            user_message_id=user_message.id if user_message else None,
            company_id=company_id,
            actor_user_id=actor.id,
            query_text=question.strip(),
            query_type=query_type,
            filters_json={"scope": scope, "period": period},
            retrieval_policy_version=self.retrieval_policy["version"],
            chunk_index_version=INDEX_VERSION,
            model_provider=self.answer_provider.provider_name,
            model_name=self.answer_provider.model_name,
            prompt_version=PROMPT_VERSION,
            status="COMPLETED",
            input_hash=_digest(
                {
                    "company": str(company_id),
                    "question": question.strip(),
                    "scope": scope,
                    "period": period,
                    "index": INDEX_VERSION,
                }
            ),
            created_at=_now(),
        )
        self.session.add(query_run)
        self.session.flush()
        write_audit_log(
            self.session,
            entity_type="rag_query_run",
            entity_id=query_run.id,
            action="ANALYST_QUERY_RECEIVED",
            event_type="ANALYST_QUERY_RECEIVED",
            company_id=company_id,
            user_id=actor.id,
            metadata_json={"query_type": query_type},
        )
        for rank, (chunk, semantic, keyword, combined) in enumerate(retrieved, 1):
            self.session.add(
                RagRetrievalResult(
                    rag_query_run_id=query_run.id,
                    rag_chunk_id=chunk.id,
                    rank=rank,
                    semantic_score=semantic,
                    keyword_score=keyword,
                    combined_score=combined,
                    selected_for_context=True,
                    created_at=_now(),
                )
            )
        write_audit_log(
            self.session,
            entity_type="rag_query_run",
            entity_id=query_run.id,
            action="RAG_RETRIEVAL_COMPLETED",
            event_type="RAG_RETRIEVAL_COMPLETED",
            company_id=company_id,
            user_id=actor.id,
            metadata_json={"retrieved_count": len(retrieved)},
        )
        answer_text, status, used = self._answer(question, query_type, retrieved)
        confidence = round(sum(item[3] for item in used) / len(used), 4) if used else 0.0
        answer = RagAnswer(
            rag_query_run_id=query_run.id,
            answer_text=answer_text,
            answer_status=status,
            confidence_score=confidence,
            citation_count=len(used),
            unsupported_claim_count=0,
            citation_coverage_ratio=1.0 if used else 0.0,
            created_at=_now(),
        )
        self.session.add(answer)
        self.session.flush()
        for index, item in enumerate(used, 1):
            chunk = item[0]
            self.session.add(
                RagAnswerCitation(
                    rag_answer_id=answer.id,
                    rag_chunk_id=chunk.id,
                    citation_index=index,
                    claim_text=chunk.chunk_text[:500],
                    source_type=chunk.source_type,
                    source_reference_id=chunk.source_reference_id,
                    created_at=_now(),
                )
            )
        query_run.status = (
            "COMPLETED" if status in {"ANSWERED", "PARTIAL", "REQUIRES_HUMAN_REVIEW"} else status
        )
        query_run.latency_ms = int((time.perf_counter() - started) * 1000)
        if chat:
            self.session.add(
                AnalystChatMessage(
                    session_id=chat.id,
                    role="ASSISTANT",
                    content=answer_text,
                    query_type=query_type,
                    answer_status=status,
                    prompt_version=PROMPT_VERSION,
                    model_provider=self.answer_provider.provider_name,
                    model_name=self.answer_provider.model_name,
                    created_at=_now(),
                )
            )
        event = (
            "ANALYST_ANSWER_INSUFFICIENT_EVIDENCE"
            if status == "INSUFFICIENT_EVIDENCE"
            else "ANALYST_ANSWER_CONFLICTING_EVIDENCE"
            if status == "CONFLICTING_EVIDENCE"
            else "ANALYST_ANSWER_GENERATED"
        )
        write_audit_log(
            self.session,
            entity_type="rag_answer",
            entity_id=answer.id,
            action=event,
            event_type=event,
            company_id=company_id,
            user_id=actor.id,
            metadata_json={
                "status": status,
                "citation_count": len(used),
                "latency_ms": query_run.latency_ms,
            },
        )
        return answer

    def _answer(
        self, question: str, query_type: str, retrieved: list[tuple[RagChunk, float, float, float]]
    ) -> tuple[str, str, list[tuple[RagChunk, float, float, float]]]:
        relevant = retrieved
        preferred = {
            "HUMAN_DECISION": {"HUMAN_DECISION", "DECISION_SUPPORT"},
            "LIMIT": {"DECISION_SUPPORT", "HUMAN_DECISION"},
            "FINANCIAL_METRIC": {"FINANCIAL_VALUE", "FINANCIAL_RATIO"},
            "FINANCIAL_TREND": {"FINANCIAL_TREND", "FINANCIAL_RATIO"},
            "FIVE_CS": {"FIVE_CS"},
            "LEGAL_REGULATORY": {"RESEARCH_EVIDENCE", "RESEARCH_FINDING"},
            "RATING": {"RESEARCH_EVIDENCE", "RESEARCH_FINDING"},
            "REVIEW_WORKFLOW": {"REVIEW_COMMENT", "RFI", "POLICY_GATE", "POLICY_EXCEPTION"},
            "COMMITTEE": {"COMMITTEE_PACKAGE"},
            "REPORT": {"REPORT_SNAPSHOT"},
        }
        if query_type in preferred:
            filtered = [item for item in retrieved if item[0].source_type in preferred[query_type]]
            relevant = filtered
        if not relevant:
            return "Insufficient evidence in the indexed sources.", "INSUFFICIENT_EVIDENCE", []
        if query_type == "REPORT" and not any(
            item[0].source_type == "REPORT_SNAPSHOT" for item in relevant
        ):
            return (
                "No matching report is available in the indexed sources.",
                "INSUFFICIENT_EVIDENCE",
                [],
            )
        lower = question.lower()
        if "collateral value" in lower and not any(
            "verified collateral" in item[0].chunk_text.lower()
            and "unavailable" not in item[0].chunk_text.lower()
            for item in relevant
        ):
            used = relevant[:1]
            return (
                "Independent collateral value is unavailable in the indexed evidence. The available collateral record remains evidence for human review. [1]",
                "INSUFFICIENT_EVIDENCE",
                used,
            )
        lines = []
        for index, item in enumerate(relevant[:4], 1):
            chunk = item[0]
            excerpt = " ".join(chunk.chunk_text.split())[:700]
            lines.append(f"{excerpt} [{index}]")
        status = (
            "CONFLICTING_EVIDENCE"
            if any((item[0].status or "").upper() == "CONFLICTING" for item in relevant)
            else "ANSWERED"
        )
        if query_type == "LIMIT" and any(term in lower for term in ("should", "give", "recommend")):
            lines.insert(
                0,
                "The assistant does not independently choose a sanctioned lending limit. It can report the persisted analytical ceiling and any recorded human-approved limit.",
            )
            status = "REQUIRES_HUMAN_REVIEW"
        if query_type == "HUMAN_DECISION" and not any(
            item[0].source_type == "HUMAN_DECISION" for item in relevant
        ):
            lines.insert(
                0,
                "No human approval or decline has been recorded. Any system recommendation shown below is advisory.",
            )
        if query_type == "LEGAL_REGULATORY" and "fraud" in lower:
            lines.insert(
                0,
                "The indexed evidence is reported with its original legal status; an allegation or investigation does not establish a confirmed fraud finding.",
            )
        lines.append(
            "This response summarizes persisted evidence and does not make or change a lending decision."
        )
        return "\n\n".join(lines), status, relevant[:4]


def answer_payload(session: Session, answer: RagAnswer) -> dict[str, object]:
    citations = list(
        session.scalars(
            select(RagAnswerCitation)
            .where(RagAnswerCitation.rag_answer_id == answer.id)
            .order_by(RagAnswerCitation.citation_index)
        )
    )
    chunks = (
        {
            chunk.id: chunk
            for chunk in session.scalars(
                select(RagChunk).where(
                    RagChunk.id.in_([citation.rag_chunk_id for citation in citations])
                )
            )
        }
        if citations
        else {}
    )
    return {
        "answer_id": answer.id,
        "query_run_id": answer.rag_query_run_id,
        "answer": answer.answer_text,
        "status": answer.answer_status,
        "confidence": answer.confidence_score,
        "citation_coverage_ratio": answer.citation_coverage_ratio,
        "unsupported_claim_count": answer.unsupported_claim_count,
        "citations": [
            {
                "index": citation.citation_index,
                "source_type": citation.source_type,
                "source_reference_id": citation.source_reference_id,
                "chunk_id": citation.rag_chunk_id,
                "evidence_text": chunks[citation.rag_chunk_id].chunk_text,
                "page_number": chunks[citation.rag_chunk_id].page_number,
                "status": chunks[citation.rag_chunk_id].status,
                "confidence": chunks[citation.rag_chunk_id].confidence_score,
                "metadata": chunks[citation.rag_chunk_id].source_metadata_json,
            }
            for citation in citations
        ],
    }
