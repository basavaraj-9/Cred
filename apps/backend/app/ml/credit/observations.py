from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.repositories.audit_log import write_audit_log
from app.models.credit_ml import CreditMLObservation
from app.models.enums import CreditLabelStatus, DatasetEligibilityStatus


def create_observation(
    session: Session,
    *,
    company_id: UUID,
    observation_date: date,
    as_of_fiscal_year: str,
    feature_cutoff_timestamp: datetime,
    prediction_horizon_days: int = 365,
    analysis_job_id: UUID | None = None,
    document_id: UUID | None = None,
) -> CreditMLObservation:
    if prediction_horizon_days <= 0:
        raise ValueError("prediction_horizon_days must be positive")
    existing = session.scalar(
        select(CreditMLObservation).where(
            CreditMLObservation.company_id == company_id,
            CreditMLObservation.observation_date == observation_date,
            CreditMLObservation.prediction_horizon_days == prediction_horizon_days,
            CreditMLObservation.feature_cutoff_timestamp == feature_cutoff_timestamp,
        )
    )
    if existing:
        return existing
    row = CreditMLObservation(
        company_id=company_id,
        analysis_job_id=analysis_job_id,
        document_id=document_id,
        observation_date=observation_date,
        as_of_fiscal_year=as_of_fiscal_year,
        prediction_horizon_days=prediction_horizon_days,
        outcome_window_start=observation_date + timedelta(days=1),
        outcome_window_end=observation_date + timedelta(days=prediction_horizon_days),
        feature_cutoff_timestamp=feature_cutoff_timestamp,
        label_status=CreditLabelStatus.UNKNOWN,
        dataset_eligibility_status=DatasetEligibilityStatus.NEEDS_REVIEW,
    )
    session.add(row)
    session.flush()
    write_audit_log(
        session,
        entity_type="credit_ml_observation",
        entity_id=row.id,
        action="CREDIT_ML_OBSERVATION_CREATED",
        event_type="CREDIT_ML_OBSERVATION_CREATED",
        company_id=company_id,
        analysis_job_id=analysis_job_id,
        metadata_json={
            "observation_date": observation_date.isoformat(),
            "as_of_fiscal_year": as_of_fiscal_year,
            "prediction_horizon_days": prediction_horizon_days,
            "feature_cutoff_timestamp": feature_cutoff_timestamp.isoformat(),
        },
    )
    return row
