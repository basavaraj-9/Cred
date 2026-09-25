from uuid import UUID

from sqlalchemy.orm import Session

from app.models.analysis_job import AnalysisJob


def create_analysis_job(
    session: Session, company_id: UUID, created_by_user_id: UUID | None = None
) -> AnalysisJob:
    job = AnalysisJob(company_id=company_id, created_by_user_id=created_by_user_id)
    session.add(job)
    session.flush()
    return job


def get_analysis_job(session: Session, job_id: UUID) -> AnalysisJob | None:
    return session.get(AnalysisJob, job_id)
