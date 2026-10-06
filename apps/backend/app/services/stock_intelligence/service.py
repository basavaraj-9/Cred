from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.stock import ListedCompany, StockListing, StockPrice
from app.models.stock_analytics import (
    SectorMetric,
    SectorMetricRun,
    StockFeature,
    StockFeatureInput,
    StockFeatureRun,
    StockFundamental,
)
from app.models.stock_intelligence import (
    StockIntelligenceComponent,
    StockIntelligenceComponentInput,
    StockIntelligenceRun,
    StockRankingMember,
    StockRankingRun,
)
from app.models.stock_ml import (
    StockMLDataset,
    StockMLDatasetRow,
    StockMLModel,
    StockMLPrediction,
    StockMLRun,
)
from app.services.stock.authorization import require_stock_actor

SCORE_VERSION = "stock_intelligence_score_v1"
COMPONENT_NAMES = (
    "ML_SIGNAL",
    "VALUATION",
    "FUNDAMENTAL_QUALITY",
    "GROWTH",
    "PROFITABILITY",
    "BALANCE_SHEET",
    "MOMENTUM",
    "RISK",
    "PEER_RELATIVE",
    "SECTOR_RELATIVE",
    "DATA_QUALITY",
)


def now() -> datetime:
    return datetime.now(UTC)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def clamp(value: Decimal, low: Decimal = Decimal("0"), high: Decimal = Decimal("100")) -> Decimal:
    return min(high, max(low, value))


@dataclass(frozen=True)
class InputRef:
    source_type: str
    source_id: UUID
    name: str
    value: Decimal | None
    status: str


@dataclass(frozen=True)
class ComponentResult:
    name: str
    score: Decimal | None
    weight: Decimal
    confidence: Decimal
    status: str
    inputs: tuple[InputRef, ...]
    explanation: str


class StockIntelligenceService:
    def __init__(self, session: Session):
        self.s = session
        directory = Path(__file__).parent
        self.fusion = json.loads(
            (directory / "stock_intelligence_fusion_policy_v1.json").read_text()
        )
        self.normalization = json.loads(
            (directory / "stock_component_normalization_policy_v1.json").read_text()
        )
        self.ranking = json.loads((directory / "stock_ranking_policy_v1.json").read_text())
        self.watchlist = json.loads((directory / "stock_watchlist_policy_v1.json").read_text())
        total = sum(Decimal(str(value)) for value in self.fusion["weights"].values())
        if total != Decimal("100") or tuple(self.fusion["weights"]) != COMPONENT_NAMES:
            raise AppError(
                "STOCK_INTELLIGENCE_POLICY_INVALID",
                "Stock intelligence component weights must define the ordered components "
                "and sum to 100",
                500,
            )

    def _weight(self, name: str) -> Decimal:
        return Decimal(str(self.fusion["weights"][name]))

    def _linear(self, name: str, value: Decimal) -> Decimal:
        direction, minimum, maximum = self.normalization["features"][name]
        low, high = Decimal(str(minimum)), Decimal(str(maximum))
        bounded = min(high, max(low, value))
        score = (bounded - low) / (high - low) * Decimal("100")
        return clamp(Decimal("100") - score if direction == "LOWER" else score)

    def _feature_context(
        self, listing_id: UUID, as_of: date
    ) -> tuple[StockFeatureRun | None, dict[str, StockFeature]]:
        run = self.s.scalar(
            select(StockFeatureRun)
            .where(
                StockFeatureRun.stock_listing_id == listing_id,
                StockFeatureRun.as_of_date == as_of,
                StockFeatureRun.status == "COMPLETED",
            )
            .order_by(desc(StockFeatureRun.created_at))
            .limit(1)
        )
        if run is None:
            return None, {}
        return run, {
            feature.feature_name: feature
            for feature in self.s.scalars(
                select(StockFeature).where(StockFeature.feature_run_id == run.id)
            )
            if self._feature_sources_eligible(feature, as_of)
        }

    def _feature_sources_eligible(self, feature: StockFeature, as_of: date) -> bool:
        for source in self.s.scalars(
            select(StockFeatureInput).where(StockFeatureInput.stock_feature_id == feature.id)
        ):
            if source.source_type == "PRICE":
                price = self.s.get(StockPrice, source.source_reference_id)
                if price is None or price.trade_date > as_of:
                    return False
            elif source.source_type == "FUNDAMENTAL":
                fundamental = self.s.get(StockFundamental, source.source_reference_id)
                if (
                    fundamental is None
                    or fundamental.availability_date is None
                    or fundamental.availability_date > as_of
                ):
                    return False
            elif source.source_type == "RELATIVE_METRIC":
                metric = self.s.get(SectorMetric, source.source_reference_id)
                metric_run = (
                    self.s.get(SectorMetricRun, metric.sector_metric_run_id) if metric else None
                )
                if metric_run is None or metric_run.as_of_date > as_of:
                    return False
        return True

    def _available_features(
        self, features: dict[str, StockFeature], names: list[str]
    ) -> list[StockFeature]:
        return [
            features[name]
            for name in names
            if name in features
            and features[name].status == "AVAILABLE"
            and features[name].value is not None
        ]

    def _feature_refs(self, features: list[StockFeature]) -> tuple[InputRef, ...]:
        refs: list[InputRef] = []
        for feature in features:
            refs.append(
                InputRef(
                    "STOCK_FEATURE",
                    feature.id,
                    feature.feature_name,
                    feature.value,
                    feature.status,
                )
            )
            refs.extend(
                InputRef(
                    source.source_type,
                    source.source_reference_id,
                    feature.feature_name,
                    source.input_value,
                    feature.status,
                )
                for source in self.s.scalars(
                    select(StockFeatureInput).where(
                        StockFeatureInput.stock_feature_id == feature.id
                    )
                )
            )
        return tuple(refs)

    def _feature_component(
        self,
        component: str,
        features: dict[str, StockFeature],
        names: list[str],
        explanation: str,
        custom_scores: dict[str, Decimal] | None = None,
    ) -> ComponentResult:
        available = self._available_features(features, names)
        inputs = self._feature_refs(available)
        scores = [
            custom_scores[item.feature_name]
            if custom_scores is not None and item.feature_name in custom_scores
            else self._linear(item.feature_name, item.value)
            for item in available
            if item.value is not None
        ]
        if not scores:
            return ComponentResult(
                component,
                None,
                self._weight(component),
                Decimal("0"),
                "UNAVAILABLE",
                inputs,
                f"{component.replace('_', ' ').title()} is unavailable because eligible "
                "inputs are missing.",
            )
        score = sum(scores, Decimal("0")) / Decimal(len(scores))
        completeness = Decimal(len(scores)) / Decimal(len(names))
        return ComponentResult(
            component,
            clamp(score),
            self._weight(component),
            min(Decimal("1"), completeness),
            "AVAILABLE" if len(scores) == len(names) else "PARTIAL",
            inputs,
            explanation,
        )

    def _ml_component(self, listing_id: UUID, as_of: date) -> ComponentResult:
        row = self.s.execute(
            select(StockMLPrediction, StockMLModel, StockMLRun, StockMLDataset)
            .join(StockMLModel, StockMLModel.ml_run_id == StockMLPrediction.ml_run_id)
            .join(StockMLRun, StockMLRun.id == StockMLPrediction.ml_run_id)
            .join(StockMLDatasetRow, StockMLDatasetRow.id == StockMLPrediction.dataset_row_id)
            .join(StockMLDataset, StockMLDataset.id == StockMLRun.dataset_id)
            .where(
                StockMLDatasetRow.stock_listing_id == listing_id,
                StockMLDatasetRow.as_of_date == as_of,
                StockMLModel.selected_for_research.is_(True),
                StockMLModel.lifecycle.in_(self.fusion["ml_allowed_lifecycles"]),
                StockMLPrediction.prediction_probability.is_not(None),
                StockMLModel.feature_schema_hash == StockMLDataset.feature_schema_hash,
            )
            .order_by(desc(StockMLModel.created_at))
            .limit(1)
        ).first()
        if row is None:
            return ComponentResult(
                "ML_SIGNAL",
                None,
                self._weight("ML_SIGNAL"),
                Decimal("0"),
                "UNAVAILABLE",
                (),
                "No eligible same-date research prediction is available.",
            )
        prediction, model, run, dataset = row
        dataset_row = self.s.get(StockMLDatasetRow, prediction.dataset_row_id)
        feature_run = (
            self.s.get(StockFeatureRun, dataset_row.feature_run_id) if dataset_row else None
        )
        if feature_run is None or feature_run.as_of_date != as_of:
            return ComponentResult(
                "ML_SIGNAL",
                None,
                self._weight("ML_SIGNAL"),
                Decimal("0"),
                "UNAVAILABLE",
                (),
                "The research prediction does not have valid same-date feature lineage.",
            )
        probability = prediction.prediction_probability
        if probability is None:
            raise AppError("STOCK_INTELLIGENCE_ML_INVALID", "ML probability is unavailable", 422)
        confidence = Decimal(str(self.fusion["ml_confidence_caps"].get(model.lifecycle, 0)))
        refs = (
            InputRef(
                "STOCK_ML_PREDICTION",
                prediction.id,
                "outperformance_probability",
                probability,
                "AVAILABLE",
            ),
            InputRef("STOCK_ML_MODEL", model.id, model.model_version, None, model.lifecycle),
            InputRef("STOCK_ML_RUN", run.id, run.model_name, None, run.status),
            InputRef("STOCK_ML_DATASET", dataset.id, dataset.dataset_version, None, dataset.status),
        )
        return ComponentResult(
            "ML_SIGNAL",
            clamp(probability * Decimal("100")),
            self._weight("ML_SIGNAL"),
            confidence,
            "AVAILABLE",
            refs,
            f"The selected {model.model_version} research probability is bounded to a "
            f"0-100 signal; lifecycle confidence is capped at {confidence}.",
        )

    def _relative_component(
        self,
        component: str,
        features: dict[str, StockFeature],
        allowed_groups: tuple[str, ...],
    ) -> ComponentResult:
        directions: dict[str, str] = self.normalization["relative_directions"]
        chosen: dict[str, StockFeature] = {}
        for group in allowed_groups:
            for metric, direction in directions.items():
                name = f"{group}_{metric}_PERCENTILE"
                feature = features.get(name)
                if (
                    metric not in chosen
                    and feature
                    and feature.status == "AVAILABLE"
                    and feature.value is not None
                ):
                    chosen[metric] = feature
            if component == "VALUATION" and chosen:
                break
        scores: list[Decimal] = []
        selected_features: list[StockFeature] = []
        for metric, feature in sorted(chosen.items()):
            value = clamp(feature.value * Decimal("100")) if feature.value is not None else None
            if value is None:
                continue
            scores.append(Decimal("100") - value if directions[metric] == "LOWER" else value)
            selected_features.append(feature)
        refs = self._feature_refs(selected_features)
        if not scores:
            return ComponentResult(
                component,
                None,
                self._weight(component),
                Decimal("0"),
                "UNAVAILABLE",
                refs,
                f"{component.replace('_', ' ').title()} is unavailable because eligible "
                "relative metrics are missing.",
            )
        score = sum(scores, Decimal("0")) / Decimal(len(scores))
        confidence = Decimal(len(scores)) / Decimal(len(directions))
        return ComponentResult(
            component,
            score,
            self._weight(component),
            confidence,
            "AVAILABLE" if len(scores) == len(directions) else "PARTIAL",
            refs,
            f"{component.replace('_', ' ').title()} uses recorded relative percentiles "
            "with metric-specific direction.",
        )

    def _fundamental_quality(self, features: dict[str, StockFeature]) -> ComponentResult:
        names = ["OPERATING_CASH_FLOW", "FREE_CASH_FLOW", "REVENUE", "PAT"]
        available = self._available_features(features, names)
        custom = {
            item.feature_name: Decimal("75") if item.value and item.value > 0 else Decimal("25")
            for item in available
        }
        return self._feature_component(
            "FUNDAMENTAL_QUALITY",
            features,
            names,
            "Fundamental quality reflects positive cash generation, revenue, and earnings "
            "without using credit recommendations.",
            custom,
        )

    def _momentum(self, features: dict[str, StockFeature]) -> ComponentResult:
        return_names = ["RETURN_1M", "RETURN_3M", "RETURN_6M", "RETURN_12M"]
        trend_names = ["PRICE_TO_SMA20", "PRICE_TO_SMA50", "PRICE_TO_SMA200"]
        available = self._available_features(features, return_names + trend_names)
        refs = self._feature_refs(available)
        weights: dict[str, float] = self.normalization["momentum_weights"]
        weighted = Decimal("0")
        used = Decimal("0")
        for item in available:
            if item.value is None:
                continue
            key = item.feature_name if item.feature_name in return_names else "TREND_CONFIRMATION"
            item_weight = Decimal(str(weights[key]))
            if key == "TREND_CONFIRMATION":
                item_weight /= Decimal(len(trend_names))
            weighted += self._linear(item.feature_name, item.value) * item_weight
            used += item_weight
        if not used:
            return ComponentResult(
                "MOMENTUM",
                None,
                self._weight("MOMENTUM"),
                Decimal("0"),
                "UNAVAILABLE",
                refs,
                "Momentum inputs are unavailable.",
            )
        return ComponentResult(
            "MOMENTUM",
            clamp(weighted / used),
            self._weight("MOMENTUM"),
            min(Decimal("1"), used),
            "AVAILABLE" if used == Decimal("1") else "PARTIAL",
            refs,
            "Momentum blends 1M, 3M, 6M, 12M returns and moving-average confirmation "
            "using policy weights.",
        )

    def _data_quality(
        self, feature_run: StockFeatureRun | None, features: dict[str, StockFeature]
    ) -> ComponentResult:
        if feature_run is None or not features:
            return ComponentResult(
                "DATA_QUALITY",
                None,
                self._weight("DATA_QUALITY"),
                Decimal("0"),
                "UNAVAILABLE",
                (),
                "No same-date feature run is available.",
            )
        available = [
            item
            for item in features.values()
            if item.status == "AVAILABLE" and item.value is not None
        ]
        ratio = Decimal(len(available)) / Decimal(len(features))
        refs = self._feature_refs(sorted(features.values(), key=lambda value: value.feature_name))
        lineage_complete = sum(
            1
            for item in available
            if item.source_count == 0
            or self.s.scalar(
                select(StockFeatureInput.id)
                .where(StockFeatureInput.stock_feature_id == item.id)
                .limit(1)
            )
            is not None
        )
        lineage_ratio = (
            Decimal(lineage_complete) / Decimal(len(available)) if available else Decimal("0")
        )
        score = (ratio * Decimal("0.75") + lineage_ratio * Decimal("0.25")) * Decimal("100")
        return ComponentResult(
            "DATA_QUALITY",
            score,
            self._weight("DATA_QUALITY"),
            ratio * lineage_ratio,
            "AVAILABLE" if ratio >= Decimal("0.8") and lineage_ratio == 1 else "PARTIAL",
            refs,
            "Data quality reflects feature availability and source-lineage completeness.",
        )

    def _components(
        self, listing_id: UUID, as_of: date
    ) -> tuple[list[ComponentResult], StockFeatureRun | None]:
        feature_run, features = self._feature_context(listing_id, as_of)
        results = [
            self._ml_component(listing_id, as_of),
            self._relative_component("VALUATION", features, ("PEER_GROUP", "INDUSTRY", "SECTOR")),
            self._fundamental_quality(features),
            self._feature_component(
                "GROWTH",
                features,
                [
                    "REVENUE_YOY",
                    "EBITDA_YOY",
                    "PAT_YOY",
                    "EPS_YOY",
                    "OPERATING_CASH_FLOW_YOY",
                    "FREE_CASH_FLOW_YOY",
                ],
                "Growth uses bounded year-over-year operating, earnings, and cash-flow changes.",
            ),
            self._feature_component(
                "PROFITABILITY",
                features,
                ["ROE", "ROA", "EBITDA_MARGIN", "NET_MARGIN"],
                "Profitability uses bounded return and margin measures.",
            ),
            self._feature_component(
                "BALANCE_SHEET",
                features,
                ["DEBT_TO_EQUITY"],
                "Balance-sheet strength rewards lower leverage without importing a "
                "credit decision.",
            ),
            self._momentum(features),
            self._feature_component(
                "RISK",
                features,
                [
                    "VOLATILITY_20D",
                    "VOLATILITY_60D",
                    "VOLATILITY_252D",
                    "MAX_DRAWDOWN_3M",
                    "MAX_DRAWDOWN_6M",
                    "MAX_DRAWDOWN_12M",
                ],
                "Risk rewards lower volatility and less severe drawdowns.",
            ),
            self._relative_component("PEER_RELATIVE", features, ("PEER_GROUP",)),
            self._relative_component("SECTOR_RELATIVE", features, ("INDUSTRY", "SECTOR")),
            self._data_quality(feature_run, features),
        ]
        return results, feature_run

    def _band(self, score: Decimal | None) -> str | None:
        if score is None:
            return None
        for band in self.fusion["bands"]:
            if score >= Decimal(str(band["minimum"])):
                return str(band["name"])
        return None

    def _contradictions(self, values: dict[str, Decimal]) -> list[str]:
        flags: list[str] = []
        if (
            values.get("MOMENTUM", Decimal("50")) >= 70
            and values.get("FUNDAMENTAL_QUALITY", Decimal("50")) < 40
        ):
            flags.append("STRONG_MOMENTUM_WEAK_FUNDAMENTALS")
        if (
            values.get("VALUATION", Decimal("50")) >= 70
            and values.get("PROFITABILITY", Decimal("50")) < 40
        ):
            flags.append("CHEAP_VALUATION_WEAK_PROFITABILITY")
        if values.get("GROWTH", Decimal("50")) >= 70 and values.get("RISK", Decimal("50")) < 40:
            flags.append("HIGH_GROWTH_HIGH_RISK")
        ml, deterministic = (
            values.get("ML_SIGNAL"),
            [value for name, value in values.items() if name not in {"ML_SIGNAL", "DATA_QUALITY"}],
        )
        rule = (
            sum(deterministic, Decimal("0")) / Decimal(len(deterministic))
            if deterministic
            else None
        )
        if ml is not None and rule is not None and ml >= 70 and rule < 40:
            flags.append("STRONG_ML_WEAK_RULE_SIGNAL")
        if ml is not None and rule is not None and rule >= 70 and ml < 40:
            flags.append("STRONG_RULE_SIGNAL_WEAK_ML")
        if values.get("SECTOR_RELATIVE", Decimal("50")) >= 70 and rule is not None and rule < 40:
            flags.append("SECTOR_STRONG_COMPANY_WEAK")
        if values.get("SECTOR_RELATIVE", Decimal("50")) < 40 and rule is not None and rule >= 70:
            flags.append("COMPANY_STRONG_SECTOR_WEAK")
        return flags

    def build_score(self, listing_id: UUID, as_of: date, actor_id: UUID) -> StockIntelligenceRun:
        actor = require_stock_actor(self.s, actor_id, write=True)
        listing = self.s.get(StockListing, listing_id)
        if listing is None:
            raise AppError("STOCK_LISTING_NOT_FOUND", "Stock listing not found", 404)
        results, feature_run = self._components(listing_id, as_of)
        available = [result for result in results if result.score is not None]
        available_weight = sum((result.weight for result in available), Decimal("0"))
        coverage = available_weight / Decimal("100")
        weighted_sum = sum(
            (result.score * result.weight for result in available if result.score is not None),
            Decimal("0"),
        )
        minimum_coverage = Decimal(str(self.fusion["minimum_coverage"]))
        score = (
            clamp(weighted_sum / available_weight)
            if available_weight and coverage >= minimum_coverage
            else None
        )
        confidence = (
            sum((result.confidence * result.weight for result in available), Decimal("0"))
            / available_weight
            if available_weight
            else Decimal("0")
        )
        status = "INSUFFICIENT_DATA"
        if score is not None:
            status = (
                "AVAILABLE"
                if confidence >= Decimal(str(self.fusion["partial_confidence_threshold"]))
                else "PARTIAL"
            )
        impact_rows: list[tuple[Decimal, dict[str, object]]] = []
        for result in available:
            if result.score is None:
                continue
            impact = (result.score - Decimal("50")) * result.weight / Decimal("100")
            impact_rows.append(
                (
                    impact,
                    {
                        "component": result.name,
                        "impact": float(impact),
                        "explanation": result.explanation,
                    },
                )
            )
        positive = [
            payload
            for _, payload in sorted(
                (row for row in impact_rows if row[0] > 0),
                key=lambda row: (-abs(row[0]), str(row[1]["component"])),
            )[:3]
        ]
        negative = [
            payload
            for _, payload in sorted(
                (row for row in impact_rows if row[0] < 0),
                key=lambda row: (-abs(row[0]), str(row[1]["component"])),
            )[:3]
        ]
        values = {result.name: result.score for result in available if result.score is not None}
        contradictions = self._contradictions(values)
        missing = [result.name for result in results if result.score is None]
        dispersion = (
            Decimal(str(statistics.pstdev([float(value) for value in values.values()])))
            if len(values) > 1
            else Decimal("0")
        )
        agreement = clamp(Decimal("1") - dispersion / Decimal("50"), Decimal("0"), Decimal("1"))
        hash_payload = {
            "listing": listing.id,
            "company": listing.listed_company_id,
            "as_of": as_of,
            "feature_run": feature_run.id if feature_run else None,
            "policies": [self.fusion, self.normalization, self.ranking, self.watchlist],
            "components": [
                {
                    "name": result.name,
                    "score": result.score,
                    "confidence": result.confidence,
                    "status": result.status,
                    "inputs": [
                        (item.source_type, item.source_id, item.name, item.value, item.status)
                        for item in result.inputs
                    ],
                }
                for result in results
            ],
        }
        input_hash = digest(hash_payload)
        existing = self.s.scalar(
            select(StockIntelligenceRun).where(StockIntelligenceRun.input_hash == input_hash)
        )
        if existing:
            write_audit_log(
                self.s,
                entity_type="stock_intelligence_run",
                entity_id=existing.id,
                action="STOCK_INTELLIGENCE_SCORE_REUSED",
                event_type="STOCK_INTELLIGENCE_SCORE_REUSED",
                user_id=actor.id,
            )
            return existing
        run = StockIntelligenceRun(
            listed_company_id=listing.listed_company_id,
            stock_listing_id=listing.id,
            as_of_date=as_of,
            score_version=SCORE_VERSION,
            fusion_policy_version=self.fusion["version"],
            normalization_policy_version=self.normalization["version"],
            ranking_policy_version=self.ranking["version"],
            watchlist_policy_version=self.watchlist["version"],
            input_hash=input_hash,
            status=status,
            score=score,
            confidence=confidence,
            coverage=coverage,
            available_weight=available_weight,
            available_component_count=len(available),
            missing_component_count=len(results) - len(available),
            band=self._band(score),
            agreement_score=agreement,
            top_positive_drivers=positive,
            top_negative_drivers=negative,
            contradictions=contradictions,
            missing_evidence=missing,
            production_use_permitted=False,
            created_at=now(),
        )
        self.s.add(run)
        self.s.flush()
        for result in results:
            effective_weight = result.weight if result.score is not None else Decimal("0")
            normalized_score = (
                result.score.quantize(Decimal("0.0001")) if result.score is not None else None
            )
            component = StockIntelligenceComponent(
                run_id=run.id,
                component_name=result.name,
                raw_score=result.score,
                normalized_score=normalized_score,
                configured_weight=result.weight,
                effective_weight=effective_weight,
                contribution=(
                    normalized_score * effective_weight if normalized_score is not None else None
                ),
                confidence=result.confidence,
                status=result.status,
                explanation=result.explanation,
                created_at=now(),
            )
            self.s.add(component)
            self.s.flush()
            for item in result.inputs:
                self.s.add(
                    StockIntelligenceComponentInput(
                        component_id=component.id,
                        source_type=item.source_type,
                        source_id=item.source_id,
                        feature_name=item.name,
                        source_value=item.value,
                        source_status=item.status,
                        created_at=now(),
                    )
                )
        write_audit_log(
            self.s,
            entity_type="stock_intelligence_run",
            entity_id=run.id,
            action="STOCK_INTELLIGENCE_SCORE_BUILT",
            event_type="STOCK_INTELLIGENCE_SCORE_BUILT",
            user_id=actor.id,
            metadata_json={"status": status, "coverage": str(coverage)},
        )
        return run

    def _priority(self, score: Decimal, confidence: Decimal, coverage: Decimal) -> str:
        for name, label in (
            ("high", "RESEARCH_PRIORITY_HIGH"),
            ("medium", "RESEARCH_PRIORITY_MEDIUM"),
            ("low", "RESEARCH_PRIORITY_LOW"),
        ):
            policy = self.watchlist[name]
            if (
                score >= Decimal(str(policy.get("minimum_score", 0)))
                and confidence >= Decimal(str(policy["minimum_confidence"]))
                and coverage >= Decimal(str(policy["minimum_coverage"]))
            ):
                return label
        return "INSUFFICIENT_DATA"

    def build_ranking(
        self, as_of: date, actor_id: UUID, listing_ids: list[UUID] | None = None
    ) -> StockRankingRun:
        actor = require_stock_actor(self.s, actor_id, write=True)
        query = (
            select(StockListing)
            .join(ListedCompany)
            .where(
                StockListing.listing_status == self.ranking["listing_status"],
                StockListing.is_primary.is_(True),
            )
        )
        if listing_ids:
            query = query.where(StockListing.id.in_(listing_ids))
        listings = list(self.s.scalars(query.order_by(StockListing.id)))
        scores = [self.build_score(listing.id, as_of, actor_id) for listing in listings]
        eligible = [
            score
            for score in scores
            if score.status in self.ranking["eligible_statuses"]
            and score.score is not None
            and score.confidence >= Decimal(str(self.ranking["minimum_confidence"]))
            and score.coverage >= Decimal(str(self.ranking["minimum_coverage"]))
        ]
        companies = {
            company.id: company
            for company in self.s.scalars(
                select(ListedCompany).where(
                    ListedCompany.id.in_([item.listed_company_id for item in listings])
                )
            )
        }
        universe_hash = digest(
            [
                (listing.id, companies[listing.listed_company_id].universe_snapshot_hash)
                for listing in listings
            ]
        )
        input_hash = digest(
            {
                "as_of": as_of,
                "policy": self.ranking,
                "watchlist": self.watchlist,
                "universe": universe_hash,
                "scores": [
                    (
                        item.id,
                        item.score.quantize(Decimal("0.0001")) if item.score is not None else None,
                        item.confidence.quantize(Decimal("0.000001")),
                        item.coverage.quantize(Decimal("0.000001")),
                    )
                    for item in eligible
                ],
            }
        )
        existing = self.s.scalar(
            select(StockRankingRun).where(StockRankingRun.input_hash == input_hash)
        )
        if existing:
            write_audit_log(
                self.s,
                entity_type="stock_ranking_run",
                entity_id=existing.id,
                action="STOCK_RANKING_REUSED",
                event_type="STOCK_RANKING_REUSED",
                user_id=actor.id,
            )
            return existing
        run = StockRankingRun(
            as_of_date=as_of,
            ranking_policy_version=self.ranking["version"],
            watchlist_policy_version=self.watchlist["version"],
            universe_hash=universe_hash,
            input_hash=input_hash,
            status="AVAILABLE" if eligible else "INSUFFICIENT_DATA",
            eligible_company_count=len(eligible),
            created_at=now(),
        )
        self.s.add(run)
        self.s.flush()

        def ranking_key(item: StockIntelligenceRun) -> tuple[Decimal, Decimal, str]:
            if item.score is None:
                raise AppError("STOCK_RANKING_SCORE_INVALID", "Eligible score is missing", 500)
            return (-item.score, -item.confidence, str(item.listed_company_id))

        ordered = sorted(eligible, key=ranking_key)
        count = len(ordered)
        for index, score_run in enumerate(ordered, 1):
            if score_run.score is None:
                raise AppError("STOCK_RANKING_SCORE_INVALID", "Eligible score is missing", 500)
            percentile = (
                Decimal("100")
                if count == 1
                else Decimal(count - index) / Decimal(count - 1) * Decimal("100")
            )
            self.s.add(
                StockRankingMember(
                    ranking_run_id=run.id,
                    stock_intelligence_run_id=score_run.id,
                    listed_company_id=score_run.listed_company_id,
                    stock_listing_id=score_run.stock_listing_id,
                    score=score_run.score,
                    confidence=score_run.confidence,
                    coverage=score_run.coverage,
                    rank=index,
                    percentile=percentile,
                    rank_status="ELIGIBLE",
                    research_priority=self._priority(
                        score_run.score, score_run.confidence, score_run.coverage
                    ),
                    created_at=now(),
                )
            )
        write_audit_log(
            self.s,
            entity_type="stock_ranking_run",
            entity_id=run.id,
            action="STOCK_RANKING_BUILT",
            event_type="STOCK_RANKING_BUILT",
            user_id=actor.id,
            metadata_json={"eligible_company_count": len(eligible)},
        )
        return run

    def build_watchlist(self, ranking_run_id: UUID, actor_id: UUID) -> list[StockRankingMember]:
        actor = require_stock_actor(self.s, actor_id, write=True)
        ranking = self.s.get(StockRankingRun, ranking_run_id)
        if ranking is None:
            raise AppError("STOCK_RANKING_NOT_FOUND", "Stock ranking not found", 404)
        members = list(
            self.s.scalars(
                select(StockRankingMember)
                .where(StockRankingMember.ranking_run_id == ranking.id)
                .order_by(StockRankingMember.rank)
            )
        )
        write_audit_log(
            self.s,
            entity_type="stock_ranking_run",
            entity_id=ranking.id,
            action="WATCHLIST_GENERATED",
            event_type="WATCHLIST_GENERATED",
            user_id=actor.id,
            metadata_json={"member_count": len(members)},
        )
        return members

    def validate_lineage(self, run_id: UUID) -> bool:
        run = self.s.get(StockIntelligenceRun, run_id)
        if run is None:
            return False
        inputs = list(
            self.s.scalars(
                select(StockIntelligenceComponentInput)
                .join(StockIntelligenceComponent)
                .where(StockIntelligenceComponent.run_id == run.id)
            )
        )
        for item in inputs:
            if item.source_type == "STOCK_FEATURE":
                feature = self.s.get(StockFeature, item.source_id)
                feature_run = (
                    self.s.get(StockFeatureRun, feature.feature_run_id) if feature else None
                )
                if feature_run is None or feature_run.as_of_date > run.as_of_date:
                    return False
            elif item.source_type == "STOCK_ML_PREDICTION":
                prediction = self.s.get(StockMLPrediction, item.source_id)
                dataset_row = (
                    self.s.get(StockMLDatasetRow, prediction.dataset_row_id) if prediction else None
                )
                if dataset_row is None or dataset_row.as_of_date != run.as_of_date:
                    return False
            elif item.source_type == "FUNDAMENTAL":
                fundamental = self.s.get(StockFundamental, item.source_id)
                if (
                    fundamental is None
                    or fundamental.availability_date is None
                    or fundamental.availability_date > run.as_of_date
                ):
                    return False
            elif item.source_type == "PRICE":
                price = self.s.get(StockPrice, item.source_id)
                if price is None or price.trade_date > run.as_of_date:
                    return False
            elif item.source_type == "RELATIVE_METRIC":
                metric = self.s.get(SectorMetric, item.source_id)
                metric_run = (
                    self.s.get(SectorMetricRun, metric.sector_metric_run_id) if metric else None
                )
                if metric_run is None or metric_run.as_of_date > run.as_of_date:
                    return False
        return True
