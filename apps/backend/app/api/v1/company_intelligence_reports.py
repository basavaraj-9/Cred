from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.reporting import GeneratedReport, ReportArtifact, ReportSnapshot, ReportSourceLink
from app.runtime.storage import checked_artifact
from app.services.reporting.company_intelligence import (
    REPORT_TYPE,
    CompanyIntelligenceReportService,
)
from app.services.reporting.service import report_payload

router = APIRouter(prefix="/company-intelligence-reports", tags=["company intelligence reports"])


class CreateReportRequest(BaseModel):
    actor_user_id: UUID
    company_id: UUID
    analysis_job_id: UUID | None = None
    as_of_date: date | None = None
    include_stock: bool = True
    include_credit: bool = True


class FinalizeRequest(BaseModel):
    actor_user_id: UUID
    rationale: str | None = None


class SupersedeRequest(BaseModel):
    actor_user_id: UUID
    successor_report_id: UUID
    rationale: str


def _report(session: Session, report_id: UUID) -> GeneratedReport:
    report = session.get(GeneratedReport, report_id)
    if report is None or report.report_type != REPORT_TYPE:
        raise AppError("REPORT_NOT_FOUND", "360 company intelligence report not found", 404)
    return report


@router.post("")
def create_report(
    body: CreateReportRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    with session.begin():
        report = CompanyIntelligenceReportService(session, settings.storage_root).generate(
            body.company_id,
            body.actor_user_id,
            body.analysis_job_id,
            body.as_of_date,
            body.include_stock,
            body.include_credit,
        )
    return report_payload(session, report)


@router.get("")
def list_reports(
    actor_user_id: UUID,
    company: UUID | None = None,
    status: str | None = None,
    version: int | None = None,
    as_of_date: date | None = None,
    limit: int = Query(100, ge=1, le=200),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, object]]:
    CompanyIntelligenceReportService(session, settings.storage_root)._user(actor_user_id)
    query = select(GeneratedReport).where(GeneratedReport.report_type == REPORT_TYPE)
    if company:
        query = query.where(GeneratedReport.company_id == company)
    if status:
        query = query.where(GeneratedReport.status == status)
    if version:
        query = query.where(GeneratedReport.report_version == version)
    if as_of_date:
        query = query.where(GeneratedReport.analytical_as_of_date == as_of_date)
    reports = list(
        session.scalars(query.order_by(GeneratedReport.generated_at.desc()).limit(limit))
    )
    ids = [item.id for item in reports]
    artifacts: dict[UUID, list[ReportArtifact]] = {item.id: [] for item in reports}
    for artifact in session.scalars(
        select(ReportArtifact).where(ReportArtifact.generated_report_id.in_(ids))
    ):
        artifacts[artifact.generated_report_id].append(artifact)
    snapshots = {
        item.generated_report_id: item
        for item in session.scalars(
            select(ReportSnapshot).where(ReportSnapshot.generated_report_id.in_(ids))
        )
    }
    return [
        report_payload(session, item, artifacts[item.id], snapshots.get(item.id))
        for item in reports
    ]


@router.get("/{report_id}")
def get_report(
    report_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    CompanyIntelligenceReportService(session, settings.storage_root)._user(actor_user_id)
    return report_payload(session, _report(session, report_id))


@router.get("/{report_id}/snapshot")
def snapshot(
    report_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    CompanyIntelligenceReportService(session, settings.storage_root)._user(actor_user_id)
    _report(session, report_id)
    item = session.scalar(
        select(ReportSnapshot).where(ReportSnapshot.generated_report_id == report_id)
    )
    if item is None:
        raise AppError("REPORT_SNAPSHOT_NOT_FOUND", "Report snapshot not found", 404)
    return {"report_id": report_id, "payload_hash": item.payload_hash, "payload": item.payload_json}


@router.get("/{report_id}/evidence")
def evidence(
    report_id: UUID,
    actor_user_id: UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> list[dict[str, object]]:
    CompanyIntelligenceReportService(session, settings.storage_root)._user(actor_user_id)
    _report(session, report_id)
    return [
        {
            "id": item.id,
            "source_type": item.source_type,
            "source_reference_id": item.source_reference_id,
            "lineage_role": item.lineage_role,
            "metadata": item.source_metadata_json,
        }
        for item in session.scalars(
            select(ReportSourceLink)
            .where(ReportSourceLink.generated_report_id == report_id)
            .order_by(
                ReportSourceLink.lineage_role, ReportSourceLink.source_type, ReportSourceLink.id
            )
            .offset(offset)
            .limit(limit)
        )
    ]


def _artifact(
    report_id: UUID,
    artifact_format: str,
    actor_user_id: UUID,
    session: Session,
    settings: Settings,
) -> FileResponse:
    CompanyIntelligenceReportService(session, settings.storage_root)._user(actor_user_id)
    _report(session, report_id)
    item = session.scalar(
        select(ReportArtifact).where(
            ReportArtifact.generated_report_id == report_id,
            ReportArtifact.format == artifact_format,
        )
    )
    if item is None:
        raise AppError("REPORT_ARTIFACT_NOT_FOUND", "Report artifact not found", 404)
    try:
        path = checked_artifact(settings.storage_root, item.storage_path, item.sha256)
    except AppError as exc:
        code = (
            "REPORT_ARTIFACT_INTEGRITY_FAILED"
            if exc.status_code == 409
            else "REPORT_ARTIFACT_UNAVAILABLE"
        )
        raise AppError(
            code,
            "Report artifact unavailable or integrity check failed",
            409 if exc.status_code == 409 else 404,
        ) from exc
    return FileResponse(path, media_type=item.mime_type, filename=path.name)


@router.get("/{report_id}/artifacts/pdf")
def pdf_artifact(
    report_id: UUID,
    actor_user_id: UUID = Query(),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    return _artifact(report_id, "PDF", actor_user_id, session, settings)


@router.get("/{report_id}/artifacts/json")
def json_artifact(
    report_id: UUID,
    actor_user_id: UUID = Query(),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    return _artifact(report_id, "JSON", actor_user_id, session, settings)


@router.post("/{report_id}/finalize")
def finalize(
    report_id: UUID,
    body: FinalizeRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    with session.begin():
        report = CompanyIntelligenceReportService(session, settings.storage_root).finalize(
            report_id, body.actor_user_id, body.rationale
        )
    return report_payload(session, report)


@router.post("/{report_id}/supersede")
def supersede(
    report_id: UUID,
    body: SupersedeRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    with session.begin():
        report = CompanyIntelligenceReportService(session, settings.storage_root).supersede(
            report_id,
            body.successor_report_id,
            body.actor_user_id,
            body.rationale,
        )
    return report_payload(session, report)
