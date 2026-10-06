"""Best-effort security audit outside failed service transactions, with safe log fallback."""

import logging
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.repositories.audit_log import write_audit_log
from app.database.session import get_engine


def record_failure(settings: Settings, event: str, request_id: str, user_id: UUID | None) -> None:
    try:
        if not settings.database_url:
            raise RuntimeError("Audit store unavailable")
        with Session(get_engine(settings.database_url)) as session, session.begin():
            write_audit_log(
                session,
                entity_type="runtime_security",
                entity_id=uuid4(),
                action=event,
                event_type=event,
                user_id=user_id,
                metadata_json={"request_id": request_id},
            )
    except Exception:
        logging.getLogger(__name__).warning(
            "security_audit_store_unavailable",
            extra={"runtime": {"security_event": event, "request_id": request_id}},
        )
