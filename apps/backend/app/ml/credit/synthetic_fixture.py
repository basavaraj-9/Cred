from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_engine
from app.ml.credit.dataset import DATASET_NAME, CreditMLDatasetService
from app.ml.credit.feature_schema import FEATURE_BUILDER_VERSION, FEATURE_SCHEMA_VERSION
from app.models import Company
from app.models.credit_ml import CreditMLFeatureSnapshot, CreditMLObservation, CreditOutcome
from app.models.enums import (
    CreditLabelQuality,
    CreditLabelStatus,
    CreditOutcomeType,
    DatasetEligibilityStatus,
    VerificationStatus,
)
from app.models.ml import MLDataset


def create_synthetic_credit_dataset(session: Session, project_root: Path) -> dict[str, object]:
    existing = session.scalar(
        select(MLDataset).where(
            MLDataset.name == DATASET_NAME, MLDataset.version == "credit_dataset_v1"
        )
    )
    if existing:
        return CreditMLDatasetService(session, project_root).build()
    base = date(2010, 1, 1)
    for index in range(10):
        company_id = UUID(f"12000000-0000-0000-0000-{index + 1:012d}")
        observation_id = UUID(f"12100000-0000-0000-0000-{index + 1:012d}")
        outcome_id = UUID(f"12200000-0000-0000-0000-{index + 1:012d}")
        snapshot_id = UUID(f"12300000-0000-0000-0000-{index + 1:012d}")
        company = Company(id=company_id, legal_name=f"Synthetic Credit Pipeline Company {index}")
        session.add(company)
        session.flush()
        observed = base + timedelta(days=index * 365)
        cutoff = datetime.combine(observed, datetime.max.time(), tzinfo=UTC)
        observation = CreditMLObservation(
            id=observation_id,
            company_id=company_id,
            observation_date=observed,
            as_of_fiscal_year=f"FY{observed.year}",
            prediction_horizon_days=365,
            outcome_window_start=observed + timedelta(days=1),
            outcome_window_end=observed + timedelta(days=365),
            feature_cutoff_timestamp=cutoff,
            label_status=CreditLabelStatus.UNKNOWN,
            dataset_eligibility_status=DatasetEligibilityStatus.NEEDS_REVIEW,
        )
        session.add(observation)
        session.flush()
        positive = index in {1, 4, 8}
        session.add(
            CreditOutcome(
                id=outcome_id,
                company_id=company_id,
                observation_date=observed,
                outcome_date=(
                    observed + timedelta(days=100) if positive else observed + timedelta(days=365)
                ),
                outcome_type=(
                    CreditOutcomeType.DEFAULT if positive else CreditOutcomeType.NO_DEFAULT
                ),
                source_type="SYNTHETIC_PIPELINE_FIXTURE",
                source_reference=f"day12-fixture-{index}",
                label_quality=CreditLabelQuality.SYNTHETIC,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
        features: dict[str, object] = {
            "current_ratio": None if index == 2 else 0.7 + index / 10,
            "current_ratio_confidence": 0.9,
            "debt_to_equity": 1.8 - index / 10,
            "financial_completeness": 0.8 + index / 100,
            "statement_scope": "CONSOLIDATED",
            "sector": "SYNTHETIC_INDUSTRIAL" if index < 7 else "SYNTHETIC_LATER_CATEGORY",
            "trend_revenue_direction": "DECREASING" if positive else "INCREASING",
            "anomaly_persistent_net_loss": int(positive),
        }
        canonical = json.dumps(features, sort_keys=True, separators=(",", ":"))
        session.add(
            CreditMLFeatureSnapshot(
                id=snapshot_id,
                observation_id=observation_id,
                company_id=company_id,
                observation_date=observed,
                feature_cutoff_timestamp=cutoff,
                feature_builder_version=FEATURE_BUILDER_VERSION,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                feature_group="ANOMALY_ENRICHED_V1",
                features_json=features,
                feature_count=sum(value is not None for value in features.values()),
                missing_feature_count=sum(value is None for value in features.values()),
                input_hash=hashlib.sha256(canonical.encode()).hexdigest(),
                availability_complete=False,
            )
        )
    session.flush()
    return CreditMLDatasetService(session, project_root).build()


def main() -> None:
    settings = get_settings()
    database_url = (
        settings.test_database_url
        if settings.app_env == "test" and settings.test_database_url
        else settings.database_url
    )
    project_root = Path(__file__).resolve().parents[5]
    with Session(get_engine(database_url)) as session, session.begin():
        result = create_synthetic_credit_dataset(session, project_root)
    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
