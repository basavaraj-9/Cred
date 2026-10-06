"""Database queue supervisor. Children provide hard execution deadlines and cancellation."""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_engine
from app.models.runtime import BackgroundJob
from app.runtime.jobs import claim, finish, recover


def terminate_execution(process: subprocess.Popen[bytes]) -> None:
    """Terminate this owned process tree, including an OCR subprocess if present."""
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait()


def run_one(job_id: str | None = None) -> bool:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("Worker database is not configured")
    engine = get_engine(settings.database_url)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        recover(session, settings)
        job = claim(
            session, f"{socket.gethostname()}:{os.getpid()}", UUID(job_id) if job_id else None
        )
        if job is None:
            return False
        identifier, lease, timeout = job.id, job.lease_id, job.timeout_seconds
    assert lease is not None
    command = [sys.executable, "-m", "app.runtime.execute", str(identifier), str(lease)]
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        command, creationflags=creationflags, start_new_session=os.name != "nt"
    )
    deadline = time.monotonic() + timeout
    timed_out = False
    try:
        while process.poll() is None:
            with Session(engine) as session:
                current = session.get(BackgroundJob, identifier)
                active = (
                    current is not None
                    and current.status == "RUNNING"
                    and current.lease_id == lease
                )
            timed_out = time.monotonic() >= deadline
            if not active or timed_out:
                terminate_execution(process)
                break
            time.sleep(0.25)
    finally:
        if process.poll() is None:
            terminate_execution(process)
    with Session(engine) as session, session.begin():
        # A successful child already finalized its lease; this becomes a no-op.
        finish(
            session,
            settings,
            identifier,
            lease,
            error_code="JOB_TIMEOUT" if timed_out else "WORKER_EXITED",
            timed_out=timed_out,
        )
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    concurrency = get_settings().worker_concurrency
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        while True:
            results = [executor.submit(run_one) for _ in range(concurrency)]
            worked = any([result.result() for result in results])
            if args.once:
                return
            if not worked:
                time.sleep(1)


if __name__ == "__main__":
    main()
