from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.stock import MarketDataError, MarketDataRun
from app.models.stock_analytics import (
    StockFeature,
    StockFeatureRun,
    StockFundamentalRun,
    StockValuationRun,
)
from app.models.stock_intelligence import (
    StockIntelligenceComponent,
    StockIntelligenceRun,
    StockRankingMember,
    StockRankingRun,
)
from app.models.stock_ml import StockMLDatasetRow, StockMLPrediction, StockMLRun
from app.models.stock_monitoring import (
    StockComponentMonitoring,
    StockFeatureDrift,
    StockGovernanceAssessment,
    StockModelMonitoring,
    StockMonitoringFinding,
    StockMonitoringRun,
    StockProviderMonitoring,
    StockRankingMonitoring,
    StockScoreMonitoring,
)
from app.models.stock_validation import (
    StockIntelligenceValidationPeriod,
    StockIntelligenceValidationRun,
)
from app.services.rag.service import CreditRagIndexService
from app.services.stock_intelligence.service import COMPONENT_NAMES
from app.services.stock_monitoring.psi import PsiResult, population_stability_index
from app.services.stock_validation.statistics import spearman

MONITORING_VERSION = "stock_monitoring_v1"
POLICY_DIR = Path(__file__).parent


def now() -> datetime:
    return datetime.now(UTC)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, default=str, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def policy(name: str) -> dict[str, Any]:
    return json.loads((POLICY_DIR / name).read_text(encoding="utf-8"))


def decimal(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None and math.isfinite(value) else None


def average(values: list[Decimal]) -> Decimal | None:
    return decimal(statistics.fmean(float(value) for value in values)) if values else None


def std(values: list[Decimal]) -> Decimal | None:
    return decimal(statistics.pstdev(float(value) for value in values)) if values else None


def median(values: list[Decimal]) -> Decimal | None:
    return decimal(statistics.median(float(value) for value in values)) if values else None


def minimum(values: list[Decimal]) -> Decimal | None:
    return min(values) if values else None


def maximum(values: list[Decimal]) -> Decimal | None:
    return max(values) if values else None


def below_rate(values: list[Decimal], threshold: Decimal) -> Decimal | None:
    if not values:
        return None
    return Decimal(sum(value < threshold for value in values)) / Decimal(len(values))


class StockMonitoringService:
    def __init__(self, session: Session):
        self.s = session
        self.window = policy("stock_monitoring_window_policy_v1.json")
        self.drift = policy("stock_drift_policy_v1.json")
        self.governance = policy("stock_model_governance_policy_v1.json")
        self.readiness = policy("stock_recalibration_readiness_v1.json")

    def _psi(self, reference: list[Decimal], current: list[Decimal]) -> PsiResult:
        return population_stability_index(
            [float(value) for value in reference],
            [float(value) for value in current],
            requested_bins=int(self.drift["psi_bins"]),
            epsilon=float(self.drift["psi_epsilon"]),
            minimum_samples=int(self.window["minimum_rows"]),
        )

    def _severity(self, psi: float | Decimal | None, status: str = "AVAILABLE") -> str:
        if psi is None or status != "AVAILABLE":
            return "INFO"
        if float(psi) > float(self.drift["psi_thresholds"]["high"]):
            return "HIGH"
        if float(psi) >= float(self.drift["psi_thresholds"]["moderate"]):
            return "MODERATE"
        return "LOW"

    def _finding(
        self,
        run_id: UUID,
        category: str,
        metric: str,
        severity: str,
        message: str,
        *,
        entity_type: str | None = None,
        entity_name: str | None = None,
        reference: Decimal | None = None,
        current: Decimal | None = None,
        drift_value: Decimal | None = None,
        status: str | None = None,
    ) -> None:
        if status is None:
            status = (
                "REVIEW_REQUIRED"
                if severity == "HIGH"
                else "WATCH"
                if severity == "MODERATE"
                else "OBSERVED"
            )
        self.s.add(
            StockMonitoringFinding(
                monitoring_run_id=run_id,
                category=category,
                metric_name=metric,
                entity_type=entity_type,
                entity_name=entity_name,
                reference_value=reference,
                current_value=current,
                delta=(current - reference)
                if current is not None and reference is not None
                else None,
                drift_value=drift_value,
                severity=severity,
                status=status,
                message=message,
                created_at=now(),
            )
        )

    def _window_score_runs(self, start: date, end: date) -> list[StockIntelligenceRun]:
        return list(
            self.s.scalars(
                select(StockIntelligenceRun)
                .where(
                    StockIntelligenceRun.as_of_date.between(start, end),
                    StockIntelligenceRun.score.is_not(None),
                )
                .order_by(StockIntelligenceRun.as_of_date, StockIntelligenceRun.stock_listing_id)
            )
        )

    def _validate_windows(self, rs: date, re: date, cs: date, ce: date) -> None:
        if not (rs <= re < cs <= ce):
            raise AppError(
                "STOCK_MONITORING_WINDOWS_INVALID",
                "Reference and current windows must be ordered and non-overlapping",
                422,
            )

    def build_monitoring_run(
        self,
        reference_start: date,
        reference_end: date,
        current_start: date,
        current_end: date,
        actor_id: UUID,
    ) -> StockMonitoringRun:
        actor = CreditRagIndexService(self.s)._user(actor_id)
        self._validate_windows(reference_start, reference_end, current_start, current_end)
        ref_scores = self._window_score_runs(reference_start, reference_end)
        cur_scores = self._window_score_runs(current_start, current_end)
        ref_features = list(
            self.s.scalars(
                select(StockFeatureRun).where(
                    StockFeatureRun.as_of_date.between(reference_start, reference_end)
                )
            )
        )
        cur_features = list(
            self.s.scalars(
                select(StockFeatureRun).where(
                    StockFeatureRun.as_of_date.between(current_start, current_end)
                )
            )
        )
        predictions = list(
            self.s.execute(
                select(
                    StockMLPrediction.id,
                    StockMLDatasetRow.as_of_date,
                    StockMLPrediction.prediction_probability,
                    StockMLPrediction.predicted_class,
                )
                .join(StockMLDatasetRow, StockMLDatasetRow.id == StockMLPrediction.dataset_row_id)
                .where(StockMLDatasetRow.as_of_date.between(reference_start, current_end))
            )
        )
        rankings = list(
            self.s.scalars(
                select(StockRankingRun).where(
                    StockRankingRun.as_of_date.between(reference_start, current_end)
                )
            )
        )
        validations = list(
            self.s.scalars(
                select(StockIntelligenceValidationRun).where(
                    StockIntelligenceValidationRun.start_date <= current_end,
                    StockIntelligenceValidationRun.end_date >= reference_start,
                )
            )
        )
        ref_members = {run.stock_listing_id for run in ref_scores}
        cur_members = {run.stock_listing_id for run in cur_scores}
        data_sufficient = all(
            (
                len(ref_scores) >= int(self.window["minimum_rows"]),
                len(cur_scores) >= int(self.window["minimum_rows"]),
                len({item.as_of_date for item in ref_scores}) >= int(self.window["minimum_dates"]),
                len({item.as_of_date for item in cur_scores}) >= int(self.window["minimum_dates"]),
                len(ref_members) >= int(self.window["minimum_companies"]),
                len(cur_members) >= int(self.window["minimum_companies"]),
            )
        )
        ref_hash = digest(sorted(ref_members, key=str))
        cur_hash = digest(sorted(cur_members, key=str))
        changed = len(ref_members.symmetric_difference(cur_members))
        feature_run_ids = [item.id for item in ref_features + cur_features]
        feature_inputs = list(
            self.s.execute(
                select(
                    StockFeature.id,
                    StockFeature.feature_name,
                    StockFeature.value,
                    StockFeature.status,
                )
                .where(StockFeature.feature_run_id.in_(feature_run_ids))
                .order_by(StockFeature.id)
            )
        )
        ranking_ids = [item.id for item in rankings]
        ranking_inputs = list(
            self.s.execute(
                select(
                    StockRankingMember.id,
                    StockRankingMember.rank,
                    StockRankingMember.percentile,
                )
                .where(StockRankingMember.ranking_run_id.in_(ranking_ids))
                .order_by(StockRankingMember.id)
            )
        )
        input_hash = digest(
            {
                "windows": (reference_start, reference_end, current_start, current_end),
                "features": feature_inputs,
                "predictions": predictions,
                "scores": [
                    (item.id, item.score, item.confidence, item.coverage, item.band)
                    for item in ref_scores + cur_scores
                ],
                "rankings": ranking_inputs,
                "validations": sorted([run.id for run in validations], key=str),
                "policies": (self.window, self.drift, self.governance, self.readiness),
                "universes": (ref_hash, cur_hash),
            }
        )
        existing = self.s.scalar(
            select(StockMonitoringRun).where(StockMonitoringRun.input_hash == input_hash)
        )
        if existing:
            write_audit_log(
                self.s,
                entity_type="stock_monitoring_run",
                entity_id=existing.id,
                action="STOCK_MONITORING_REUSED",
                event_type="STOCK_MONITORING_REUSED",
                user_id=actor.id,
            )
            return existing
        run = StockMonitoringRun(
            monitoring_version=MONITORING_VERSION,
            drift_policy_version=self.drift["version"],
            governance_policy_version=self.governance["version"],
            window_policy_version=self.window["version"],
            recalibration_readiness_version=self.readiness["version"],
            reference_start_date=reference_start,
            reference_end_date=reference_end,
            current_start_date=current_start,
            current_end_date=current_end,
            reference_universe_hash=ref_hash,
            current_universe_hash=cur_hash,
            changed_member_count=changed,
            comparability_status="COMPARABLE"
            if ref_members == cur_members
            else "PARTIALLY_COMPARABLE",
            input_hash=input_hash,
            status="RUNNING",
            overall_health_status="INSUFFICIENT_DATA",
            recalibration_readiness_status="INSUFFICIENT_DATA",
            created_at=now(),
            completed_at=None,
        )
        self.s.add(run)
        self.s.flush()
        self._monitor_features(run, ref_features, cur_features)
        self._monitor_models(run, reference_start, reference_end, current_start, current_end)
        score_status = self._monitor_scores(run, ref_scores, cur_scores)
        self._monitor_components(run, ref_scores, cur_scores)
        ranking_status = self._monitor_rankings(run, rankings)
        stale = self._monitor_providers(run, current_end)
        self._monitor_universe_labels_validation(
            run,
            ref_members,
            cur_members,
            reference_start,
            reference_end,
            current_start,
            current_end,
        )
        self._govern(run, score_status, ranking_status, stale, data_sufficient)
        run.status = "COMPLETED" if data_sufficient else "INSUFFICIENT_DATA"
        run.completed_at = now()
        write_audit_log(
            self.s,
            entity_type="stock_monitoring_run",
            entity_id=run.id,
            action="STOCK_MONITORING_BUILT",
            event_type="STOCK_MONITORING_BUILT",
            user_id=actor.id,
        )
        return run

    def _feature_values(self, runs: list[StockFeatureRun]) -> dict[str, tuple[list[Decimal], int]]:
        run_ids = [run.id for run in runs]
        output: dict[str, tuple[list[Decimal], int]] = {}
        if not run_ids:
            return output
        grouped: dict[str, list[StockFeature]] = defaultdict(list)
        for feature in self.s.scalars(
            select(StockFeature).where(StockFeature.feature_run_id.in_(run_ids))
        ):
            grouped[feature.feature_name].append(feature)
        for name, rows in grouped.items():
            output[name] = (
                [row.value for row in rows if row.value is not None and row.status == "AVAILABLE"],
                len(rows),
            )
        return output

    def _monitor_features(
        self,
        run: StockMonitoringRun,
        reference_runs: list[StockFeatureRun],
        current_runs: list[StockFeatureRun],
    ) -> None:
        reference = self._feature_values(reference_runs)
        current = self._feature_values(current_runs)
        for name in sorted(set(reference) | set(current)):
            ref_values, ref_total = reference.get(name, ([], 0))
            cur_values, cur_total = current.get(name, ([], 0))
            psi = self._psi(ref_values, cur_values)
            ref_missing = (
                Decimal(ref_total - len(ref_values)) / Decimal(ref_total)
                if ref_total
                else Decimal("1")
            )
            cur_missing = (
                Decimal(cur_total - len(cur_values)) / Decimal(cur_total)
                if cur_total
                else Decimal("1")
            )
            missing_delta = cur_missing - ref_missing
            severity = self._severity(psi.value, psi.status)
            missing_abs = abs(missing_delta)
            if missing_abs > Decimal(str(self.drift["missing_rate_thresholds"]["high"])):
                severity = "HIGH"
            elif missing_abs >= Decimal(
                str(self.drift["missing_rate_thresholds"]["moderate"])
            ) and severity not in {"HIGH"}:
                severity = "MODERATE"
            status = psi.status if psi.status != "AVAILABLE" else "AVAILABLE"
            self.s.add(
                StockFeatureDrift(
                    monitoring_run_id=run.id,
                    feature_name=name,
                    reference_count=len(ref_values),
                    current_count=len(cur_values),
                    reference_mean=average(ref_values),
                    current_mean=average(cur_values),
                    reference_std=std(ref_values),
                    current_std=std(cur_values),
                    psi=decimal(psi.value),
                    psi_bin_count=psi.bin_count,
                    ks_statistic=None,
                    ks_pvalue=None,
                    reference_missing_rate=ref_missing,
                    current_missing_rate=cur_missing,
                    missing_rate_delta=missing_delta,
                    severity=severity,
                    status=status,
                    created_at=now(),
                )
            )
            self._finding(
                run.id,
                "FEATURE_DRIFT",
                "PSI",
                severity,
                f"{name} distribution monitoring: {status}",
                entity_type="FEATURE",
                entity_name=name,
                reference=average(ref_values),
                current=average(cur_values),
                drift_value=decimal(psi.value),
                status="INSUFFICIENT_DATA" if psi.value is None else None,
            )
            missing_severity = (
                "HIGH"
                if missing_abs > Decimal(str(self.drift["missing_rate_thresholds"]["high"]))
                else "MODERATE"
                if missing_abs >= Decimal(str(self.drift["missing_rate_thresholds"]["moderate"]))
                else "LOW"
            )
            self._finding(
                run.id,
                "FEATURE_AVAILABILITY",
                "MISSING_RATE_DELTA",
                missing_severity,
                f"{name} missing-value rate monitoring",
                entity_type="FEATURE",
                entity_name=name,
                reference=ref_missing,
                current=cur_missing,
            )

    def _monitor_models(
        self, run: StockMonitoringRun, rs: date, re: date, cs: date, ce: date
    ) -> None:
        rows = list(
            self.s.execute(
                select(StockMLPrediction, StockMLDatasetRow, StockMLRun)
                .join(StockMLDatasetRow, StockMLDatasetRow.id == StockMLPrediction.dataset_row_id)
                .join(StockMLRun, StockMLRun.id == StockMLPrediction.ml_run_id)
                .where(StockMLDatasetRow.as_of_date.between(rs, ce))
            )
        )
        groups: dict[
            tuple[str, str], list[tuple[StockMLPrediction, StockMLDatasetRow, StockMLRun]]
        ] = defaultdict(list)
        for prediction, dataset_row, ml_run in rows:
            groups[(ml_run.model_name, ml_run.model_version)].append(
                (prediction, dataset_row, ml_run)
            )
        reference_versions = {
            (ml_run.model_name, ml_run.model_version)
            for _, dataset_row, ml_run in rows
            if rs <= dataset_row.as_of_date <= re
        }
        current_versions = {
            (ml_run.model_name, ml_run.model_version)
            for _, dataset_row, ml_run in rows
            if cs <= dataset_row.as_of_date <= ce
        }
        if reference_versions != current_versions:
            run.comparability_status = "PARTIALLY_COMPARABLE"
            self._finding(
                run.id,
                "PREDICTION_DRIFT",
                "MODEL_VERSION_CHANGE",
                "MODERATE",
                "Model candidate identity differs between monitoring windows",
                entity_type="MODEL",
                status="WATCH",
            )
        for (name, version), items in sorted(groups.items()):
            ref = [
                item
                for item in items
                if rs <= item[1].as_of_date <= re and item[0].prediction_probability is not None
            ]
            cur = [
                item
                for item in items
                if cs <= item[1].as_of_date <= ce and item[0].prediction_probability is not None
            ]
            ref_p = [
                item[0].prediction_probability
                for item in ref
                if item[0].prediction_probability is not None
            ]
            cur_p = [
                item[0].prediction_probability
                for item in cur
                if item[0].prediction_probability is not None
            ]
            psi = self._psi(ref_p, cur_p)
            severity = self._severity(psi.value, psi.status)
            mature_ref = [
                item
                for item in ref
                if item[1].eligibility_status == "LABELED" and item[1].relative_return is not None
            ]
            mature_cur = [
                item
                for item in cur
                if item[1].eligibility_status == "LABELED" and item[1].relative_return is not None
            ]
            ref_metric = spearman(
                [
                    item[0].prediction_probability
                    for item in mature_ref
                    if item[0].prediction_probability is not None
                ],
                [
                    item[1].relative_return
                    for item in mature_ref
                    if item[0].prediction_probability is not None
                    and item[1].relative_return is not None
                ],
            )
            cur_metric = spearman(
                [
                    item[0].prediction_probability
                    for item in mature_cur
                    if item[0].prediction_probability is not None
                ],
                [
                    item[1].relative_return
                    for item in mature_cur
                    if item[0].prediction_probability is not None
                    and item[1].relative_return is not None
                ],
            )
            maturity = (
                "MATURE"
                if len({item[1].as_of_date for item in mature_ref + mature_cur})
                >= int(self.drift["minimum_mature_periods"])
                else "INSUFFICIENT_DATA"
            )
            self.s.add(
                StockModelMonitoring(
                    monitoring_run_id=run.id,
                    model_name=name,
                    model_version=version,
                    lifecycle=items[0][2].lifecycle,
                    reference_prediction_count=len(ref_p),
                    current_prediction_count=len(cur_p),
                    reference_probability_mean=average(ref_p),
                    current_probability_mean=average(cur_p),
                    reference_probability_median=median(ref_p),
                    current_probability_median=median(cur_p),
                    reference_probability_std=std(ref_p),
                    current_probability_std=std(cur_p),
                    reference_probability_min=minimum(ref_p),
                    current_probability_min=minimum(cur_p),
                    reference_probability_max=maximum(ref_p),
                    current_probability_max=maximum(cur_p),
                    probability_psi=decimal(psi.value),
                    reference_positive_rate=Decimal(
                        sum(item[0].predicted_class == "OUTPERFORM" for item in ref)
                    )
                    / Decimal(len(ref))
                    if ref
                    else None,
                    current_positive_rate=Decimal(
                        sum(item[0].predicted_class == "OUTPERFORM" for item in cur)
                    )
                    / Decimal(len(cur))
                    if cur
                    else None,
                    diagnostic_metric_name="SPEARMAN",
                    reference_metric=ref_metric,
                    current_metric=cur_metric,
                    metric_delta=(cur_metric - ref_metric)
                    if cur_metric is not None and ref_metric is not None
                    else None,
                    maturity_status=maturity,
                    comparability_status="COMPARABLE",
                    status=psi.status,
                    created_at=now(),
                )
            )
            self._finding(
                run.id,
                "PREDICTION_DRIFT",
                "PROBABILITY_PSI",
                severity,
                f"{name} {version} prediction distribution monitoring",
                entity_type="MODEL",
                entity_name=name,
                reference=average(ref_p),
                current=average(cur_p),
                drift_value=decimal(psi.value),
                status="INSUFFICIENT_DATA" if psi.value is None else None,
            )

    def _rates(self, values: list[str | None]) -> dict[str, float]:
        return (
            {
                name: values.count(name) / len(values)
                for name in sorted({value for value in values if value})
            }
            if values
            else {}
        )

    def _monitor_scores(
        self,
        run: StockMonitoringRun,
        ref: list[StockIntelligenceRun],
        cur: list[StockIntelligenceRun],
    ) -> str:
        ref_values = [item.score for item in ref if item.score is not None]
        cur_values = [item.score for item in cur if item.score is not None]
        psi = self._psi(ref_values, cur_values)
        severity = self._severity(psi.value, psi.status)
        status = psi.status
        ref_confidence = [item.confidence for item in ref]
        cur_confidence = [item.confidence for item in cur]
        ref_coverage = [item.coverage for item in ref]
        cur_coverage = [item.coverage for item in cur]
        self.s.add(
            StockScoreMonitoring(
                monitoring_run_id=run.id,
                score_version="stock_intelligence_score_v1",
                reference_count=len(ref_values),
                current_count=len(cur_values),
                reference_mean=average(ref_values),
                current_mean=average(cur_values),
                reference_median=median(ref_values),
                current_median=median(cur_values),
                reference_std=std(ref_values),
                current_std=std(cur_values),
                reference_min=minimum(ref_values),
                current_min=minimum(cur_values),
                reference_max=maximum(ref_values),
                current_max=maximum(cur_values),
                score_psi=decimal(psi.value),
                confidence_reference_mean=average(ref_confidence),
                confidence_current_mean=average(cur_confidence),
                confidence_reference_median=median(ref_confidence),
                confidence_current_median=median(cur_confidence),
                confidence_reference_below_rate=below_rate(
                    ref_confidence, Decimal(str(self.drift["confidence_threshold"]))
                ),
                confidence_current_below_rate=below_rate(
                    cur_confidence, Decimal(str(self.drift["confidence_threshold"]))
                ),
                coverage_reference_mean=average(ref_coverage),
                coverage_current_mean=average(cur_coverage),
                coverage_reference_median=median(ref_coverage),
                coverage_current_median=median(cur_coverage),
                coverage_reference_below_rate=below_rate(
                    ref_coverage, Decimal(str(self.drift["coverage_threshold"]))
                ),
                coverage_current_below_rate=below_rate(
                    cur_coverage, Decimal(str(self.drift["coverage_threshold"]))
                ),
                band_distribution_reference=self._rates([item.band for item in ref]),
                band_distribution_current=self._rates([item.band for item in cur]),
                status=status,
                created_at=now(),
            )
        )
        self._finding(
            run.id,
            "SCORE_DRIFT",
            "SCORE_PSI",
            severity,
            f"Score distribution monitoring: {status}",
            reference=average(ref_values),
            current=average(cur_values),
            drift_value=decimal(psi.value),
            status="INSUFFICIENT_DATA" if psi.value is None else None,
        )
        ref_bands = self._rates([item.band for item in ref])
        cur_bands = self._rates([item.band for item in cur])
        band_delta = max(
            (
                abs(cur_bands.get(name, 0.0) - ref_bands.get(name, 0.0))
                for name in set(ref_bands) | set(cur_bands)
            ),
            default=0.0,
        )
        self._finding(
            run.id,
            "SCORE_DRIFT",
            "MAX_BAND_RATE_DELTA",
            "MODERATE" if band_delta >= 0.20 else "LOW",
            "Maximum change across score-band population rates",
            reference=Decimal("0"),
            current=Decimal(str(band_delta)),
        )
        for metric, ref_metric, cur_metric in (
            (
                "CONFIDENCE_MEAN",
                average([item.confidence for item in ref]),
                average([item.confidence for item in cur]),
            ),
            (
                "COVERAGE_MEAN",
                average([item.coverage for item in ref]),
                average([item.coverage for item in cur]),
            ),
        ):
            self._finding(
                run.id,
                metric.split("_")[0] + "_DRIFT",
                metric,
                "LOW",
                f"{metric} monitoring",
                reference=ref_metric,
                current=cur_metric,
            )
        return status

    def _monitor_components(
        self,
        run: StockMonitoringRun,
        ref_scores: list[StockIntelligenceRun],
        cur_scores: list[StockIntelligenceRun],
    ) -> None:
        def grouped(scores: list[StockIntelligenceRun]) -> dict[str, tuple[list[Decimal], int]]:
            output: dict[str, list[StockIntelligenceComponent]] = defaultdict(list)
            for component in self.s.scalars(
                select(StockIntelligenceComponent).where(
                    StockIntelligenceComponent.run_id.in_([score.id for score in scores])
                )
            ):
                output[component.component_name].append(component)
            return {
                name: (
                    [item.normalized_score for item in items if item.normalized_score is not None],
                    len(items),
                )
                for name, items in output.items()
            }

        reference, current = grouped(ref_scores), grouped(cur_scores)
        for name in COMPONENT_NAMES:
            ref, ref_total = reference.get(name, ([], 0))
            cur, cur_total = current.get(name, ([], 0))
            psi = self._psi(ref, cur)
            status = psi.status
            ar = Decimal(len(ref)) / Decimal(ref_total) if ref_total else Decimal("0")
            ac = Decimal(len(cur)) / Decimal(cur_total) if cur_total else Decimal("0")
            self.s.add(
                StockComponentMonitoring(
                    monitoring_run_id=run.id,
                    component_name=name,
                    reference_count=len(ref),
                    current_count=len(cur),
                    reference_mean=average(ref),
                    current_mean=average(cur),
                    psi=decimal(psi.value),
                    availability_reference=ar,
                    availability_current=ac,
                    availability_delta=ac - ar,
                    status=status,
                    created_at=now(),
                )
            )
            self._finding(
                run.id,
                "COMPONENT_DRIFT",
                "PSI",
                self._severity(psi.value, status),
                f"{name} component monitoring: {status}",
                entity_type="COMPONENT",
                entity_name=name,
                reference=average(ref),
                current=average(cur),
                drift_value=decimal(psi.value),
                status="INSUFFICIENT_DATA" if psi.value is None else None,
            )

    def _monitor_rankings(self, run: StockMonitoringRun, rankings: list[StockRankingRun]) -> str:
        reference = [
            item
            for item in rankings
            if run.reference_start_date <= item.as_of_date <= run.reference_end_date
        ]
        current = [
            item
            for item in rankings
            if run.current_start_date <= item.as_of_date <= run.current_end_date
        ]
        if not reference or not current:
            self._finding(
                run.id,
                "RANKING_STABILITY",
                "RANK_SPEARMAN",
                "INFO",
                "Ranking comparison unavailable",
                status="INSUFFICIENT_DATA",
            )
            return "INSUFFICIENT_DATA"
        ref_run, cur_run = (
            max(reference, key=lambda item: item.as_of_date),
            max(current, key=lambda item: item.as_of_date),
        )
        ref = {
            item.stock_listing_id: item.rank
            for item in self.s.scalars(
                select(StockRankingMember).where(StockRankingMember.ranking_run_id == ref_run.id)
            )
        }
        cur = {
            item.stock_listing_id: item.rank
            for item in self.s.scalars(
                select(StockRankingMember).where(StockRankingMember.ranking_run_id == cur_run.id)
            )
        }
        common = sorted(set(ref) & set(cur), key=str)
        minimum = int(self.window["minimum_common_ranking_companies"])
        if len(common) < minimum:
            metrics: tuple[
                Decimal | None,
                Decimal | None,
                Decimal | None,
                Decimal | None,
                int,
            ] = (None, None, None, None, 0)
            status = "INSUFFICIENT_DATA"
        else:
            corr = spearman(
                [Decimal(ref[item]) for item in common], [Decimal(cur[item]) for item in common]
            )
            k = min(
                len(common),
                max(
                    int(self.window["minimum_top_k"]),
                    math.ceil(len(common) * float(self.window["top_k_percentage"])),
                ),
            )
            ref_top = set(sorted(common, key=lambda item: ref[item])[:k])
            cur_top = set(sorted(common, key=lambda item: cur[item])[:k])
            overlap = Decimal(len(ref_top & cur_top)) / Decimal(k)
            change = Decimal(sum(abs(ref[item] - cur[item]) for item in common)) / Decimal(
                len(common)
            )
            turnover = Decimal("1") - overlap
            metrics = (corr, overlap, change, turnover, k)
            status = "AVAILABLE"
        self.s.add(
            StockRankingMonitoring(
                monitoring_run_id=run.id,
                reference_ranking_id=ref_run.id,
                current_ranking_id=cur_run.id,
                common_company_count=len(common),
                actual_top_k=metrics[4],
                rank_spearman=metrics[0],
                top_k_overlap=metrics[1],
                mean_absolute_rank_change=metrics[2],
                turnover=metrics[3],
                status=status,
                created_at=now(),
            )
        )
        severity = (
            "HIGH"
            if metrics[0] is not None
            and metrics[0] < Decimal(str(self.drift["ranking_review_threshold"]))
            else "MODERATE"
            if metrics[0] is not None
            and metrics[0] < Decimal(str(self.drift["ranking_watch_threshold"]))
            else "LOW"
            if metrics[0] is not None
            else "INFO"
        )
        self._finding(
            run.id,
            "RANKING_STABILITY",
            "RANK_SPEARMAN",
            severity,
            f"Ranking stability monitoring: {status}",
            reference=Decimal("1"),
            current=metrics[0],
            status="INSUFFICIENT_DATA" if metrics[0] is None else None,
        )
        return status

    def _freshness(self, latest: date | None, current_end: date) -> tuple[int | None, str]:
        if latest is None:
            return None, "MISSING"
        age = max(0, (current_end - latest).days)
        return age, "CURRENT" if age <= int(
            self.drift["freshness_days"]["current"]
        ) else "AGING" if age <= int(self.drift["freshness_days"]["aging"]) else "STALE"

    def _monitor_providers(self, run: StockMonitoringRun, current_end: date) -> int:
        output = []
        market = self.s.scalar(
            select(MarketDataRun)
            .where(MarketDataRun.end_date <= current_end)
            .order_by(desc(MarketDataRun.end_date), desc(MarketDataRun.completed_at))
            .limit(1)
        )
        fundamental = self.s.scalar(
            select(StockFundamentalRun)
            .where(StockFundamentalRun.availability_date <= current_end)
            .order_by(
                desc(StockFundamentalRun.availability_date),
                desc(StockFundamentalRun.completed_at),
            )
            .limit(1)
        )
        market_failure = (
            self.s.scalar(
                select(func.max(MarketDataError.created_at)).where(
                    MarketDataError.market_data_run_id == market.id
                )
            )
            if market
            else None
        )
        output.append(
            (
                "MARKET",
                market.provider if market else "MISSING",
                market.provider_version if market else "UNKNOWN",
                market.end_date if market else None,
                market.completed_at if market else None,
                market.failure_count if market else 0,
            )
        )
        output.append(
            (
                "FUNDAMENTAL",
                fundamental.provider if fundamental else "MISSING",
                fundamental.provider_version if fundamental else "UNKNOWN",
                fundamental.availability_date if fundamental else None,
                fundamental.completed_at if fundamental else None,
                0,
            )
        )
        latest_feature = self.s.scalar(
            select(func.max(StockFeatureRun.as_of_date)).where(
                StockFeatureRun.as_of_date <= current_end
            )
        )
        latest_valuation = self.s.scalar(
            select(func.max(StockValuationRun.valuation_date)).where(
                StockValuationRun.valuation_date <= current_end
            )
        )
        latest_prediction = self.s.scalar(
            select(func.max(StockMLDatasetRow.as_of_date))
            .join(StockMLPrediction, StockMLPrediction.dataset_row_id == StockMLDatasetRow.id)
            .where(StockMLDatasetRow.as_of_date <= current_end)
        )
        latest_score = self.s.scalar(
            select(func.max(StockIntelligenceRun.as_of_date)).where(
                StockIntelligenceRun.as_of_date <= current_end
            )
        )
        output.extend(
            (
                ("FEATURE_STORE", "INTERNAL", "stock_features_v1", latest_feature, None, 0),
                ("VALUATION", "INTERNAL", "stock_valuation_v1", latest_valuation, None, 0),
                (
                    "PREDICTION",
                    "INTERNAL",
                    "stock_ml_prediction_v1",
                    latest_prediction,
                    None,
                    0,
                ),
                ("SCORE", "INTERNAL", "stock_intelligence_score_v1", latest_score, None, 0),
            )
        )
        stale = 0
        for provider_type, name, version, latest, success, failures in output:
            age, status = self._freshness(latest, current_end)
            stale += status in {"STALE", "MISSING"}
            self.s.add(
                StockProviderMonitoring(
                    monitoring_run_id=run.id,
                    provider_type=provider_type,
                    provider_name=name,
                    provider_version=version,
                    provider_classification="DEVELOPMENT",
                    last_success_at=success,
                    last_failure_at=market_failure if provider_type == "MARKET" else None,
                    failure_count=failures,
                    freshness_age_days=age,
                    freshness_status=status,
                    created_at=now(),
                )
            )
            self._finding(
                run.id,
                "DATA_FRESHNESS",
                provider_type,
                "HIGH"
                if status == "STALE"
                else "MODERATE"
                if status == "AGING"
                else "LOW"
                if status == "CURRENT"
                else "INFO",
                f"{provider_type} development-provider freshness: {status}",
                current=Decimal(age) if age is not None else None,
                status="INSUFFICIENT_DATA" if status == "MISSING" else None,
            )
        return stale

    def _monitor_universe_labels_validation(
        self,
        run: StockMonitoringRun,
        ref_members: set[UUID],
        cur_members: set[UUID],
        rs: date,
        re: date,
        cs: date,
        ce: date,
    ) -> None:
        self._finding(
            run.id,
            "UNIVERSE_CHANGE",
            "CHANGED_MEMBER_COUNT",
            "MODERATE" if run.changed_member_count else "LOW",
            "Universe membership comparison",
            reference=Decimal(len(ref_members)),
            current=Decimal(len(cur_members)),
        )
        rows = list(
            self.s.scalars(
                select(StockMLDatasetRow).where(StockMLDatasetRow.as_of_date.between(rs, ce))
            )
        )
        for label, start, end in (("REFERENCE", rs, re), ("CURRENT", cs, ce)):
            window = [row for row in rows if start <= row.as_of_date <= end]
            censored = (
                Decimal(sum(row.eligibility_status == "CENSORED" for row in window))
                / Decimal(len(window))
                if window
                else None
            )
            self._finding(
                run.id,
                "LABEL_DISTRIBUTION_DRIFT",
                f"{label}_CENSORED_RATE",
                "LOW",
                f"{label} mature/censored label distribution",
                current=censored,
                status="INSUFFICIENT_DATA" if not window else None,
            )
        periods = list(
            self.s.execute(
                select(
                    StockIntelligenceValidationPeriod.spearman,
                    StockIntelligenceValidationPeriod.top_bottom_spread,
                    StockIntelligenceValidationPeriod.as_of_date,
                )
                .join(StockIntelligenceValidationRun)
                .where(StockIntelligenceValidationPeriod.as_of_date.between(rs, ce))
            )
        )
        for metric, index in (("MEAN_SPEARMAN", 0), ("MEAN_SPREAD", 1)):
            ref = [
                row[index]
                for row in periods
                if rs <= row.as_of_date <= re and row[index] is not None
            ]
            cur = [
                row[index]
                for row in periods
                if cs <= row.as_of_date <= ce and row[index] is not None
            ]
            self._finding(
                run.id,
                "MODEL_DIAGNOSTIC_DRIFT",
                metric,
                "LOW" if ref and cur else "INFO",
                "Day 26 validation diagnostic trend",
                reference=average(ref),
                current=average(cur),
                status="INSUFFICIENT_DATA" if not ref or not cur else None,
            )

    def _govern(
        self,
        run: StockMonitoringRun,
        score_status: str,
        ranking_status: str,
        stale: int,
        data_sufficient: bool,
    ) -> None:
        findings = list(
            self.s.scalars(
                select(StockMonitoringFinding).where(
                    StockMonitoringFinding.monitoring_run_id == run.id
                )
            )
        )
        high = sum(item.severity == "HIGH" for item in findings)
        moderate = sum(item.severity == "MODERATE" for item in findings)
        high_features = sum(
            item.severity == "HIGH" and item.category == "FEATURE_DRIFT" for item in findings
        )
        model_drift = sum(
            item.severity in {"HIGH", "MODERATE"}
            and item.category in {"PREDICTION_DRIFT", "MODEL_DIAGNOSTIC_DRIFT"}
            for item in findings
        )
        sufficient = data_sufficient and any(
            item.status != "INSUFFICIENT_DATA" for item in findings
        )
        if not sufficient:
            health = "INSUFFICIENT_DATA"
            readiness = "INSUFFICIENT_DATA"
        elif (
            high >= int(self.governance["review_minimum_high_findings"])
            and len({item.category for item in findings if item.severity == "HIGH"}) >= 2
        ):
            health = "REVIEW_REQUIRED"
            readiness = "RESEARCH_REVIEW_RECOMMENDED"
        elif high or moderate >= int(self.governance["watch_minimum_moderate_findings"]) or stale:
            health = "WATCH"
            readiness = "MONITOR"
        else:
            health = "HEALTHY"
            readiness = "NOT_INDICATED"
        reasons = [f"{high} high-severity findings across guarded metrics"] if high else []
        against = [
            "No automatic retraining, recalibration, model promotion, or policy "
            "change is permitted."
        ]
        insufficient = sorted(
            {item.category for item in findings if item.status == "INSUFFICIENT_DATA"}
        )
        assessment = StockGovernanceAssessment(
            monitoring_run_id=run.id,
            health_status=health,
            recalibration_readiness_status=readiness,
            high_severity_count=high,
            moderate_severity_count=moderate,
            stale_provider_count=stale,
            high_drift_feature_count=high_features,
            model_drift_count=model_drift,
            score_drift_status=score_status,
            ranking_stability_status=ranking_status,
            reasons_for_review=reasons,
            reasons_against_review=against,
            insufficient_evidence=insufficient,
            summary=(
                f"Research monitoring health is {health}; recalibration readiness is "
                f"{readiness}. No automatic action was taken."
            ),
            created_at=now(),
        )
        self.s.add(assessment)
        run.overall_health_status = health
        run.recalibration_readiness_status = readiness
        if high:
            write_audit_log(
                self.s,
                entity_type="stock_monitoring_run",
                entity_id=run.id,
                action="STOCK_DRIFT_HIGH_DETECTED",
                event_type="STOCK_DRIFT_HIGH_DETECTED",
            )
        if readiness == "RESEARCH_REVIEW_RECOMMENDED":
            write_audit_log(
                self.s,
                entity_type="stock_monitoring_run",
                entity_id=run.id,
                action="STOCK_GOVERNANCE_REVIEW_RECOMMENDED",
                event_type="STOCK_GOVERNANCE_REVIEW_RECOMMENDED",
            )
