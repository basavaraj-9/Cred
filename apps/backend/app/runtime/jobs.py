"""Durable job state. Every transition uses a database lock and an attempt lease."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.runtime import BackgroundJob, JobAttempt
from app.runtime.observability import metrics

JOB_PERMISSIONS = {
    "REPORT_360": "REPORT_GENERATE",
    "RESEARCH": "CREDIT_ANALYZE",
    "STOCK_DATASET": "STOCK_RESEARCH_BUILD",
    "STOCK_TRAIN": "STOCK_RESEARCH_BUILD",
    "MONITORING": "STOCK_RESEARCH_BUILD",
    "PARSE": "CREDIT_ANALYZE",
}
TERMINAL = frozenset({"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"})
TRANSIENT = frozenset({"DEPENDENCY_UNAVAILABLE", "PROVIDER_TIMEOUT", "DATABASE_TRANSIENT"})
TIMEOUT_CAPS = {
    "REPORT_360": 300,
    "RESEARCH": 120,
    "STOCK_DATASET": 900,
    "STOCK_TRAIN": 1800,
    "MONITORING": 900,
    "PARSE": 120,
}


def enqueue(
    session: Session,
    settings: Settings,
    *,
    job_type: str,
    payload: dict[str, Any],
    actor_id: UUID,
    request_id: str,
    company_id: UUID | None = None,
    idempotency_key: str,
) -> BackgroundJob:
    if job_type not in JOB_PERMISSIONS:
        raise AppError("VALIDATION_ERROR", "Unsupported job type", 422)
    canonical = json.dumps(
        {
            "actor": str(actor_id),
            "payload": payload,
            "key": idempotency_key,
            "company": str(company_id),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    job_id = uuid4()
    # Uniqueness plus ON CONFLICT makes concurrent identical requests converge.
    session.execute(
        insert(BackgroundJob)
        .values(
            id=job_id,
            job_type=job_type,
            payload_json=payload,
            created_by=actor_id,
            request_id=request_id,
            company_id=company_id,
            input_hash=digest,
            status="QUEUED",
            scheduled_at=datetime.now(UTC),
            max_attempts=settings.job_max_attempts,
            timeout_seconds=min(settings.job_timeout_seconds, TIMEOUT_CAPS[job_type]),
        )
        .on_conflict_do_nothing(constraint="uq_background_jobs_input")
    )
    job = session.scalar(
        select(BackgroundJob).where(
            BackgroundJob.job_type == job_type, BackgroundJob.input_hash == digest
        )
    )
    assert job is not None
    if job.id == job_id:
        audit(session, job, "JOB_ENQUEUED", actor_id)
        metrics.add("jobs_enqueued_total", category=job.job_type)
    return job


def audit(session: Session, job: BackgroundJob, event: str, actor_id: UUID) -> None:
    write_audit_log(
        session,
        entity_type="background_job",
        entity_id=job.id,
        action=event,
        event_type=event,
        user_id=actor_id,
        company_id=job.company_id,
        metadata_json={"request_id": job.request_id, "attempt": job.attempt_count},
    )


def claim(session: Session, worker_id: str, job_id: UUID | None = None) -> BackgroundJob | None:
    query = select(BackgroundJob).where(
        BackgroundJob.status.in_(["QUEUED", "RETRYING"]),
        BackgroundJob.scheduled_at <= datetime.now(UTC),
        BackgroundJob.attempt_count < BackgroundJob.max_attempts,
    )
    if job_id:
        query = query.where(BackgroundJob.id == job_id)
    job = session.scalar(
        query.order_by(BackgroundJob.priority.desc(), BackgroundJob.scheduled_at, BackgroundJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    now = datetime.now(UTC)
    job.status, job.started_at, job.lease_id = "RUNNING", now, uuid4()
    job.attempt_count += 1
    job.completed_at = job.failed_at = None
    job.error_code = job.error_message = None
    session.add(
        JobAttempt(
            job_id=job.id,
            attempt_number=job.attempt_count,
            started_at=now,
            created_at=now,
            status="RUNNING",
            worker_id=worker_id,
        )
    )
    session.flush()
    return job


def finish(
    session: Session,
    settings: Settings,
    job_id: UUID,
    lease_id: UUID,
    *,
    result: dict[str, Any] | None = None,
    error_code: str | None = None,
    timed_out: bool = False,
) -> bool:
    job = session.scalar(select(BackgroundJob).where(BackgroundJob.id == job_id).with_for_update())
    if job is None or job.status != "RUNNING" or job.lease_id != lease_id:
        return False  # A cancelled/recovered attempt cannot overwrite the current state.
    now = datetime.now(UTC)
    attempt = session.scalar(
        select(JobAttempt).where(
            JobAttempt.job_id == job.id, JobAttempt.attempt_number == job.attempt_count
        )
    )
    assert attempt is not None
    attempt.completed_at = now
    attempt.duration_ms = max(0, int((now - attempt.started_at).total_seconds() * 1000))
    attempt.error_code = error_code
    attempt.retryable = error_code in TRANSIENT and not timed_out
    attempt.status = "TIMED_OUT" if timed_out else "FAILED" if error_code else "COMPLETED"
    if attempt.retryable and job.attempt_count < job.max_attempts:
        job.status = "RETRYING"
        delay = min(300, settings.retry_base_seconds * 2 ** (job.attempt_count - 1))
        job.scheduled_at = now + timedelta(seconds=delay)
    else:
        job.status = attempt.status
        job.completed_at = now
        job.failed_at = now if error_code else None
    job.error_code = error_code
    job.error_message = (
        "Job execution failed; consult authorized operations logs" if error_code else None
    )
    job.result_json = result if not error_code else None
    job.lease_id = None
    audit(session, job, "JOB_" + job.status, job.created_by)
    metrics.add(
        "jobs_failed_total" if error_code else "jobs_completed_total", category=job.job_type
    )
    metrics.add("job_duration_seconds_sum", attempt.duration_ms / 1000, category=job.job_type)
    return True


def cancel(session: Session, job_id: UUID, actor_id: UUID) -> BackgroundJob:
    job = session.scalar(select(BackgroundJob).where(BackgroundJob.id == job_id).with_for_update())
    if job is None:
        raise AppError("NOT_FOUND", "Job not found", 404)
    if job.status in TERMINAL:
        return job
    now = datetime.now(UTC)
    if job.status == "RUNNING":
        attempt = session.scalar(
            select(JobAttempt).where(
                JobAttempt.job_id == job.id, JobAttempt.attempt_number == job.attempt_count
            )
        )
        if attempt:
            attempt.status, attempt.completed_at = "CANCELLED", now
    job.status, job.completed_at, job.lease_id = "CANCELLED", now, None
    audit(session, job, "JOB_CANCELLED", actor_id)
    return job


def retry(session: Session, job_id: UUID, actor_id: UUID) -> BackgroundJob:
    job = session.scalar(select(BackgroundJob).where(BackgroundJob.id == job_id).with_for_update())
    if job is None:
        raise AppError("NOT_FOUND", "Job not found", 404)
    if job.status not in {"FAILED", "TIMED_OUT"} or job.attempt_count >= job.max_attempts:
        raise AppError("JOB_RETRY_NOT_ALLOWED", "Job cannot be retried", 409)
    if job.error_code not in TRANSIENT and job.status != "TIMED_OUT":
        raise AppError("JOB_RETRY_NOT_ALLOWED", "Permanent failure requires corrected inputs", 409)
    job.status, job.scheduled_at = "RETRYING", datetime.now(UTC)
    audit(session, job, "JOB_RETRY_REQUESTED", actor_id)
    return job


def recover(session: Session, settings: Settings) -> int:
    jobs = list(
        session.scalars(
            select(BackgroundJob)
            .where(BackgroundJob.status == "RUNNING")
            .with_for_update(skip_locked=True)
            .limit(200)
        )
    )
    recovered = 0
    for job in jobs:
        if job.started_at is None or job.lease_id is None:
            continue
        deadline = job.started_at + timedelta(
            seconds=job.timeout_seconds + settings.job_recovery_grace_seconds
        )
        if deadline < datetime.now(UTC):
            recovered += finish(
                session, settings, job.id, job.lease_id, error_code="JOB_TIMEOUT", timed_out=True
            )
    return recovered
