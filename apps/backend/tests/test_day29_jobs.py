from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.exceptions import AppError
from app.models.runtime import JobAttempt
from app.models.user import User
from app.runtime.jobs import cancel, claim, enqueue, finish, recover, retry


@pytest.fixture
def queued(db_session):
    user = User(email=f"jobs-{uuid4()}@example.test", reviewer_role="ADMIN")
    db_session.add(user)
    db_session.flush()
    settings = Settings(_env_file=None, app_env="test")
    values = dict(
        job_type="REPORT_360",
        payload={"company_id": str(uuid4())},
        actor_id=user.id,
        request_id="test-job",
        idempotency_key="once",
    )
    job = enqueue(db_session, settings, **values)
    return db_session, settings, values, job


def test_enqueue_idempotency_and_claim(queued):
    session, settings, values, job = queued
    assert enqueue(session, settings, **values).id == job.id
    assert claim(session, "test-worker", job.id).id == job.id
    assert claim(session, "second-worker", job.id) is None
    assert job.attempt_count == 1
    assert finish(session, settings, job.id, job.lease_id, result={"report_id": "result"})
    assert job.status == "COMPLETED"
    assert job.result_json == {"report_id": "result"}


def test_transient_retry_bounded_and_attempt_history_preserved(queued):
    session, settings, _, job = queued
    for attempt in range(1, settings.job_max_attempts + 1):
        claim(session, "test-worker", job.id)
        assert job.attempt_count == attempt
        finish(session, settings, job.id, job.lease_id, error_code="DEPENDENCY_UNAVAILABLE")
        assert job.status == ("RETRYING" if attempt < settings.job_max_attempts else "FAILED")
        job.scheduled_at = datetime.now(UTC) - timedelta(seconds=1)
        session.flush()
    with pytest.raises(AppError):
        retry(session, job.id, job.created_by)
    attempts = list(session.scalars(select(JobAttempt).where(JobAttempt.job_id == job.id)))
    assert len(attempts) == settings.job_max_attempts
    assert all(attempt.completed_at and attempt.retryable for attempt in attempts)


def test_cancel_fences_late_completion(queued):
    session, settings, _, job = queued
    claim(session, "test-worker", job.id)
    lease = job.lease_id
    cancel(session, job.id, job.created_by)
    assert not finish(session, settings, job.id, lease, result={"unexpected": True})
    assert job.status == "CANCELLED"
    assert job.result_json is None
    attempt = session.scalar(select(JobAttempt).where(JobAttempt.job_id == job.id))
    assert attempt.status == "CANCELLED"


def test_permanent_failure_does_not_retry(queued):
    session, settings, _, job = queued
    claim(session, "test-worker", job.id)
    finish(session, settings, job.id, job.lease_id, error_code="AUTHORIZATION_DENIED")
    assert job.status == "FAILED"
    with pytest.raises(AppError):
        retry(session, job.id, job.created_by)


def test_recovery_preserves_attempt_and_fences_old_lease(queued):
    session, settings, _, job = queued
    claim(session, "test-worker", job.id)
    old_lease = job.lease_id
    job.started_at = datetime.now(UTC) - timedelta(hours=3)
    session.flush()
    assert recover(session, settings) >= 1
    assert job.status == "TIMED_OUT"
    retry(session, job.id, job.created_by)
    claim(session, "replacement-worker", job.id)
    assert job.lease_id != old_lease
    assert not finish(session, settings, job.id, old_lease, result={})
    assert job.status == "RUNNING"


def test_supervisor_enforces_timeout_with_process_termination(queued, monkeypatch):
    from types import SimpleNamespace

    from sqlalchemy.orm import Session

    from app.runtime import worker

    session, settings, _, job = queued
    connection = session.connection()
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "get_engine", lambda _: connection)
    settings.database_url = "postgresql://unused-in-test"
    monkeypatch.setattr(
        worker,
        "Session",
        lambda bind, **kwargs: Session(bind, join_transaction_mode="create_savepoint", **kwargs),
    )
    clock = iter([0.0, 10000.0])
    monkeypatch.setattr(
        worker, "time", SimpleNamespace(monotonic=lambda: next(clock), sleep=lambda _: None)
    )

    class Process:
        stopped = False

        def __init__(self, *args, **kwargs):
            pass

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            self.stopped = True

        def kill(self):
            self.stopped = True

        def wait(self, **kwargs):
            return 0

    monkeypatch.setattr(worker.subprocess, "Popen", Process)
    monkeypatch.setattr(worker, "terminate_execution", lambda process: process.terminate())
    assert worker.run_one(str(job.id))
    session.refresh(job)
    assert job.status == "TIMED_OUT"
    assert job.error_code == "JOB_TIMEOUT"
