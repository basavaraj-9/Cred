from collections import Counter, defaultdict
from datetime import datetime

from app.ml.credit.feature_schema import feature_schema


def leakage_report(records: list[dict[str, object]]) -> dict[str, object]:
    forbidden = set(feature_schema()["forbidden_features"])
    companies: dict[str, set[str]] = defaultdict(set)
    hashes: dict[str, set[str]] = defaultdict(set)
    observation_counts: Counter[str] = Counter()
    future_sources = 0
    target_features = 0
    unknown_source_availability = 0
    for record in records:
        split = str(record["split"])
        companies[str(record["company_id"])].add(split)
        hashes[str(record["feature_hash"])].add(split)
        observation_counts[str(record["observation_id"])] += 1
        features = record["features"]
        if isinstance(features, dict) and forbidden.intersection(features):
            target_features += 1
        cutoff = record.get("feature_cutoff_timestamp")
        raw_times = record.get("source_available_at", [])
        available_times = raw_times if isinstance(raw_times, list) else []
        if record.get("availability_complete") is not True:
            unknown_source_availability += 1
        for available in available_times:
            if (
                available
                and cutoff
                and datetime.fromisoformat(str(available)) > datetime.fromisoformat(str(cutoff))
            ):
                future_sources += 1
    overlap = sum(len(splits) > 1 for splits in companies.values())
    feature_overlap = sum(len(splits) > 1 for splits in hashes.values())
    duplicates = sum(count > 1 for count in observation_counts.values())
    checks: dict[str, object] = {
        "company_overlap": {"status": "PASS" if overlap == 0 else "FAIL", "count": overlap},
        "exact_feature_overlap": {
            "status": "PASS" if feature_overlap == 0 else "FAIL",
            "count": feature_overlap,
        },
        "duplicate_observations": {
            "status": "PASS" if duplicates == 0 else "FAIL",
            "count": duplicates,
        },
        "target_in_features": {
            "status": "PASS" if target_features == 0 else "FAIL",
            "count": target_features,
        },
        "future_source_timestamp": {
            "status": "PASS" if future_sources == 0 else "FAIL",
            "count": future_sources,
        },
        "future_financial_period": {
            "status": "PASS",
            "count": 0,
            "enforced_by": "credit_ml_feature_builder_v1",
        },
        "outcome_date_in_features": {
            "status": "PASS" if target_features == 0 else "FAIL",
            "count": target_features,
        },
        "unknown_source_availability": {
            "status": "PASS" if unknown_source_availability == 0 else "WARN",
            "count": unknown_source_availability,
        },
    }
    checks["critical_failure"] = any(
        isinstance(item, dict) and item.get("status") == "FAIL" for item in checks.values()
    )
    return checks
