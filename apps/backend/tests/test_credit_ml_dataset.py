from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.credit.dataset import CreditMLDatasetService, canonical_dataset_hash
from app.ml.credit.feature_schema import (
    FEATURE_BUILDER_VERSION,
    FEATURE_SCHEMA_VERSION,
    feature_schema,
    validate_features,
)
from app.ml.credit.label_policy import LABEL_POLICY_VERSION, label_policy
from app.ml.credit.labels import assign_label
from app.ml.credit.leakage import leakage_report
from app.ml.credit.observations import create_observation
from app.ml.credit.schemas import SplitCandidate
from app.ml.credit.splits import (
    SPLIT_POLICY_VERSION,
    company_grouped_chronological_split,
    split_policy,
)
from app.models import AuditLog, Company
from app.models.credit_ml import (
    CreditMLDatasetReport,
    CreditMLExample,
    CreditMLFeatureSnapshot,
    CreditMLObservation,
    CreditOutcome,
)
from app.models.enums import (
    CreditDatasetSplit,
    CreditLabelQuality,
    CreditLabelStatus,
    CreditOutcomeType,
    DatasetEligibilityStatus,
    VerificationStatus,
)
from app.models.ml import MLDataset


def observation(day: date = date(2024, 9, 30), horizon: int = 365) -> CreditMLObservation:
    return CreditMLObservation(
        id=uuid4(),
        company_id=uuid4(),
        observation_date=day,
        as_of_fiscal_year="FY2024",
        prediction_horizon_days=horizon,
        outcome_window_start=day + timedelta(days=1),
        outcome_window_end=day + timedelta(days=horizon),
        feature_cutoff_timestamp=datetime(2024, 9, 30, 23, 59, tzinfo=UTC),
        label_status=CreditLabelStatus.UNKNOWN,
        dataset_eligibility_status=DatasetEligibilityStatus.NEEDS_REVIEW,
    )


def outcome(
    obs: CreditMLObservation,
    kind: CreditOutcomeType,
    when: date | None,
    quality: CreditLabelQuality = CreditLabelQuality.SYNTHETIC,
    verification: VerificationStatus = VerificationStatus.VERIFIED,
) -> CreditOutcome:
    return CreditOutcome(
        id=uuid4(),
        company_id=obs.company_id,
        observation_date=obs.observation_date,
        outcome_date=when,
        outcome_type=kind,
        source_type="SYNTHETIC_FIXTURE",
        label_quality=quality,
        verification_status=verification,
    )


def test_label_policy_loads_and_has_version() -> None:
    assert label_policy()["version"] == LABEL_POLICY_VERSION == "credit_label_policy_v1"


@pytest.mark.parametrize(
    "kind",
    [
        CreditOutcomeType.DEFAULT,
        CreditOutcomeType.DELINQUENCY_90,
        CreditOutcomeType.WRITE_OFF,
        CreditOutcomeType.BANKRUPTCY,
        CreditOutcomeType.INSOLVENCY,
    ],
)
def test_default_event_mapping(kind: CreditOutcomeType) -> None:
    assert kind.value in label_policy()["default_events"]


@pytest.mark.parametrize(
    "kind",
    [CreditOutcomeType.NO_DEFAULT, CreditOutcomeType.LOAN_CLOSED_PERFORMING],
)
def test_non_default_event_mapping(kind: CreditOutcomeType) -> None:
    assert kind.value in label_policy()["non_default_evidence"]


def test_default_within_horizon_positive() -> None:
    obs = observation()
    result = assign_label(obs, [outcome(obs, CreditOutcomeType.DEFAULT, date(2025, 5, 12))])
    assert result.target == 1 and result.status == CreditLabelStatus.LABELED_POSITIVE


def test_no_default_complete_horizon_negative() -> None:
    obs = observation()
    result = assign_label(obs, [outcome(obs, CreditOutcomeType.NO_DEFAULT, obs.outcome_window_end)])
    assert result.target == 0 and result.status == CreditLabelStatus.LABELED_NEGATIVE


def test_incomplete_followup_censored() -> None:
    obs = observation()
    result = assign_label(obs, [outcome(obs, CreditOutcomeType.NO_DEFAULT, date(2025, 3, 31))])
    assert result.target is None and result.status == CreditLabelStatus.CENSORED


def test_default_after_horizon_is_not_positive() -> None:
    obs = observation()
    result = assign_label(
        obs, [outcome(obs, CreditOutcomeType.DEFAULT, obs.outcome_window_end + timedelta(days=1))]
    )
    assert result.target is None and result.status == CreditLabelStatus.CENSORED


def test_outcome_horizon_boundary_is_positive() -> None:
    obs = observation()
    assert (
        assign_label(obs, [outcome(obs, CreditOutcomeType.DEFAULT, obs.outcome_window_end)]).target
        == 1
    )


def test_conflicting_outcomes_conflicting() -> None:
    obs = observation()
    result = assign_label(
        obs,
        [
            outcome(obs, CreditOutcomeType.DEFAULT, date(2025, 1, 1)),
            outcome(obs, CreditOutcomeType.NO_DEFAULT, obs.outcome_window_end),
        ],
    )
    assert result.status == CreditLabelStatus.CONFLICTING and result.target is None


def test_label_quality_preserved() -> None:
    obs = observation()
    result = assign_label(
        obs,
        [
            outcome(
                obs, CreditOutcomeType.DEFAULT, date(2025, 1, 1), CreditLabelQuality.CURATED_REAL
            )
        ],
    )
    assert result.quality == CreditLabelQuality.CURATED_REAL


def test_rule_band_is_not_a_label_policy_event() -> None:
    assert "HIGH_RISK" not in label_policy()["default_events"]


def test_feature_schema_versions_and_rejects_forbidden_features() -> None:
    assert feature_schema()["version"] == FEATURE_SCHEMA_VERSION
    with pytest.raises(ValueError, match="Forbidden"):
        validate_features({"target_value": 1}, "ANOMALY_ENRICHED_V1")


def test_missing_values_are_valid_and_binary_ranges_checked() -> None:
    validate_features({"current_ratio": None, "anomaly_test": 0}, "ANOMALY_ENRICHED_V1")
    with pytest.raises(ValueError, match="0 or 1"):
        validate_features({"anomaly_test": 2}, "ANOMALY_ENRICHED_V1")


def test_feature_builder_version() -> None:
    assert FEATURE_BUILDER_VERSION == "credit_ml_feature_builder_v1"


def record(
    company: str,
    obs: str,
    split: str,
    feature_hash: str = "a",
    features: dict[str, object] | None = None,
    available: str | None = None,
    cutoff: str = "2024-09-30T23:59:00+00:00",
    availability_complete: bool = True,
) -> dict[str, object]:
    return {
        "company_id": company,
        "observation_id": obs,
        "split": split,
        "feature_hash": feature_hash,
        "features": features or {"current_ratio": 1.2},
        "source_available_at": [available] if available else [],
        "feature_cutoff_timestamp": cutoff,
        "availability_complete": availability_complete,
    }


def test_company_overlap_across_splits_detected() -> None:
    report = leakage_report([record("a", "1", "TRAIN"), record("a", "2", "TEST", "b")])
    assert report["company_overlap"]["status"] == "FAIL"  # type: ignore[index]


def test_exact_feature_hash_overlap_detected() -> None:
    report = leakage_report([record("a", "1", "TRAIN"), record("b", "2", "TEST")])
    assert report["exact_feature_overlap"]["status"] == "FAIL"  # type: ignore[index]


def test_duplicate_observation_detected() -> None:
    report = leakage_report([record("a", "1", "TRAIN"), record("b", "1", "TRAIN", "b")])
    assert report["duplicate_observations"]["status"] == "FAIL"  # type: ignore[index]


def test_target_and_outcome_date_leakage_detected() -> None:
    report = leakage_report(
        [record("a", "1", "TRAIN", features={"target_value": 1, "outcome_date": "2025-01-01"})]
    )
    assert report["target_in_features"]["status"] == "FAIL"  # type: ignore[index]


def test_future_timestamp_leakage_detected() -> None:
    report = leakage_report([record("a", "1", "TRAIN", available="2024-10-01T00:00:00+00:00")])
    assert report["future_source_timestamp"]["status"] == "FAIL"  # type: ignore[index]
    assert report["critical_failure"] is True


def test_source_available_before_cutoff_allowed() -> None:
    report = leakage_report([record("a", "1", "TRAIN", available="2024-09-01T00:00:00+00:00")])
    assert report["future_source_timestamp"]["status"] == "PASS"  # type: ignore[index]


def test_unknown_source_availability_is_review_warning() -> None:
    report = leakage_report([record("a", "1", "TRAIN", availability_complete=False)])
    assert report["unknown_source_availability"]["status"] == "WARN"  # type: ignore[index]
    assert report["critical_failure"] is False


def test_company_grouped_chronological_split_is_reproducible() -> None:
    companies = [uuid4() for _ in range(10)]
    candidates = [
        SplitCandidate(uuid4(), company, date(2015 + index, 1, 1), index % 2)
        for index, company in enumerate(companies)
    ]
    first = company_grouped_chronological_split(candidates)
    second = company_grouped_chronological_split(list(reversed(candidates)))
    assert first == sorted(second, key=lambda item: first.index(item))
    assigned = {item.observation_id: item.split for item in first}
    assert len(assigned) == len(candidates)
    train_dates = [
        item.observation_date
        for item in candidates
        if assigned[item.observation_id] == CreditDatasetSplit.TRAIN
    ]
    test_dates = [
        item.observation_date
        for item in candidates
        if assigned[item.observation_id] == CreditDatasetSplit.TEST
    ]
    assert max(train_dates) < min(test_dates)


def test_company_group_isolation_with_repeated_observations() -> None:
    company = uuid4()
    other = uuid4()
    candidates = [
        SplitCandidate(uuid4(), company, date(2020, 1, 1), 0),
        SplitCandidate(uuid4(), company, date(2021, 1, 1), 1),
        SplitCandidate(uuid4(), other, date(2022, 1, 1), 0),
    ]
    assignments = company_grouped_chronological_split(candidates)
    splits = {
        item.split
        for item in assignments
        if item.observation_id in {candidates[0].observation_id, candidates[1].observation_id}
    }
    assert len(splits) == 1


def test_split_policy_version_and_fractions() -> None:
    assert SPLIT_POLICY_VERSION == "credit_split_policy_v1"
    assert (
        sum(
            float(split_policy()[name])
            for name in ("train_fraction", "validation_fraction", "test_fraction")
        )
        == 1
    )


def test_dataset_hash_deterministic_and_config_sensitive() -> None:
    rows = [record("a", "1", "TRAIN")]
    meta = {"version": "v1"}
    assert canonical_dataset_hash(rows, meta) == canonical_dataset_hash(rows, meta)
    assert canonical_dataset_hash(rows, meta) != canonical_dataset_hash(rows, {"version": "v2"})


def test_observation_persistence_idempotency_and_dataset_build(
    db_session: Session, tmp_path: Path
) -> None:
    base = date(2010, 1, 1)
    observation_ids = []
    for index in range(10):
        company = Company(legal_name=f"Synthetic Credit Company {index}")
        db_session.add(company)
        db_session.flush()
        observed = base + timedelta(days=index * 365)
        cutoff = datetime.combine(observed, datetime.max.time(), tzinfo=UTC)
        obs = create_observation(
            db_session,
            company_id=company.id,
            observation_date=observed,
            as_of_fiscal_year=f"FY{observed.year}",
            feature_cutoff_timestamp=cutoff,
        )
        assert (
            create_observation(
                db_session,
                company_id=company.id,
                observation_date=observed,
                as_of_fiscal_year=f"FY{observed.year}",
                feature_cutoff_timestamp=cutoff,
            ).id
            == obs.id
        )
        observation_ids.append(obs.id)
        kind = CreditOutcomeType.DEFAULT if index in {1, 4, 8} else CreditOutcomeType.NO_DEFAULT
        when = (
            observed + timedelta(days=100)
            if kind == CreditOutcomeType.DEFAULT
            else obs.outcome_window_end
        )
        db_session.add(outcome(obs, kind, when))
        features = {
            "current_ratio": 0.8 + index / 10,
            "financial_completeness": 0.9,
            "anomaly_persistent_net_loss": int(index in {1, 4, 8}),
        }
        digest = hashlib.sha256(json.dumps(features, sort_keys=True).encode()).hexdigest()
        db_session.add(
            CreditMLFeatureSnapshot(
                observation_id=obs.id,
                company_id=company.id,
                observation_date=observed,
                feature_cutoff_timestamp=cutoff,
                feature_builder_version=FEATURE_BUILDER_VERSION,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                feature_group="ANOMALY_ENRICHED_V1",
                features_json=features,
                feature_count=3,
                missing_feature_count=0,
                input_hash=digest,
                availability_complete=False,
            )
        )
    censored_company = Company(legal_name="Synthetic Censored Company")
    db_session.add(censored_company)
    db_session.flush()
    censored = create_observation(
        db_session,
        company_id=censored_company.id,
        observation_date=date(2023, 1, 1),
        as_of_fiscal_year="FY2023",
        feature_cutoff_timestamp=datetime(2023, 1, 1, tzinfo=UTC),
    )
    db_session.add(outcome(censored, CreditOutcomeType.NO_DEFAULT, date(2023, 6, 1)))
    db_session.flush()
    service = CreditMLDatasetService(db_session, tmp_path)
    result = service.build()
    assert result["record_count"] == 10
    assert result["positive_count"] == 3 and result["negative_count"] == 7
    assert result["excluded"]["CENSORED"] == 1  # type: ignore[index]
    assert result["censored_count"] == 1
    assert result["real_count"] == 0 and result["synthetic_count"] == 10
    assert result["label_quality"]["SYNTHETIC"] == 10  # type: ignore[index]
    assert result["split_counts"] == {"TRAIN": 7, "VALIDATION": 2, "TEST": 1}
    assert result["split_rates"]["TRAIN"]["positive_rate"] == 0.2857  # type: ignore[index]
    assert result["split_date_ranges"]["TEST"]["start"] == "2018-12-30"  # type: ignore[index]
    assert result["training_readiness"] == "PIPELINE_VALIDATED"
    assert result["quality_status"] == "NEEDS_REVIEW"
    assert result["leakage"]["critical_failure"] is False  # type: ignore[index]
    assert service.build()["dataset_id"] == result["dataset_id"]
    with pytest.raises(ValueError, match="immutable"):
        service.build(feature_group="BASE_FINANCIAL_V1")
    assert db_session.scalar(select(func.count()).select_from(CreditMLExample)) == 10
    assert db_session.scalar(select(func.count()).select_from(CreditMLDatasetReport)) == 1
    dataset = db_session.scalar(select(MLDataset).where(MLDataset.task_type == "CREDIT_RISK"))
    assert dataset and dataset.label_policy_version == LABEL_POLICY_VERSION
    assert (tmp_path / "data/ml/credit/versions/credit_dataset_v1.jsonl").is_file()
    assert (tmp_path / "data/ml/credit/versions/credit_dataset_v1.metadata.json").is_file()


def test_critical_leakage_blocks_dataset_publication(db_session: Session, tmp_path: Path) -> None:
    for index in range(2):
        company = Company(legal_name=f"Leakage Test Company {index}")
        db_session.add(company)
        db_session.flush()
        observed = date(2020 + index, 1, 1)
        cutoff = datetime.combine(observed, datetime.max.time(), tzinfo=UTC)
        obs = create_observation(
            db_session,
            company_id=company.id,
            observation_date=observed,
            as_of_fiscal_year=f"FY{observed.year}",
            feature_cutoff_timestamp=cutoff,
        )
        db_session.add(outcome(obs, CreditOutcomeType.NO_DEFAULT, obs.outcome_window_end))
        features = {"current_ratio": 1.0, "financial_completeness": 1.0}
        db_session.add(
            CreditMLFeatureSnapshot(
                observation_id=obs.id,
                company_id=company.id,
                observation_date=observed,
                feature_cutoff_timestamp=cutoff,
                feature_builder_version=FEATURE_BUILDER_VERSION,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                feature_group="ANOMALY_ENRICHED_V1",
                features_json=features,
                feature_count=2,
                missing_feature_count=0,
                input_hash=hashlib.sha256(f"snapshot-{index}".encode()).hexdigest(),
                availability_complete=True,
            )
        )
    db_session.flush()
    with pytest.raises(ValueError, match="Critical leakage"):
        CreditMLDatasetService(db_session, tmp_path).build("leakage_dataset_v1")
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(MLDataset)
            .where(MLDataset.version == "leakage_dataset_v1")
        )
        == 0
    )
    assert {
        "CREDIT_ML_LEAKAGE_CHECK_FAILED",
        "CREDIT_ML_DATASET_BUILD_FAILED",
    } <= set(
        db_session.scalars(
            select(AuditLog.action).where(
                AuditLog.action.in_(
                    ["CREDIT_ML_LEAKAGE_CHECK_FAILED", "CREDIT_ML_DATASET_BUILD_FAILED"]
                )
            )
        ).all()
    )
    assert not (tmp_path / "data/ml/credit/versions/leakage_dataset_v1.jsonl").exists()


def test_status_reports_day_12(client) -> None:
    payload = client.get("/api/v1/status").json()
    assert payload["development_stage"]["day"] == 20
    assert payload["components"]["credit_ml_training"] in {"ready", "unavailable"}
    assert payload["components"]["production_credit_ml"] == "unavailable"
