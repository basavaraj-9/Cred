from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit_log(
    session: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    action: str,
    event_type: str,
    company_id: UUID | None = None,
    analysis_job_id: UUID | None = None,
    user_id: UUID | None = None,
    message: str | None = None,
    metadata_json: dict[str, object] | None = None,
) -> AuditLog:
    log = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        event_type=event_type,
        company_id=company_id,
        analysis_job_id=analysis_job_id,
        user_id=user_id,
        message=message,
        metadata_json=metadata_json,
    )
    session.add(log)
    session.flush()
    return log
