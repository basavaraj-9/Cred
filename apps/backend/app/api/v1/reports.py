from __future__ import annotations

# ruff: noqa: E501, E701, E702
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.reporting import GeneratedReport, ReportSnapshot, ReportSourceLink
from app.services.reporting.service import CreditReportService, report_payload

router = APIRouter(tags=["credit reports"])


class GenerateReportRequest(BaseModel):
    actor_user_id: UUID
    report_type: str
    format: str = "PDF"
    committee_package_id: UUID | None = None


class FinalizeReportRequest(BaseModel):
    actor_user_id: UUID
    rationale: str | None = None


class SupersedeReportRequest(BaseModel):
    actor_user_id: UUID
    successor_report_id: UUID
    rationale: str


def _report(session: Session, report_id: UUID) -> GeneratedReport:
    row = session.get(GeneratedReport, report_id)
    if row is None:
        raise AppError("REPORT_NOT_FOUND", "Report not found", 404)
    return row


@router.post("/credit-review-cases/{review_case_id}/reports")
def generate_report(
    review_case_id: UUID,
    body: GenerateReportRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        with session.begin():
            row = CreditReportService(session, settings.storage_root).generate(
                review_case_id,
                body.actor_user_id,
                body.report_type,
                body.format,
                body.committee_package_id,
            )
        if row.status == "FAILED":
            raise AppError("REPORT_GENERATION_FAILED", "Report artifact generation failed", 500)
        return report_payload(session, row)
    except Exception:
        session.rollback()
        raise


@router.get("/reports/{report_id}")
def get_report(report_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    return report_payload(session, _report(session, report_id))


@router.get("/credit-review-cases/{review_case_id}/reports")
def list_reports(
    review_case_id: UUID,
    report_type: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    query = select(GeneratedReport).where(GeneratedReport.review_case_id == review_case_id)
    if report_type:
        query = query.where(GeneratedReport.report_type == report_type)
    if status:
        query = query.where(GeneratedReport.status == status)
    return [
        report_payload(session, x)
        for x in session.scalars(
            query.order_by(GeneratedReport.report_type, GeneratedReport.report_version)
        )
    ]


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: UUID,
    actor_user_id: UUID = Query(),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    _, artifact, path = CreditReportService(session, settings.storage_root).authorized_artifact(
        report_id, actor_user_id
    )
    return FileResponse(path, media_type=artifact.mime_type, filename=path.name)


@router.get("/reports/{report_id}/snapshot")
def get_report_snapshot(
    report_id: UUID,
    actor_user_id: UUID = Query(),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    CreditReportService(session, settings.storage_root).authorized_artifact(
        report_id, actor_user_id
    )
    row = session.scalar(
        select(ReportSnapshot).where(ReportSnapshot.generated_report_id == report_id)
    )
    if row is None:
        raise AppError("REPORT_SNAPSHOT_NOT_FOUND", "Report snapshot not found", 404)
    return {
        "report_id": report_id,
        "snapshot_version": row.snapshot_version,
        "payload_hash": row.payload_hash,
        "payload": row.payload_json,
    }


@router.get("/reports/{report_id}/evidence")
def get_report_evidence(
    report_id: UUID,
    actor_user_id: UUID = Query(),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, object]]:
    CreditReportService(session, settings.storage_root).authorized_artifact(
        report_id, actor_user_id
    )
    return [
        {
            "id": x.id,
            "source_type": x.source_type,
            "source_reference_id": x.source_reference_id,
            "lineage_role": x.lineage_role,
            "metadata": x.source_metadata_json,
        }
        for x in session.scalars(
            select(ReportSourceLink)
            .where(ReportSourceLink.generated_report_id == report_id)
            .order_by(ReportSourceLink.lineage_role)
        )
    ]


@router.post("/reports/{report_id}/finalize")
def finalize_report(
    report_id: UUID,
    body: FinalizeReportRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    with session.begin():
        row = CreditReportService(session, settings.storage_root).finalize(
            report_id, body.actor_user_id, body.rationale
        )
    return report_payload(session, row)


@router.get("/reports/{report_id}/versions")
def report_versions(report_id: UUID, session: Session = Depends(get_db)) -> list[dict[str, object]]:
    row = _report(session, report_id)
    return [
        report_payload(session, x)
        for x in session.scalars(
            select(GeneratedReport)
            .where(
                GeneratedReport.review_case_id == row.review_case_id,
                GeneratedReport.report_type == row.report_type,
            )
            .order_by(GeneratedReport.report_version)
        )
    ]


@router.post("/reports/{report_id}/supersede")
def supersede_report(
    report_id: UUID,
    body: SupersedeReportRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    with session.begin():
        row = CreditReportService(session, settings.storage_root).supersede(
            report_id,
            body.successor_report_id,
            body.actor_user_id,
            body.rationale,
        )
    return report_payload(session, row)
