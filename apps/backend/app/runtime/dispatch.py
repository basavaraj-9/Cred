"""Durable SQL outbox poller for RQ delivery; Redis outages leave queued work intact."""

import argparse
import logging
import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_engine
from app.models.runtime import BackgroundJob
from app.runtime.jobs import recover
from app.runtime.queue import queue_adapter


def dispatch_once() -> int:
    settings = get_settings()
    if settings.queue_backend != "redis_rq" or not settings.database_url:
        raise RuntimeError("Redis dispatcher requires the Redis queue and database")
    with Session(get_engine(settings.database_url)) as session, session.begin():
        recover(session, settings)
        pending = list(
            session.execute(
                select(BackgroundJob.id, BackgroundJob.attempt_count)
                .where(
                    BackgroundJob.status.in_(["QUEUED", "RETRYING"]),
                    BackgroundJob.scheduled_at <= datetime.now(UTC),
                )
                .order_by(BackgroundJob.scheduled_at)
                .limit(100)
            )
        )
    adapter = queue_adapter(settings)
    for identifier, attempt in pending:
        adapter.dispatch(identifier, attempt)
    return len(pending)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            dispatch_once()
        except Exception:
            logging.getLogger(__name__).error("queue_dispatch_unavailable")
            if args.once:
                raise SystemExit(1) from None
        if args.once:
            return
        time.sleep(2)


if __name__ == "__main__":
    main()
