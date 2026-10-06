"""Provider-neutral delivery adapters. PostgreSQL remains the authoritative job ledger."""

from typing import Any, Protocol
from uuid import UUID

from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.runtime import BackgroundJob
from app.runtime import jobs


class JobQueue(Protocol):
    def enqueue(self, **values: Any) -> BackgroundJob: ...
    def cancel(self, job_id: UUID, actor_id: UUID) -> BackgroundJob: ...
    def status(self, job_id: UUID) -> BackgroundJob | None: ...
    def retry(self, job_id: UUID, actor_id: UUID) -> BackgroundJob: ...


class DatabaseJobQueue:
    def __init__(self, session: Session, settings: Settings):
        self.session, self.settings = session, settings

    def enqueue(self, **values: Any) -> BackgroundJob:
        return jobs.enqueue(self.session, self.settings, **values)

    def cancel(self, job_id: UUID, actor_id: UUID) -> BackgroundJob:
        return jobs.cancel(self.session, job_id, actor_id)

    def status(self, job_id: UUID) -> BackgroundJob | None:
        return self.session.get(BackgroundJob, job_id)

    def retry(self, job_id: UUID, actor_id: UUID) -> BackgroundJob:
        return jobs.retry(self.session, job_id, actor_id)


class RedisJobQueue(DatabaseJobQueue):
    """The SQL ledger is the outbox; a separate dispatcher performs Redis delivery."""


def job_queue(session: Session, settings: Settings) -> JobQueue:
    adapter = RedisJobQueue if settings.queue_backend == "redis_rq" else DatabaseJobQueue
    return adapter(session, settings)


class QueueAdapter(Protocol):
    def dispatch(self, job_id: UUID, attempt: int) -> None: ...


class DatabaseQueue:
    def dispatch(self, job_id: UUID, attempt: int) -> None:
        # The database worker polls the committed ledger directly.
        return None


class RedisQueue:
    def __init__(self, settings: Settings):
        self.connection = Redis.from_url(
            settings.redis_url or "", socket_connect_timeout=2, socket_timeout=2
        )
        self.queue = Queue("analytics", connection=self.connection, serializer=JSONSerializer)
        self.timeout = settings.job_timeout_seconds + 60

    def dispatch(self, job_id: UUID, attempt: int) -> None:
        from app.runtime.worker import run_one

        identifier = f"runtime-{job_id}-{attempt}"
        existing = self.queue.fetch_job(identifier)
        if existing is not None:
            state = existing.get_status(refresh=True)
            if state in {"queued", "started", "deferred", "scheduled"}:
                return
            # Delivery metadata only; the immutable application attempt history stays in SQL.
            existing.delete()
        self.queue.enqueue(
            run_one,
            str(job_id),
            job_id=identifier,
            job_timeout=self.timeout,
            result_ttl=60,
            failure_ttl=86400,
        )


def queue_adapter(settings: Settings) -> QueueAdapter:
    return RedisQueue(settings) if settings.queue_backend == "redis_rq" else DatabaseQueue()
