from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.stock import ListedCompany
from app.models.stock_intelligence import (
    StockIntelligenceComponent,
    StockIntelligenceRun,
    StockRankingMember,
    StockRankingRun,
)
from app.models.stock_ml import StockMLDataset, StockMLDatasetRow
from app.models.stock_validation import (
    StockIntelligenceAblationMetric,
    StockIntelligenceAblationRun,
    StockIntelligenceComponentCorrelation,
    StockIntelligenceComponentValidation,
    StockIntelligenceSegmentValidation,
    StockIntelligenceSensitivityRun,
    StockIntelligenceValidationBucket,
    StockIntelligenceValidationMember,
    StockIntelligenceValidationPeriod,
    StockIntelligenceValidationRun,
)
from app.services.rag.service import CreditRagIndexService
from app.services.stock_intelligence.service import COMPONENT_NAMES, StockIntelligenceService
from app.services.stock_validation.statistics import (
    mean,
    median,
    monotonicity,
    population_std,
    quantile_buckets,
    spearman,
)

VALIDATION_VERSION = "stock_intelligence_validation_v1"
POLICY_DIR = Path(__file__).parent


def now() -> datetime:
    return datetime.now(UTC)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, default=str, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_policy(name: str) -> dict[str, Any]:
    return json.loads((POLICY_DIR / name).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class HistoricalRow:
    label_row_id: UUID
    as_of_date: date
    listed_company_id: UUID
    stock_listing_id: UUID
    score_run_id: UUID
    ranking_run_id: UUID
    score: Decimal
    confidence: Decimal
    coverage: Decimal
    rank: int
    percentile: Decimal
    research_priority: str
    relative_return: Decimal
    label_class: str
    rank_target: Decimal | None
    sector: str
    contradictions: tuple[str, ...]
    components: dict[str, Decimal]


@dataclass(frozen=True)
class MetricSet:
    spearman: Decimal | None
    spread: Decimal | None
    hit_rate: Decimal | None
    monotonicity: Decimal | None
    monotonicity_status: str
    bucket_method: str
    buckets: tuple[tuple[str, int, list[Decimal], list[str]], ...]


class StockIntelligenceValidationService:
    def __init__(self, session: Session):
        self.s = session
        self.policy = load_policy("stock_intelligence_validation_policy_v1.json")
        self.ablation = load_policy("stock_intelligence_ablation_policy_v1.json")
        self.robustness = load_policy("stock_intelligence_robustness_policy_v1.json")
        self.fusion = load_policy("../stock_intelligence/stock_intelligence_fusion_policy_v1.json")

    def _dataset(self, start_date: date, end_date: date) -> StockMLDataset:
        dataset = self.s.scalar(
            select(StockMLDataset)
            .where(
                StockMLDataset.label_policy_version == self.policy["label_policy_version"],
                StockMLDataset.start_date <= end_date,
                StockMLDataset.end_date >= start_date,
            )
            .order_by(desc(StockMLDataset.created_at), desc(StockMLDataset.id))
        )
        if dataset is None:
            raise AppError(
                "STOCK_VALIDATION_DATASET_NOT_FOUND",
                "No Day 24 dataset with the required label policy covers this date range",
                404,
            )
        return dataset

    def _source_rows(
        self, start_date: date, end_date: date
    ) -> tuple[StockMLDataset, list[StockMLDatasetRow]]:
        dataset = self._dataset(start_date, end_date)
        rows = list(
            self.s.scalars(
                select(StockMLDatasetRow)
                .where(
                    StockMLDatasetRow.dataset_id == dataset.id,
                    StockMLDatasetRow.as_of_date >= start_date,
                    StockMLDatasetRow.as_of_date <= end_date,
                )
                .order_by(StockMLDatasetRow.as_of_date, StockMLDatasetRow.stock_listing_id)
            )
        )
        return dataset, rows

    def _materialize_history(
        self, start_date: date, end_date: date, actor_id: UUID
    ) -> tuple[list[HistoricalRow], int, list[UUID], list[UUID], StockMLDataset]:
        dataset, source_rows = self._source_rows(start_date, end_date)
        companies = {
            company.id: company
            for company in self.s.scalars(
                select(ListedCompany).where(
                    ListedCompany.id.in_({row.listed_company_id for row in source_rows})
                )
            )
        }
        rows_by_date: dict[date, list[StockMLDatasetRow]] = {}
        for row in source_rows:
            rows_by_date.setdefault(row.as_of_date, []).append(row)
        history: list[HistoricalRow] = []
        ranking_ids: list[UUID] = []
        score_ids: list[UUID] = []
        censored = sum(row.eligibility_status == "CENSORED" for row in source_rows)
        intelligence = StockIntelligenceService(self.s)
        statuses = set(self.policy["eligible_score_statuses"])
        minimum_coverage = Decimal(str(self.policy["minimum_coverage"]))
        minimum_confidence = Decimal(str(self.policy["minimum_confidence"]))
        for as_of, date_rows in rows_by_date.items():
            ranking = intelligence.build_ranking(
                as_of, actor_id, [row.stock_listing_id for row in date_rows]
            )
            ranking_ids.append(ranking.id)
            members = list(
                self.s.scalars(
                    select(StockRankingMember).where(
                        StockRankingMember.ranking_run_id == ranking.id
                    )
                )
            )
            member_by_listing = {member.stock_listing_id: member for member in members}
            score_runs = {
                score.id: score
                for score in self.s.scalars(
                    select(StockIntelligenceRun).where(
                        StockIntelligenceRun.id.in_(
                            [member.stock_intelligence_run_id for member in members]
                        )
                    )
                )
            }
            components_by_run: dict[UUID, dict[str, Decimal]] = {}
            for component in self.s.scalars(
                select(StockIntelligenceComponent).where(
                    StockIntelligenceComponent.run_id.in_(list(score_runs))
                )
            ):
                if component.normalized_score is not None:
                    components_by_run.setdefault(component.run_id, {})[component.component_name] = (
                        component.normalized_score
                    )
            for label in date_rows:
                member = member_by_listing.get(label.stock_listing_id)
                if member is None:
                    continue
                score_run = score_runs[member.stock_intelligence_run_id]
                score_ids.append(score_run.id)
                if (
                    label.eligibility_status != "LABELED"
                    or label.relative_return is None
                    or label.label_class is None
                    or score_run.status not in statuses
                    or score_run.score is None
                    or score_run.coverage < minimum_coverage
                    or score_run.confidence < minimum_confidence
                ):
                    continue
                company = companies[label.listed_company_id]
                history.append(
                    HistoricalRow(
                        label_row_id=label.id,
                        as_of_date=as_of,
                        listed_company_id=label.listed_company_id,
                        stock_listing_id=label.stock_listing_id,
                        score_run_id=score_run.id,
                        ranking_run_id=ranking.id,
                        score=score_run.score,
                        confidence=score_run.confidence,
                        coverage=score_run.coverage,
                        rank=member.rank,
                        percentile=member.percentile,
                        research_priority=member.research_priority,
                        relative_return=label.relative_return,
                        label_class=label.label_class,
                        rank_target=label.rank_target,
                        sector=company.sector or "UNCLASSIFIED",
                        contradictions=tuple(sorted(score_run.contradictions)),
                        components=components_by_run.get(score_run.id, {}),
                    )
                )
        return (
            history,
            censored,
            sorted(set(score_ids), key=str),
            sorted(set(ranking_ids), key=str),
            dataset,
        )

    def _group_dates(self, rows: list[HistoricalRow]) -> dict[date, list[HistoricalRow]]:
        grouped: dict[date, list[HistoricalRow]] = {}
        for row in rows:
            grouped.setdefault(row.as_of_date, []).append(row)
        return grouped

    def _metrics(
        self, rows: list[HistoricalRow], score_getter: Callable[[HistoricalRow], Decimal]
    ) -> MetricSet:
        minimum = int(self.policy["minimum_companies_per_date"])
        if len(rows) < minimum:
            return MetricSet(None, None, None, None, "INSUFFICIENT_DATA", "NONE", ())
        scores = [score_getter(row) for row in rows]
        returns = [row.relative_return for row in rows]
        quintile_minimum = int(self.policy["quintile_minimum_companies"])
        tercile_minimum = int(self.policy["tercile_minimum_companies"])
        method = (
            "QUINTILE"
            if len(rows) >= quintile_minimum
            else "TERCILE"
            if len(rows) >= tercile_minimum
            else "NONE"
        )
        if method == "NONE":
            return MetricSet(
                spearman(scores, returns), None, None, None, "INSUFFICIENT_DATA", method, ()
            )
        buckets: list[tuple[str, int, list[Decimal], list[str]]] = []
        for bucket in quantile_buckets(scores, method):
            buckets.append(
                (
                    bucket.name,
                    bucket.order,
                    [returns[index] for index in bucket.indexes],
                    [rows[index].label_class for index in bucket.indexes],
                )
            )
        bucket_means = [mean(item[2]) for item in buckets]
        complete_means = [item for item in bucket_means if item is not None]
        monotonicity_score, monotonicity_status = monotonicity(complete_means)
        spread = complete_means[-1] - complete_means[0] if len(complete_means) >= 2 else None
        top_labels = buckets[-1][3]
        hit_rate = Decimal(sum(label == "OUTPERFORM" for label in top_labels)) / Decimal(
            len(top_labels)
        )
        return MetricSet(
            spearman(scores, returns),
            spread,
            hit_rate,
            monotonicity_score,
            monotonicity_status,
            method,
            tuple(buckets),
        )

    def build_validation(
        self,
        start_date: date,
        end_date: date,
        actor_id: UUID,
        score_version: str = "stock_intelligence_score_v1",
    ) -> StockIntelligenceValidationRun:
        actor = CreditRagIndexService(self.s)._user(actor_id)
        if start_date > end_date:
            raise AppError(
                "STOCK_VALIDATION_DATE_RANGE_INVALID",
                "Start date must be on or before end date",
                422,
            )
        if score_version != self.policy["score_version"]:
            raise AppError(
                "STOCK_VALIDATION_SCORE_VERSION_UNSUPPORTED",
                "Only the immutable Day 25 score version is supported",
                422,
            )
        history, censored, score_ids, ranking_ids, dataset = self._materialize_history(
            start_date, end_date, actor.id
        )
        _, label_rows = self._source_rows(start_date, end_date)
        input_hash = digest(
            {
                "validation": self.policy,
                "ablation": self.ablation,
                "robustness": self.robustness,
                "score_version": score_version,
                "score_run_ids": score_ids,
                "ranking_run_ids": ranking_ids,
                "labels": [
                    (
                        row.id,
                        row.stock_listing_id,
                        row.as_of_date,
                        row.eligibility_status,
                        row.relative_return,
                        row.label_class,
                        row.rank_target,
                    )
                    for row in label_rows
                ],
                "universe": [(row.as_of_date, row.stock_listing_id) for row in label_rows],
                "date_range": (start_date, end_date),
            }
        )
        existing = self.s.scalar(
            select(StockIntelligenceValidationRun).where(
                StockIntelligenceValidationRun.input_hash == input_hash
            )
        )
        if existing:
            write_audit_log(
                self.s,
                entity_type="stock_intelligence_validation_run",
                entity_id=existing.id,
                action="STOCK_INTELLIGENCE_VALIDATION_REUSED",
                event_type="STOCK_INTELLIGENCE_VALIDATION_REUSED",
                user_id=actor.id,
            )
            return existing
        grouped = self._group_dates(history)
        minimum_dates = int(self.policy["minimum_historical_dates"])
        run = StockIntelligenceValidationRun(
            validation_version=VALIDATION_VERSION,
            validation_policy_version=str(self.policy["version"]),
            ablation_policy_version=str(self.ablation["version"]),
            robustness_policy_version=str(self.robustness["version"]),
            score_version=score_version,
            label_policy_version=dataset.label_policy_version,
            start_date=start_date,
            end_date=end_date,
            input_hash=input_hash,
            status="RUNNING",
            result_status="INSUFFICIENT_DATA",
            historical_date_count=len(grouped),
            eligible_row_count=len(history),
            censored_row_count=censored,
            mean_spearman=None,
            median_spearman=None,
            mean_top_bottom_spread=None,
            created_at=now(),
            completed_at=None,
        )
        self.s.add(run)
        self.s.flush()
        period_metrics: list[MetricSet] = []
        for as_of, rows in sorted(grouped.items()):
            metrics = self._metrics(rows, lambda row: row.score)
            period_metrics.append(metrics)
            period = StockIntelligenceValidationPeriod(
                validation_run_id=run.id,
                ranking_run_id=rows[0].ranking_run_id,
                as_of_date=as_of,
                eligible_company_count=len(rows),
                bucket_method=metrics.bucket_method,
                spearman=metrics.spearman,
                kendall=None,
                top_bottom_spread=metrics.spread,
                top_bucket_hit_rate=metrics.hit_rate,
                monotonicity_score=metrics.monotonicity,
                monotonicity_status=metrics.monotonicity_status,
                mean_score=mean([row.score for row in rows]),
                median_score=median([row.score for row in rows]),
                score_std=population_std([row.score for row in rows]),
                mean_confidence=mean([row.confidence for row in rows]),
                mean_coverage=mean([row.coverage for row in rows]),
                created_at=now(),
            )
            self.s.add(period)
            self.s.flush()
            for row in rows:
                self.s.add(
                    StockIntelligenceValidationMember(
                        validation_run_id=run.id,
                        validation_period_id=period.id,
                        dataset_row_id=row.label_row_id,
                        score_run_id=row.score_run_id,
                        ranking_run_id=row.ranking_run_id,
                        listed_company_id=row.listed_company_id,
                        stock_listing_id=row.stock_listing_id,
                        as_of_date=row.as_of_date,
                        score=row.score,
                        confidence=row.confidence,
                        coverage=row.coverage,
                        rank=row.rank,
                        percentile=row.percentile,
                        future_relative_return=row.relative_return,
                        future_rank_target=row.rank_target,
                        label_class=row.label_class,
                        label_status="LABELED",
                        created_at=now(),
                    )
                )
            for bucket_name, bucket_order, values, labels in metrics.buckets:
                self.s.add(
                    StockIntelligenceValidationBucket(
                        validation_period_id=period.id,
                        bucket_name=bucket_name,
                        bucket_order=bucket_order,
                        company_count=len(values),
                        mean_relative_return=mean(values),
                        median_relative_return=median(values),
                        positive_rate=Decimal(sum(value > 0 for value in values))
                        / Decimal(len(values)),
                        std_relative_return=population_std(values),
                        minimum_relative_return=min(values),
                        maximum_relative_return=max(values),
                        created_at=now(),
                    )
                )
        valid_spearman = [item.spearman for item in period_metrics if item.spearman is not None]
        valid_spreads = [item.spread for item in period_metrics if item.spread is not None]
        run.mean_spearman = mean(valid_spearman)
        run.median_spearman = median(valid_spearman)
        run.mean_top_bottom_spread = mean(valid_spreads)
        self._persist_components(run.id, grouped)
        self._persist_correlations(run.id, grouped)
        self._persist_segments(run.id, history)
        run.status = "COMPLETED" if len(grouped) >= minimum_dates else "INSUFFICIENT_DATA"
        run.result_status = (
            "RESEARCH_DIAGNOSTICS_AVAILABLE"
            if valid_spearman and len(grouped) >= minimum_dates
            else "INSUFFICIENT_DATA"
        )
        run.completed_at = now()
        write_audit_log(
            self.s,
            entity_type="stock_intelligence_validation_run",
            entity_id=run.id,
            action="STOCK_INTELLIGENCE_VALIDATION_BUILT",
            event_type="STOCK_INTELLIGENCE_VALIDATION_BUILT",
            user_id=actor.id,
            metadata_json={
                "historical_date_count": len(grouped),
                "eligible_row_count": len(history),
            },
        )
        return run

    def _persist_components(self, run_id: UUID, grouped: dict[date, list[HistoricalRow]]) -> None:
        for component_name in COMPONENT_NAMES:
            correlations: list[Decimal] = []
            sample_count = 0
            for rows in grouped.values():
                eligible = [row for row in rows if component_name in row.components]
                correlation = spearman(
                    [row.components[component_name] for row in eligible],
                    [row.relative_return for row in eligible],
                )
                sample_count += len(eligible)
                if correlation is not None:
                    correlations.append(correlation)
            self.s.add(
                StockIntelligenceComponentValidation(
                    validation_run_id=run_id,
                    component_name=component_name,
                    valid_period_count=len(correlations),
                    sample_count=sample_count,
                    mean_spearman=mean(correlations),
                    median_spearman=median(correlations),
                    std_spearman=population_std(correlations),
                    minimum_spearman=min(correlations) if correlations else None,
                    maximum_spearman=max(correlations) if correlations else None,
                    created_at=now(),
                )
            )

    def _persist_correlations(self, run_id: UUID, grouped: dict[date, list[HistoricalRow]]) -> None:
        thresholds = self.policy["redundancy_thresholds"]
        assert isinstance(thresholds, dict)
        for component_a, component_b in itertools.combinations(COMPONENT_NAMES, 2):
            date_correlations: list[Decimal] = []
            sample_count = 0
            for rows in grouped.values():
                eligible = [
                    row
                    for row in rows
                    if component_a in row.components and component_b in row.components
                ]
                sample_count += len(eligible)
                correlation = spearman(
                    [row.components[component_a] for row in eligible],
                    [row.components[component_b] for row in eligible],
                )
                if correlation is not None:
                    date_correlations.append(correlation)
            aggregate = mean(date_correlations)
            if aggregate is None:
                status = "INSUFFICIENT_DATA"
            elif abs(aggregate) >= Decimal(str(thresholds["high"])):
                status = "HIGH"
            elif abs(aggregate) >= Decimal(str(thresholds["moderate"])):
                status = "MODERATE"
            else:
                status = "LOW"
            self.s.add(
                StockIntelligenceComponentCorrelation(
                    validation_run_id=run_id,
                    component_a=component_a,
                    component_b=component_b,
                    correlation=aggregate,
                    sample_count=sample_count,
                    redundancy_status=status,
                    created_at=now(),
                )
            )

    def _persist_segments(self, run_id: UUID, history: list[HistoricalRow]) -> None:
        segment_rows: dict[tuple[str, str], list[HistoricalRow]] = {}
        for band in self.policy["confidence_bands"]:
            segment_rows[("CONFIDENCE", str(band["name"]))] = []
        for band in self.policy["coverage_bands"]:
            segment_rows[("COVERAGE", str(band["name"]))] = []
        for priority in (
            "RESEARCH_PRIORITY_HIGH",
            "RESEARCH_PRIORITY_MEDIUM",
            "RESEARCH_PRIORITY_LOW",
        ):
            segment_rows[("WATCHLIST", priority)] = []
        for row in history:
            for band in self.policy["confidence_bands"]:
                if Decimal(str(band["minimum"])) <= row.confidence < Decimal(str(band["maximum"])):
                    segment_rows.setdefault(("CONFIDENCE", str(band["name"])), []).append(row)
            for band in self.policy["coverage_bands"]:
                if Decimal(str(band["minimum"])) <= row.coverage < Decimal(str(band["maximum"])):
                    segment_rows.setdefault(("COVERAGE", str(band["name"])), []).append(row)
            segment_rows.setdefault(("SECTOR", row.sector), []).append(row)
            segment_rows.setdefault(("WATCHLIST", row.research_priority), []).append(row)
            for contradiction in row.contradictions:
                segment_rows.setdefault(("CONTRADICTION", contradiction), []).append(row)
        minimum = int(self.policy["segment_minimum_sample_size"])
        for (segment_type, segment_value), rows in sorted(segment_rows.items()):
            eligible = len(rows) >= minimum
            metric = self._pooled_segment_metric(rows) if eligible else (None, None, None)
            if segment_type == "SECTOR":
                available = eligible and any(value is not None for value in metric)
            else:
                available = eligible
            returns = [row.relative_return for row in rows]
            self.s.add(
                StockIntelligenceSegmentValidation(
                    validation_run_id=run_id,
                    segment_type=segment_type,
                    segment_value=segment_value,
                    sample_count=len(rows),
                    period_count=len({row.as_of_date for row in rows}),
                    spearman=metric[0],
                    top_bottom_spread=metric[1],
                    top_bucket_hit_rate=metric[2],
                    mean_relative_return=mean(returns),
                    median_relative_return=median(returns),
                    std_relative_return=population_std(returns),
                    positive_rate=(
                        Decimal(sum(row.relative_return > 0 for row in rows)) / Decimal(len(rows))
                    )
                    if rows
                    else None,
                    status="AVAILABLE" if available else "INSUFFICIENT_DATA",
                    created_at=now(),
                )
            )

    def _pooled_segment_metric(
        self, rows: list[HistoricalRow]
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        correlations: list[Decimal] = []
        spreads: list[Decimal] = []
        hit_rates: list[Decimal] = []
        for date_rows in self._group_dates(rows).values():
            metrics = self._metrics(date_rows, lambda row: row.score)
            if metrics.spearman is not None:
                correlations.append(metrics.spearman)
            if metrics.spread is not None:
                spreads.append(metrics.spread)
            if metrics.hit_rate is not None:
                hit_rates.append(metrics.hit_rate)
        return mean(correlations), mean(spreads), mean(hit_rates)

    def _run(self, run_id: UUID) -> StockIntelligenceValidationRun:
        run = self.s.get(StockIntelligenceValidationRun, run_id)
        if run is None:
            raise AppError("STOCK_VALIDATION_NOT_FOUND", "Stock validation run not found", 404)
        return run

    def _history_for_run(
        self, run: StockIntelligenceValidationRun, actor_id: UUID
    ) -> list[HistoricalRow]:
        history, _, _, _, _ = self._materialize_history(run.start_date, run.end_date, actor_id)
        return history

    def _normalized_weights(self, removed: set[str]) -> dict[str, Decimal]:
        base = {
            name: Decimal(str(value))
            for name, value in self.fusion["weights"].items()
            if name not in removed
        }
        total = sum(base.values(), Decimal("0"))
        return {name: value / total * Decimal("100") for name, value in base.items()}

    def _experimental_score(
        self, row: HistoricalRow, weights: dict[str, Decimal]
    ) -> Decimal | None:
        available = sum(weight for name, weight in weights.items() if name in row.components)
        if available < Decimal("70"):
            return None
        return sum(
            (
                row.components[name] * weight / Decimal("100")
                for name, weight in weights.items()
                if name in row.components
            ),
            Decimal("0"),
        )

    def run_ablation(
        self, validation_run_id: UUID, actor_id: UUID
    ) -> list[StockIntelligenceAblationRun]:
        actor = CreditRagIndexService(self.s)._user(actor_id)
        validation = self._run(validation_run_id)
        history = self._history_for_run(validation, actor.id)
        grouped = self._group_dates(history)
        outputs: list[StockIntelligenceAblationRun] = []
        experiments = self.ablation["experiments"]
        assert isinstance(experiments, dict)
        for experiment_name, removed_value in experiments.items():
            removed = set(removed_value)
            weights = self._normalized_weights(removed)
            input_hash = digest(
                {
                    "validation": validation.input_hash,
                    "experiment": experiment_name,
                    "weights": weights,
                    "policy": self.ablation,
                }
            )
            existing = self.s.scalar(
                select(StockIntelligenceAblationRun).where(
                    StockIntelligenceAblationRun.input_hash == input_hash
                )
            )
            if existing:
                outputs.append(existing)
                continue
            experiment = StockIntelligenceAblationRun(
                validation_run_id=validation.id,
                experiment_name=str(experiment_name),
                ablation_policy_version=str(self.ablation["version"]),
                removed_components_json=sorted(removed),
                weights_json={name: float(value) for name, value in weights.items()},
                input_hash=input_hash,
                status="RUNNING",
                created_at=now(),
            )
            self.s.add(experiment)
            self.s.flush()
            metrics_by_date: list[MetricSet] = []
            sample_count = 0
            for rows in grouped.values():
                eligible = [(row, self._experimental_score(row, weights)) for row in rows]
                usable = [(row, score) for row, score in eligible if score is not None]
                sample_count += len(usable)
                if usable:
                    score_map = {row.score_run_id: score for row, score in usable}
                    metrics_by_date.append(
                        self._metrics(
                            [row for row, _ in usable], lambda row: score_map[row.score_run_id]
                        )
                    )
            metric_values: dict[str, list[Decimal]] = {
                "MEAN_SPEARMAN": [
                    metric.spearman for metric in metrics_by_date if metric.spearman is not None
                ],
                "MEAN_TOP_BOTTOM_SPREAD": [
                    metric.spread for metric in metrics_by_date if metric.spread is not None
                ],
                "MEAN_TOP_BUCKET_HIT_RATE": [
                    metric.hit_rate for metric in metrics_by_date if metric.hit_rate is not None
                ],
                "MEAN_MONOTONICITY": [
                    metric.monotonicity
                    for metric in metrics_by_date
                    if metric.monotonicity is not None
                ],
            }
            for metric_name, values in metric_values.items():
                self.s.add(
                    StockIntelligenceAblationMetric(
                        ablation_run_id=experiment.id,
                        metric_name=metric_name,
                        metric_value=mean(values),
                        valid_period_count=len(values),
                        sample_count=sample_count,
                        created_at=now(),
                    )
                )
            experiment.status = "COMPLETED" if any(metric_values.values()) else "INSUFFICIENT_DATA"
            outputs.append(experiment)
        write_audit_log(
            self.s,
            entity_type="stock_intelligence_validation_run",
            entity_id=validation.id,
            action="STOCK_INTELLIGENCE_ABLATION_BUILT",
            event_type="STOCK_INTELLIGENCE_ABLATION_BUILT",
            user_id=actor.id,
            metadata_json={"experiment_count": len(outputs)},
        )
        return outputs

    def _perturbed_weights(self, component: str, multiplier: Decimal) -> dict[str, Decimal]:
        base = {name: Decimal(str(value)) for name, value in self.fusion["weights"].items()}
        target = base[component] * multiplier
        other_total = Decimal("100") - base[component]
        remaining = Decimal("100") - target
        return {
            name: target if name == component else value / other_total * remaining
            for name, value in base.items()
        }

    def run_sensitivity(
        self, validation_run_id: UUID, actor_id: UUID
    ) -> list[StockIntelligenceSensitivityRun]:
        actor = CreditRagIndexService(self.s)._user(actor_id)
        validation = self._run(validation_run_id)
        history = self._history_for_run(validation, actor.id)
        grouped = self._group_dates(history)
        baseline_spearman = validation.mean_spearman
        baseline_spread = validation.mean_top_bottom_spread
        outputs: list[StockIntelligenceSensitivityRun] = []
        experiments = self.robustness["experiments"]
        assert isinstance(experiments, dict)
        for experiment_name, configuration in experiments.items():
            assert isinstance(configuration, dict)
            weights = self._perturbed_weights(
                str(configuration["component"]), Decimal(str(configuration["multiplier"]))
            )
            date_rank_correlations: list[Decimal] = []
            date_overlaps: list[Decimal] = []
            absolute_rank_changes: list[Decimal] = []
            experiment_spearman: list[Decimal] = []
            experiment_spreads: list[Decimal] = []
            for rows in grouped.values():
                scored = [(row, self._experimental_score(row, weights)) for row in rows]
                usable = [(row, score) for row, score in scored if score is not None]
                if len(usable) < int(self.policy["minimum_companies_per_date"]):
                    continue
                experiment_scores = [score for _, score in usable]
                baseline_scores = [row.score for row, _ in usable]
                rank_correlation = spearman(baseline_scores, experiment_scores)
                if rank_correlation is not None:
                    date_rank_correlations.append(rank_correlation)
                baseline_order = sorted(
                    range(len(usable)),
                    key=lambda index: (
                        -baseline_scores[index],
                        str(usable[index][0].stock_listing_id),
                    ),
                )
                experiment_order = sorted(
                    range(len(usable)),
                    key=lambda index: (
                        -experiment_scores[index],
                        str(usable[index][0].stock_listing_id),
                    ),
                )
                top_count = max(1, round(len(usable) * float(self.policy["top_k_percentage"])))
                date_overlaps.append(
                    Decimal(
                        len(set(baseline_order[:top_count]) & set(experiment_order[:top_count]))
                    )
                    / Decimal(top_count)
                )
                baseline_positions = {
                    index: position for position, index in enumerate(baseline_order, 1)
                }
                experiment_positions = {
                    index: position for position, index in enumerate(experiment_order, 1)
                }
                absolute_rank_changes.extend(
                    Decimal(abs(baseline_positions[index] - experiment_positions[index]))
                    for index in baseline_positions
                )
                score_map = {row.score_run_id: score for row, score in usable}
                metrics = self._metrics(
                    [row for row, _ in usable], lambda row: score_map[row.score_run_id]
                )
                if metrics.spearman is not None:
                    experiment_spearman.append(metrics.spearman)
                if metrics.spread is not None:
                    experiment_spreads.append(metrics.spread)
            mean_experiment_spearman = mean(experiment_spearman)
            mean_experiment_spread = mean(experiment_spreads)
            result = StockIntelligenceSensitivityRun(
                validation_run_id=validation.id,
                experiment_name=str(experiment_name),
                robustness_policy_version=str(self.robustness["version"]),
                weights_json={name: float(value) for name, value in weights.items()},
                baseline_rank_correlation=mean(date_rank_correlations),
                top_k_overlap=mean(date_overlaps),
                mean_absolute_rank_change=mean(absolute_rank_changes),
                spearman_delta=(mean_experiment_spearman - baseline_spearman)
                if mean_experiment_spearman is not None and baseline_spearman is not None
                else None,
                spread_delta=(mean_experiment_spread - baseline_spread)
                if mean_experiment_spread is not None and baseline_spread is not None
                else None,
                created_at=now(),
            )
            existing = self.s.scalar(
                select(StockIntelligenceSensitivityRun).where(
                    StockIntelligenceSensitivityRun.validation_run_id == validation.id,
                    StockIntelligenceSensitivityRun.experiment_name == experiment_name,
                )
            )
            if existing:
                outputs.append(existing)
            else:
                self.s.add(result)
                outputs.append(result)
        write_audit_log(
            self.s,
            entity_type="stock_intelligence_validation_run",
            entity_id=validation.id,
            action="STOCK_INTELLIGENCE_SENSITIVITY_BUILT",
            event_type="STOCK_INTELLIGENCE_SENSITIVITY_BUILT",
            user_id=actor.id,
            metadata_json={"experiment_count": len(outputs)},
        )
        return outputs

    def validate_lineage(self, run_id: UUID) -> bool:
        run = self.s.get(StockIntelligenceValidationRun, run_id)
        if run is None:
            return False
        periods = list(
            self.s.scalars(
                select(StockIntelligenceValidationPeriod).where(
                    StockIntelligenceValidationPeriod.validation_run_id == run.id
                )
            )
        )
        for period in periods:
            ranking = self.s.get(StockRankingRun, period.ranking_run_id)
            if ranking is None or ranking.as_of_date != period.as_of_date:
                return False
        return True
