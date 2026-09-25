from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.repositories.audit_log import write_audit_log
from app.database.session import get_engine
from app.ml.credit.feature_schema import FEATURE_BUILDER_VERSION, FEATURE_SCHEMA_VERSION
from app.ml.credit.features import build_feature_snapshot
from app.ml.credit.label_policy import LABEL_POLICY_VERSION, label_policy
from app.ml.credit.labels import assign_label
from app.ml.credit.leakage import leakage_report
from app.ml.credit.quality import quality_report
from app.ml.credit.schemas import LabelResult, SplitCandidate
from app.ml.credit.splits import SPLIT_POLICY_VERSION, company_grouped_chronological_split
from app.models.credit_ml import (
    CreditMLDatasetReport,
    CreditMLExample,
    CreditMLFeatureSnapshot,
    CreditMLFeatureSource,
    CreditMLObservation,
    CreditOutcome,
)
from app.models.enums import (
    CreditDatasetQuality,
    CreditLabelStatus,
    DatasetEligibilityStatus,
)
from app.models.ml import MLDataset

DATASET_NAME = "credit_default_dataset"
TARGET_NAME = "default_within_365_days"


def canonical_dataset_hash(records: list[dict[str, object]], metadata: dict[str, object]) -> str:
    content = "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in records)
    canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n" + content
    return hashlib.sha256(canonical.encode()).hexdigest()


class CreditMLDatasetService:
    def __init__(self, session: Session, output_root: Path) -> None:
        self.session = session
        self.output_root = output_root

    def build(
        self, dataset_version: str = "credit_dataset_v1", feature_group: str = "ANOMALY_ENRICHED_V1"
    ) -> dict[str, object]:
        try:
            return self._build(dataset_version, feature_group)
        except Exception as exc:
            self._record_build_failure(dataset_version, feature_group, exc)
            raise

    def _record_build_failure(
        self, dataset_version: str, feature_group: str, error: Exception
    ) -> None:
        bind = self.session.get_bind()
        engine = bind.engine if isinstance(bind, Connection) else bind
        try:
            with Session(engine) as audit_session, audit_session.begin():
                if isinstance(error, ValueError) and "Critical leakage" in str(error):
                    write_audit_log(
                        audit_session,
                        entity_type="credit_ml_dataset",
                        entity_id=UUID(int=0),
                        action="CREDIT_ML_LEAKAGE_CHECK_FAILED",
                        event_type="CREDIT_ML_LEAKAGE_CHECK_FAILED",
                        metadata_json={
                            "dataset_version": dataset_version,
                            "feature_group": feature_group,
                        },
                    )
                write_audit_log(
                    audit_session,
                    entity_type="credit_ml_dataset",
                    entity_id=UUID(int=0),
                    action="CREDIT_ML_DATASET_BUILD_FAILED",
                    event_type="CREDIT_ML_DATASET_BUILD_FAILED",
                    metadata_json={
                        "dataset_version": dataset_version,
                        "feature_group": feature_group,
                        "label_policy_version": LABEL_POLICY_VERSION,
                        "feature_builder_version": FEATURE_BUILDER_VERSION,
                        "feature_schema_version": FEATURE_SCHEMA_VERSION,
                        "split_policy_version": SPLIT_POLICY_VERSION,
                        "error_type": type(error).__name__,
                    },
                )
        except Exception:
            # Failure auditing must never hide the original dataset build error.
            return

    def _build(self, dataset_version: str, feature_group: str) -> dict[str, object]:
        existing = self.session.scalar(
            select(MLDataset).where(
                MLDataset.name == DATASET_NAME, MLDataset.version == dataset_version
            )
        )
        if existing:
            metadata = existing.metadata_json or {}
            requested_configuration = {
                "feature_group": feature_group,
                "label_policy_version": LABEL_POLICY_VERSION,
                "feature_builder_version": FEATURE_BUILDER_VERSION,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "split_policy_version": SPLIT_POLICY_VERSION,
            }
            if any(metadata.get(key) != value for key, value in requested_configuration.items()):
                raise ValueError(
                    "Dataset versions are immutable; choose a new version for changed configuration"
                )
            existing_report = self.session.scalar(
                select(CreditMLDatasetReport).where(CreditMLDatasetReport.dataset_id == existing.id)
            )
            return {
                "dataset_id": existing.id,
                "dataset_version": existing.version,
                "sha256": existing.sha256_hash,
                **(existing_report.report_json if existing_report else {}),
            }
        observations = list(
            self.session.scalars(
                select(CreditMLObservation).order_by(
                    CreditMLObservation.observation_date, CreditMLObservation.company_id
                )
            ).all()
        )
        write_audit_log(
            self.session,
            entity_type="credit_ml_dataset",
            entity_id=UUID(int=0),
            action="CREDIT_ML_DATASET_BUILD_STARTED",
            event_type="CREDIT_ML_DATASET_BUILD_STARTED",
            metadata_json={
                "dataset_version": dataset_version,
                "observation_count": len(observations),
            },
        )
        candidates: list[tuple[CreditMLObservation, CreditMLFeatureSnapshot, LabelResult]] = []
        excluded: Counter[str] = Counter()
        for observation in observations:
            outcomes = list(
                self.session.scalars(
                    select(CreditOutcome).where(
                        CreditOutcome.company_id == observation.company_id,
                        CreditOutcome.observation_date == observation.observation_date,
                    )
                ).all()
            )
            label = assign_label(observation, outcomes)
            observation.label_status = label.status
            write_audit_log(
                self.session,
                entity_type="credit_ml_observation",
                entity_id=observation.id,
                action="CREDIT_ML_LABEL_ASSIGNED",
                event_type="CREDIT_ML_LABEL_ASSIGNED",
                company_id=observation.company_id,
                analysis_job_id=observation.analysis_job_id,
                metadata_json={
                    "label_status": label.status.value,
                    "target_value": label.target,
                    "label_quality": label.quality.value,
                    "outcome_id": str(label.outcome_id) if label.outcome_id else None,
                },
            )
            if label.status not in {
                CreditLabelStatus.LABELED_POSITIVE,
                CreditLabelStatus.LABELED_NEGATIVE,
            }:
                observation.dataset_eligibility_status = DatasetEligibilityStatus.EXCLUDED
                excluded[label.status.value] += 1
                write_audit_log(
                    self.session,
                    entity_type="credit_ml_observation",
                    entity_id=observation.id,
                    action="CREDIT_ML_EXAMPLE_EXCLUDED",
                    event_type="CREDIT_ML_EXAMPLE_EXCLUDED",
                    company_id=observation.company_id,
                    analysis_job_id=observation.analysis_job_id,
                    metadata_json={"reason": label.status.value},
                )
                continue
            snapshot = self.session.scalar(
                select(CreditMLFeatureSnapshot)
                .where(
                    CreditMLFeatureSnapshot.observation_id == observation.id,
                    CreditMLFeatureSnapshot.feature_builder_version == FEATURE_BUILDER_VERSION,
                    CreditMLFeatureSnapshot.feature_schema_version == FEATURE_SCHEMA_VERSION,
                    CreditMLFeatureSnapshot.feature_group == feature_group,
                )
                .order_by(CreditMLFeatureSnapshot.created_at.desc())
            ) or build_feature_snapshot(self.session, observation, feature_group)
            observation.dataset_eligibility_status = DatasetEligibilityStatus.ELIGIBLE
            assert label.target is not None
            candidates.append((observation, snapshot, label))
        split_candidates = [
            SplitCandidate(row.id, row.company_id, row.observation_date, label.target)
            for row, _, label in candidates
            if label.target is not None
        ]
        assignments = {
            item.observation_id: item.split
            for item in company_grouped_chronological_split(split_candidates)
        }
        records: list[dict[str, object]] = []
        for observation, snapshot, label in candidates:
            source_times = [
                item.isoformat() if item else None
                for item in self.session.scalars(
                    select(CreditMLFeatureSource.source_available_at).where(
                        CreditMLFeatureSource.feature_snapshot_id == snapshot.id
                    )
                ).all()
            ]
            records.append(
                {
                    "observation_id": str(observation.id),
                    "company_id": str(observation.company_id),
                    "observation_date": observation.observation_date.isoformat(),
                    "feature_cutoff_timestamp": observation.feature_cutoff_timestamp.isoformat(),
                    "prediction_horizon_end": observation.outcome_window_end.isoformat(),
                    "features": snapshot.features_json,
                    "feature_hash": hashlib.sha256(
                        json.dumps(
                            snapshot.features_json, sort_keys=True, separators=(",", ":")
                        ).encode()
                    ).hexdigest(),
                    "source_available_at": source_times,
                    "availability_complete": snapshot.availability_complete,
                    "target_name": TARGET_NAME,
                    "target_value": label.target,
                    "label_status": label.status.value,
                    "label_quality": label.quality.value,
                    "outcome_id": str(label.outcome_id) if label.outcome_id else None,
                    "split": assignments[observation.id].value,
                }
            )
        leakage = leakage_report(records)
        quality, readiness, report_payload = quality_report(records, excluded, leakage)
        if quality == "INVALID":
            raise ValueError("Critical leakage prevents credit dataset publication")
        canonical_meta = {
            "dataset_version": dataset_version,
            "target_name": TARGET_NAME,
            "horizon_days": label_policy()["default_prediction_horizon_days"],
            "label_policy_version": LABEL_POLICY_VERSION,
            "feature_builder_version": FEATURE_BUILDER_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "split_policy_version": SPLIT_POLICY_VERSION,
            "feature_group": feature_group,
        }
        content = (
            "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in records)
            + "\n"
        )
        digest = canonical_dataset_hash(records, canonical_meta)
        folder = self.output_root / "data" / "ml" / "credit" / "versions"
        folder.mkdir(parents=True, exist_ok=True)
        data_path = folder / f"{dataset_version}.jsonl"
        metadata_path = folder / f"{dataset_version}.metadata.json"
        data_path.write_text(content, encoding="utf-8")
        metadata = {
            **canonical_meta,
            "sha256": digest,
            "quality_status": quality,
            "training_readiness": readiness,
            **report_payload,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        dataset = MLDataset(
            name=DATASET_NAME,
            task_type="CREDIT_RISK",
            version=dataset_version,
            description="Leakage-checked historical credit outcome dataset",
            taxonomy_version=LABEL_POLICY_VERSION,
            record_count=len(records),
            storage_uri=f"data://ml/credit/versions/{data_path.name}",
            sha256_hash=digest,
            target_name=TARGET_NAME,
            prediction_horizon_days=int(label_policy()["default_prediction_horizon_days"]),
            label_policy_version=LABEL_POLICY_VERSION,
            feature_builder_version=FEATURE_BUILDER_VERSION,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            split_policy_version=SPLIT_POLICY_VERSION,
            metadata_json=metadata,
        )
        self.session.add(dataset)
        self.session.flush()
        for observation, snapshot, label in candidates:
            self.session.add(
                CreditMLExample(
                    dataset_id=dataset.id,
                    observation_id=observation.id,
                    feature_snapshot_id=snapshot.id,
                    outcome_id=label.outcome_id,
                    company_id=observation.company_id,
                    observation_date=observation.observation_date,
                    target_name=TARGET_NAME,
                    target_value=label.target,
                    label_status=label.status,
                    label_quality=label.quality,
                    split=assignments[observation.id],
                    created_at=datetime.now(UTC),
                )
            )
        dataset_report = CreditMLDatasetReport(
            dataset_id=dataset.id,
            quality_status=CreditDatasetQuality(quality),
            training_readiness=readiness,
            report_json=metadata,
        )
        self.session.add(dataset_report)
        write_audit_log(
            self.session,
            entity_type="credit_ml_dataset",
            entity_id=dataset.id,
            action="CREDIT_ML_DATASET_CREATED",
            event_type="CREDIT_ML_DATASET_CREATED",
            metadata_json={
                "record_count": len(records),
                "sha256": digest,
                "quality_status": quality,
                "training_readiness": readiness,
            },
        )
        self.session.flush()
        return {"dataset_id": dataset.id, **metadata}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a leakage-safe credit ML dataset; no model is trained."
    )
    parser.add_argument("--dataset-version", default="credit_dataset_v1")
    parser.add_argument("--feature-group", default="ANOMALY_ENRICHED_V1")
    args = parser.parse_args()
    settings = get_settings()
    database_url = (
        settings.test_database_url
        if settings.app_env == "test" and settings.test_database_url
        else settings.database_url
    )
    with Session(get_engine(database_url)) as session, session.begin():
        result = CreditMLDatasetService(session, Path(__file__).resolve().parents[5]).build(
            args.dataset_version, args.feature_group
        )
        print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
