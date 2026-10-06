from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.runtime import BackgroundJob, JobAttempt
from app.runtime import jobs
from app.runtime.queue import job_queue
from app.runtime.security import Principal, authorize_request, require_permission


class JobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=128)


class ReportJob(JobInput):
    job_type: Literal["REPORT_360"]
    company_id: UUID
    analysis_job_id: UUID | None = None
    as_of_date: date | None = None
    include_stock: bool = True
    include_credit: bool = True


class ResearchJob(JobInput):
    job_type: Literal["RESEARCH"]
    company_id: UUID
    scopes: list[str] = Field(min_length=1, max_length=20)
    refresh: bool = False


class DatasetJob(JobInput):
    job_type: Literal["STOCK_DATASET"]
    start_date: date
    end_date: date
    label_horizon: Literal["1M", "3M", "6M", "12M"] = "3M"
    feature_set_version: str = Field(default="stock_features_v1", max_length=80)

    @model_validator(mode="after")
    def bounded_dates(self) -> DatasetJob:
        if not 0 <= (self.end_date - self.start_date).days <= 3650:
            raise ValueError("Date range must be ordered and no longer than ten years")
        return self


class TrainJob(JobInput):
    job_type: Literal["STOCK_TRAIN"]
    split_id: UUID
    models: list[str] | None = Field(default=None, max_length=10)


class MonitoringJob(JobInput):
    job_type: Literal["MONITORING"]
    reference_start_date: date
    reference_end_date: date
    current_start_date: date
    current_end_date: date

    @model_validator(mode="after")
    def bounded_dates(self) -> MonitoringJob:
        if not (
            self.reference_start_date
            <= self.reference_end_date
            < self.current_start_date
            <= self.current_end_date
        ):
            raise ValueError("Monitoring windows must be ordered and non-overlapping")
        if (self.current_end_date - self.reference_start_date).days > 3650:
            raise ValueError("Monitoring range exceeds ten years")
        return self


class ParseJob(JobInput):
    job_type: Literal["PARSE"]
    document_id: UUID


JobRequest = Annotated[
    ReportJob | ResearchJob | DatasetJob | TrainJob | MonitoringJob | ParseJob,
    Field(discriminator="job_type"),
]
router = APIRouter(prefix="/jobs", tags=["Background jobs"])


def payload(job: BackgroundJob) -> dict[str, Any]:
    return {
        key: getattr(job, key)
        for key in (
            "id",
            "job_type",
            "company_id",
            "status",
            "queue_name",
            "attempt_count",
            "max_attempts",
            "scheduled_at",
            "started_at",
            "completed_at",
            "error_code",
            "error_message",
            "result_json",
            "request_id",
            "created_at",
        )
    }


def accessible(session: Session, job_id: UUID, principal: Principal) -> BackgroundJob:
    job = session.get(BackgroundJob, job_id)
    if job is None:
        raise AppError("NOT_FOUND", "Job not found", 404)
    if principal.role != "ADMIN" and job.created_by != principal.user_id:
        raise AppError("AUTHORIZATION_DENIED", "Access denied", 403)
    if job.company_id:
        principal.company(job.company_id)
    return job


@router.post("", status_code=202)
def create_job(
    body: JobRequest,
    request: Request,
    principal: Principal = Depends(authorize_request),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    require_permission(principal, jobs.JOB_PERMISSIONS[body.job_type])
    company_id = getattr(body, "company_id", None)
    if company_id:
        principal.company(company_id)
    data = body.model_dump(mode="json", exclude={"idempotency_key", "job_type"})
    with session.begin():
        job = job_queue(session, request.app.state.settings).enqueue(
            job_type=body.job_type,
            payload=data,
            actor_id=principal.user_id,
            request_id=request.state.request_id,
            company_id=company_id,
            idempotency_key=body.idempotency_key,
        )
    return payload(job)


@router.get("")
def list_jobs(
    principal: Principal = Depends(authorize_request),
    session: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100000),
) -> list[dict[str, Any]]:
    query = select(BackgroundJob)
    if principal.role != "ADMIN":
        query = query.where(BackgroundJob.created_by == principal.user_id)
    return [
        payload(job)
        for job in session.scalars(
            query.order_by(BackgroundJob.created_at.desc(), BackgroundJob.id)
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/{job_id}")
def get_job(
    job_id: UUID,
    principal: Principal = Depends(authorize_request),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    job = accessible(session, job_id, principal)
    result = payload(job)
    result["attempts"] = [
        {
            "attempt_number": attempt.attempt_number,
            "status": attempt.status,
            "error_code": attempt.error_code,
            "started_at": attempt.started_at,
            "completed_at": attempt.completed_at,
        }
        for attempt in session.scalars(
            select(JobAttempt)
            .where(JobAttempt.job_id == job.id)
            .order_by(JobAttempt.attempt_number)
        )
    ]
    return result


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: UUID,
    principal: Principal = Depends(authorize_request),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    accessible(session, job_id, principal)
    job = jobs.cancel(session, job_id, principal.user_id)
    session.commit()
    return payload(job)


@router.post("/{job_id}/retry")
def retry_job(
    job_id: UUID,
    principal: Principal = Depends(authorize_request),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    job = accessible(session, job_id, principal)
    require_permission(principal, jobs.JOB_PERMISSIONS[job.job_type])
    job = jobs.retry(session, job_id, principal.user_id)
    session.commit()
    return payload(job)
