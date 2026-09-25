import hashlib
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.enums import AnalysisStage, FinancialStatus, ParserStatus
from app.models.financial import FinancialExtractionRun, FinancialLineItem, FinancialStatement
from app.services.financial_engine.extractor import EXTRACTOR_VERSION, extract, reconcile
from app.services.financial_engine.taxonomy import TAXONOMY_VERSION


def _hash_pages(pages: Sequence[DocumentPage]) -> str:
    digest = hashlib.sha256()
    for page in pages:
        digest.update(
            f"{page.page_number}:{page.extraction_method}:{page.parser_version}:".encode()
        )
        digest.update(page.text_content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _summary(session: Session, run: FinancialExtractionRun) -> dict:
    statement_ids = session.scalars(
        select(FinancialStatement.id).where(FinancialStatement.run_id == run.id)
    ).all()
    counts = (
        Counter(
            session.scalars(
                select(FinancialLineItem.status).where(
                    FinancialLineItem.financial_statement_id.in_(statement_ids)
                )
            ).all()
        )
        if statement_ids
        else Counter()
    )
    return {
        "document_id": run.document_id,
        "extractor_version": run.extractor_version,
        "taxonomy_version": run.taxonomy_version,
        "status": run.status,
        "statements_found": run.statement_count,
        "line_items_extracted": run.line_item_count,
        "verified_items": counts[FinancialStatus.VERIFIED],
        "review_items": counts[FinancialStatus.NEEDS_REVIEW],
        "conflicting_items": counts[FinancialStatus.CONFLICTING],
        "unmapped_items": counts[FinancialStatus.UNMAPPED],
    }


def extract_financial_statements(session: Session, document_id: UUID) -> dict:
    with session.begin():
        document = session.get(Document, document_id, with_for_update=True)
        if document is None:
            raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
        if document.parser_status not in {
            ParserStatus.PARSED,
            ParserStatus.PARTIAL,
            ParserStatus.REVIEW_REQUIRED,
        }:
            raise AppError(
                "DOCUMENT_NOT_PARSED", "Document must be parsed before financial extraction", 409
            )
        pages = session.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        ).all()
        if not pages:
            raise AppError("DOCUMENT_NOT_PARSED", "No parsed pages are available", 409)
        input_hash = _hash_pages(pages)
        existing = session.scalar(
            select(FinancialExtractionRun).where(
                FinancialExtractionRun.document_id == document_id,
                FinancialExtractionRun.extractor_version == EXTRACTOR_VERSION,
                FinancialExtractionRun.taxonomy_version == TAXONOMY_VERSION,
                FinancialExtractionRun.input_hash == input_hash,
            )
        )
        if existing:
            return _summary(session, existing)

        def audit(action: str, metadata: dict[str, object] | None = None) -> None:
            write_audit_log(
                session,
                entity_type="document",
                entity_id=document.id,
                action=action,
                event_type=action,
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
                metadata_json=metadata,
            )

        audit("FINANCIAL_EXTRACTION_STARTED", {"input_hash": input_hash})
        document.analysis_job.current_stage = AnalysisStage.FINANCIAL_EXTRACTION
        drafts = extract(pages)
        reconcile(drafts)
        all_candidates = [candidate for draft in drafts for candidate in draft.candidates]
        if not drafts:
            status = FinancialStatus.UNAVAILABLE
        elif any(item.status == FinancialStatus.CONFLICTING for item in all_candidates):
            status = FinancialStatus.CONFLICTING
        elif document.parser_status != ParserStatus.PARSED or any(
            page.ocr_required and not page.ocr_succeeded for page in pages
        ):
            status = FinancialStatus.NEEDS_REVIEW
        elif len({draft.statement_type for draft in drafts}) < 3 or any(
            item.status != FinancialStatus.VERIFIED for item in all_candidates
        ):
            status = FinancialStatus.PARTIAL
        else:
            status = FinancialStatus.VERIFIED
        run = FinancialExtractionRun(
            document_id=document.id,
            analysis_job_id=document.analysis_job_id,
            extractor_version=EXTRACTOR_VERSION,
            taxonomy_version=TAXONOMY_VERSION,
            input_hash=input_hash,
            status=status,
            statement_count=0,
            line_item_count=len(all_candidates),
            completed_at=datetime.now(UTC),
        )
        session.add(run)
        session.flush()
        for draft in drafts:
            years = {
                item.period.fiscal_year: item.period for item in draft.candidates if item.period
            }
            # Each reporting column is a distinct statement, preserving comparatives.
            period_entries = list(years.items()) if years else [(None, None)]
            for year, period in period_entries:
                candidates = [
                    item
                    for item in draft.candidates
                    if (item.period.fiscal_year if item.period else None) == year
                ]
                if not candidates:
                    continue
                states = {item.status for item in candidates}
                statement_status = (
                    FinancialStatus.CONFLICTING
                    if FinancialStatus.CONFLICTING in states
                    else FinancialStatus.PARTIAL
                    if states - {FinancialStatus.VERIFIED}
                    else FinancialStatus.VERIFIED
                )
                if (
                    document.parser_status != ParserStatus.PARSED
                    and statement_status == FinancialStatus.VERIFIED
                ):
                    statement_status = FinancialStatus.NEEDS_REVIEW
                statement = FinancialStatement(
                    run_id=run.id,
                    analysis_job_id=document.analysis_job_id,
                    company_id=document.company_id,
                    document_id=document.id,
                    statement_type=draft.statement_type,
                    statement_scope=draft.statement_scope,
                    period_end=period.end if period else None,
                    fiscal_year=year,
                    period_label=period.label if period else None,
                    currency=draft.currency,
                    raw_unit=draft.raw_unit,
                    normalized_unit=draft.normalized_unit,
                    unit_multiplier=draft.unit_multiplier,
                    start_page_number=draft.start_page,
                    end_page_number=draft.end_page,
                    status=statement_status,
                    confidence_score=round(
                        sum(item.confidence for item in candidates) / len(candidates), 2
                    ),
                    taxonomy_version=TAXONOMY_VERSION,
                    extractor_version=EXTRACTOR_VERSION,
                )
                session.add(statement)
                session.flush()
                run.statement_count += 1
                audit(
                    "FINANCIAL_STATEMENT_FOUND",
                    {
                        "statement_id": str(statement.id),
                        "type": draft.statement_type,
                        "fiscal_year": year,
                    },
                )
                for item in candidates:
                    session.add(
                        FinancialLineItem(
                            financial_statement_id=statement.id,
                            analysis_job_id=document.analysis_job_id,
                            company_id=document.company_id,
                            document_id=document.id,
                            document_page_id=item.page.id,
                            canonical_name=item.canonical_name,
                            raw_label=item.raw_label,
                            measurement_type=item.measurement_type,
                            raw_value=item.raw_value,
                            numeric_value=item.numeric_value,
                            raw_column_header=item.period.label if item.period else None,
                            currency=item.currency,
                            raw_unit=item.raw_unit,
                            normalized_unit=item.normalized_unit,
                            unit_multiplier=item.unit_multiplier,
                            period_end=item.period.end if item.period else None,
                            fiscal_year=item.period.fiscal_year if item.period else None,
                            period_label=item.period.label if item.period else None,
                            page_number=item.page.page_number,
                            evidence_text=item.evidence_text,
                            confidence_score=item.confidence,
                            status=item.status,
                            source_priority=item.source_priority,
                            extractor_version=EXTRACTOR_VERSION,
                            taxonomy_version=TAXONOMY_VERSION,
                        )
                    )
        session.flush()
        if any(item.status == FinancialStatus.CONFLICTING for item in all_candidates):
            audit(
                "FINANCIAL_EXTRACTION_CONFLICT",
                {
                    "count": sum(
                        item.status == FinancialStatus.CONFLICTING for item in all_candidates
                    )
                },
            )
        completion_event = (
            "FINANCIAL_EXTRACTION_FAILED"
            if status == FinancialStatus.UNAVAILABLE
            else "FINANCIAL_EXTRACTION_COMPLETED"
            if status == FinancialStatus.VERIFIED
            else "FINANCIAL_EXTRACTION_PARTIAL"
        )
        audit(
            completion_event,
            {
                "status": status,
                "statements": run.statement_count,
                "line_items": run.line_item_count,
            },
        )
        return _summary(session, run)


def latest_run(session: Session, document_id: UUID) -> FinancialExtractionRun | None:
    return session.scalar(
        select(FinancialExtractionRun)
        .where(FinancialExtractionRun.document_id == document_id)
        .order_by(FinancialExtractionRun.created_at.desc())
    )
