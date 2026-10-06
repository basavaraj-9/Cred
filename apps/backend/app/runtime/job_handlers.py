"""Whitelisted adapters delegate to existing analytical services without new scoring logic."""

from typing import Any
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.runtime.job_api import (
    DatasetJob,
    JobRequest,
    MonitoringJob,
    ParseJob,
    ReportJob,
    ResearchJob,
    TrainJob,
)


def execute(
    session: Session,
    settings: Settings,
    job_type: str,
    data: dict[str, Any],
    actor_id: UUID,
) -> dict[str, Any]:
    body: JobRequest = TypeAdapter(JobRequest).validate_python(
        {**data, "job_type": job_type, "idempotency_key": "worker-validation"}
    )
    if isinstance(body, ReportJob):
        from app.services.reporting.company_intelligence import CompanyIntelligenceReportService

        with session.begin():
            report = CompanyIntelligenceReportService(session, settings.storage_root).generate(
                body.company_id,
                actor_id,
                body.analysis_job_id,
                body.as_of_date,
                body.include_stock,
                body.include_credit,
            )
            return {"report_id": str(report.id)}
    if isinstance(body, ResearchJob):
        if not settings.external_research_enabled:
            raise AppError("FEATURE_DISABLED", "External research is disabled", 409)
        from app.services.external_research.service import ExternalResearchService

        with session.begin():
            research = ExternalResearchService(session).research_company(
                body.company_id, body.scopes, body.refresh
            )
            return {"research_run_id": str(research.id)}
    if isinstance(body, DatasetJob):
        if not settings.stock_ml_research_enabled:
            raise AppError("FEATURE_DISABLED", "Stock ML research is disabled", 409)
        from app.services.stock_ml.service import StockMlDatasetBuilder

        with session.begin():
            dataset = StockMlDatasetBuilder(session).build(
                body.start_date,
                body.end_date,
                actor_id,
                body.label_horizon,
                body.feature_set_version,
            )
            return {"dataset_id": str(dataset.id)}
    if isinstance(body, TrainJob):
        if not settings.stock_ml_research_enabled:
            raise AppError("FEATURE_DISABLED", "Stock ML research is disabled", 409)
        from app.services.stock_ml.service import StockModelTrainer

        with session.begin():
            runs = StockModelTrainer(session).train(body.split_id, actor_id, body.models)
            return {"run_ids": [str(run.id) for run in runs]}
    if isinstance(body, MonitoringJob):
        from app.services.stock_monitoring.service import StockMonitoringService

        with session.begin():
            monitoring = StockMonitoringService(session).build_monitoring_run(
                body.reference_start_date,
                body.reference_end_date,
                body.current_start_date,
                body.current_end_date,
                actor_id,
            )
            return {"monitoring_run_id": str(monitoring.id)}
    if isinstance(body, ParseJob):
        from app.services.document_intelligence.ocr import TesseractOCR
        from app.services.document_intelligence.service import parse_document
        from app.services.storage.local import LocalStorage

        parsed = parse_document(
            session,
            LocalStorage(settings.storage_root),
            TesseractOCR(settings),
            settings,
            body.document_id,
        )
        return parsed.model_dump(mode="json")
    raise AppError("VALIDATION_ERROR", "Unsupported job type", 422)
