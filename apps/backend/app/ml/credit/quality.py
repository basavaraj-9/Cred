from collections import Counter
from typing import cast

from app.ml.credit.splits import split_policy


def quality_report(
    records: list[dict[str, object]], excluded: Counter[str], leakage: dict[str, object]
) -> tuple[str, str, dict[str, object]]:
    feature_maps: list[dict[str, object]] = [
        cast(dict[str, object], row["features"])
        for row in records
        if isinstance(row.get("features"), dict)
    ]
    feature_names = sorted({name for features in feature_maps for name in features})
    missingness = {}
    for name in feature_names:
        missing = sum(features.get(name) is None for features in feature_maps)
        missingness[name] = {
            "available": len(records) - missing,
            "missing": missing,
            "missing_percent": round(missing / len(records), 4) if records else 0,
        }
    split_counts = Counter(str(row["split"]) for row in records)
    split_positive = Counter(str(row["split"]) for row in records if row["target_value"] == 1)
    split_negative = Counter(str(row["split"]) for row in records if row["target_value"] == 0)
    positives = sum(row["target_value"] == 1 for row in records)
    negatives = sum(row["target_value"] == 0 for row in records)
    qualities = Counter(str(row["label_quality"]) for row in records)
    real_count = qualities.get("VERIFIED_REAL", 0) + qualities.get("CURATED_REAL", 0)
    split_rates = {
        split: {
            "positive_rate": round(split_positive.get(split, 0) / count, 4) if count else 0,
            "negative_rate": round(split_negative.get(split, 0) / count, 4) if count else 0,
        }
        for split, count in split_counts.items()
    }
    split_date_ranges: dict[str, dict[str, str]] = {}
    for split in split_counts:
        dates = sorted(str(row["observation_date"]) for row in records if row["split"] == split)
        if dates:
            split_date_ranges[split] = {"start": dates[0], "end": dates[-1]}
    rules = split_policy()["minimum_readiness"]
    synthetic_only = bool(records) and qualities.get("SYNTHETIC", 0) == len(records)
    ready = (
        len(records) >= rules["total_examples"]
        and positives >= rules["positive_examples"]
        and negatives >= rules["negative_examples"]
        and split_positive.get("TEST", 0) >= rules["test_positives"]
        and len({row["company_id"] for row in records}) >= rules["unique_companies"]
        and not synthetic_only
    )
    availability_check = leakage.get("unknown_source_availability", {})
    availability_incomplete = (
        isinstance(availability_check, dict) and availability_check.get("status") == "WARN"
    )
    quality = (
        "INVALID"
        if leakage["critical_failure"]
        else "NEEDS_REVIEW"
        if availability_incomplete
        else "VALID"
    )
    readiness = (
        "INVALID"
        if quality == "INVALID"
        else "TRAINING_READY"
        if ready
        else "PIPELINE_VALIDATED"
        if synthetic_only
        else "NOT_TRAINING_READY"
    )
    report: dict[str, object] = {
        "record_count": len(records),
        "positive_count": positives,
        "negative_count": negatives,
        "default_rate": round(positives / len(records), 4) if records else 0,
        "excluded": dict(excluded),
        "censored_count": excluded.get("CENSORED", 0),
        "unique_companies": len({row["company_id"] for row in records}),
        "split_counts": dict(split_counts),
        "positive_by_split": dict(split_positive),
        "negative_by_split": dict(split_negative),
        "split_rates": split_rates,
        "split_date_ranges": split_date_ranges,
        "label_quality": dict(qualities),
        "verified_real_count": qualities.get("VERIFIED_REAL", 0),
        "curated_real_count": qualities.get("CURATED_REAL", 0),
        "proxy_count": qualities.get("PROXY", 0),
        "real_count": real_count,
        "synthetic_count": qualities.get("SYNTHETIC", 0),
        "feature_count": len(feature_names),
        "missingness": missingness,
        "leakage": leakage,
        "publication_availability_limitation": (
            "Source timestamps use system ingestion/creation time; original filing "
            "publication dates are not yet stored."
        ),
    }
    return quality, readiness, report
