from __future__ import annotations

# ruff: noqa: E501, E701, E702
import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.repositories.audit_log import write_audit_log
from app.models.credit import CreditAssessment
from app.models.decision import (
    CreditDecisionGate,
    CreditDecisionReviewItem,
    CreditDecisionSupport,
    CreditLimitMethod,
    CreditLimitPreparation,
    CreditPolicyException,
)
from app.models.document import Document
from app.models.enums import FinancialScope
from app.models.financial_analysis import NormalizedFinancialValue
from app.models.five_cs import FiveCsAssessment, FiveCsSection
from app.models.recommendation import (
    CreditRecommendationFactor,
    CreditRecommendationPreparation,
    CreditRecommendationReviewItem,
)
from app.models.research import ResearchRun
from app.services.credit_decision.policy import (
    ENGINE_VERSION,
    LIMIT_POLICY_VERSION,
    POLICY_VERSION,
    SUMMARY_VERSION,
    decision_policy,
    limit_policy,
    number,
    system_recommendation,
)

WARNING = "A qualified credit reviewer must make and record the final lending decision. This system output is decision support only."
LIMIT_WARNING = "This is an analytical exposure ceiling, not a sanctioned facility limit."


@dataclass(frozen=True)
class Gate:
    code: str
    category: str
    status: str
    severity: str
    blocking: bool
    exception_eligible: bool
    message: str
    confidence: float
    source_type: str | None
    source_id: UUID | None


@dataclass(frozen=True)
class LimitResult:
    code: str
    status: str
    amount: Decimal | None
    confidence: float
    version: str
    inputs: dict[str, object]


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


class CreditDecisionSupportService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def prepare(
        self,
        document_id: UUID,
        *,
        scope: FinancialScope | None = None,
        recommendation_preparation_id: UUID | None = None,
    ) -> dict[str, object]:
        document = self.session.get(Document, document_id)
        if document is None:
            raise ValueError("DOCUMENT_NOT_FOUND")
        recommendation = self._recommendation(document_id, scope, recommendation_preparation_id)
        credit = self.session.get(CreditAssessment, recommendation.credit_assessment_id)
        five_cs = self.session.get(FiveCsAssessment, recommendation.five_cs_assessment_id)
        research = (
            self.session.get(ResearchRun, recommendation.research_run_id)
            if recommendation.research_run_id
            else None
        )
        if credit is None or five_cs is None:
            raise ValueError("DECISION_SOURCE_NOT_FOUND")
        factors = list(
            self.session.scalars(
                select(CreditRecommendationFactor).where(
                    CreditRecommendationFactor.recommendation_preparation_id == recommendation.id
                )
            )
        )
        reviews = list(
            self.session.scalars(
                select(CreditRecommendationReviewItem).where(
                    CreditRecommendationReviewItem.recommendation_preparation_id
                    == recommendation.id,
                    CreditRecommendationReviewItem.resolved.is_(False),
                )
            )
        )
        values = self._financial_values(credit)
        input_hash = _digest(
            {
                "recommendation": [str(recommendation.id), recommendation.input_hash],
                "credit": [str(credit.id), credit.input_hash],
                "five_cs": [str(five_cs.id), five_cs.input_hash],
                "research": [str(research.id), research.input_hash] if research else None,
                "financial_values": [
                    (
                        str(v.id),
                        v.canonical_name,
                        str(v.normalized_value),
                        v.currency,
                        v.normalization_status.value,
                    )
                    for v in values
                ],
                "decision_policy": decision_policy(),
                "limit_policy": limit_policy(),
                "scope": five_cs.statement_scope.value,
            }
        )
        existing = self.session.scalar(
            select(CreditDecisionSupport).where(
                CreditDecisionSupport.document_id == document_id,
                CreditDecisionSupport.statement_scope == five_cs.statement_scope,
                CreditDecisionSupport.recommendation_preparation_id == recommendation.id,
                CreditDecisionSupport.input_hash == input_hash,
                CreditDecisionSupport.policy_version == POLICY_VERSION,
                CreditDecisionSupport.engine_version == ENGINE_VERSION,
            )
        )
        if existing:
            return decision_payload(self.session, existing, idempotent=True)
        self._audit(
            document,
            credit.analysis_job_id,
            "CREDIT_DECISION_SUPPORT_STARTED",
            {"recommendation_preparation_id": str(recommendation.id)},
        )
        gates = self._gates(credit, five_cs, recommendation, research, factors)
        exceptions = self._exceptions(gates)
        critical_codes = {f.factor_code for f in factors if f.category == "CRITICAL_RISK"}
        insufficient = any(g.blocking and g.status == "INSUFFICIENT_DATA" for g in gates)
        combinations = cast(list[list[str]], decision_policy()["critical_adverse_combinations"])
        adverse = any(set(combo).issubset(critical_codes) for combo in combinations) or bool(
            critical_codes & set(cast(list[str], decision_policy()["adverse_single_codes"]))
        )
        manual = any(
            g.status in {"CONFLICTING", "FAIL_REVIEW"} and not g.exception_eligible for g in gates
        )
        conditional = bool(reviews) or any(g.status == "PASS_WITH_REVIEW" for g in gates)
        recommendation_state = system_recommendation(
            insufficient=insufficient,
            exceptions=len(exceptions),
            adverse=adverse,
            manual=manual,
            conditional=conditional,
        )
        confidence = self._confidence(credit, five_cs, recommendation, research, gates)
        completeness = round(
            (
                float(credit.component_coverage)
                + five_cs.overall_completeness
                + recommendation.overall_completeness
            )
            / 3,
            4,
        )
        row = CreditDecisionSupport(
            analysis_job_id=credit.analysis_job_id,
            company_id=document.company_id,
            document_id=document_id,
            credit_assessment_id=credit.id,
            five_cs_assessment_id=five_cs.id,
            recommendation_preparation_id=recommendation.id,
            research_run_id=recommendation.research_run_id,
            fusion_experiment_id=recommendation.fusion_experiment_id,
            statement_scope=five_cs.statement_scope,
            system_recommendation=recommendation_state,
            confidence_score=confidence,
            completeness_score=completeness,
            blocking_gate_count=sum(g.blocking for g in gates),
            review_gate_count=sum(g.status != "PASS" for g in gates),
            exception_count=len(exceptions),
            production_ml_used=False,
            policy_version=POLICY_VERSION,
            engine_version=ENGINE_VERSION,
            summary_version=SUMMARY_VERSION,
            input_hash=input_hash,
            summary_text=self._summary(recommendation_state, gates, exceptions),
            human_decision=None,
        )
        self.session.add(row)
        self.session.flush()
        for gate in gates:
            self.session.add(
                CreditDecisionGate(
                    credit_decision_support_id=row.id,
                    gate_code=gate.code,
                    category=gate.category,
                    status=gate.status,
                    severity=gate.severity,
                    blocking=gate.blocking,
                    exception_eligible=gate.exception_eligible,
                    message=gate.message,
                    confidence_score=gate.confidence,
                    source_type=gate.source_type,
                    source_reference_id=gate.source_id,
                )
            )
            self._audit(
                document,
                credit.analysis_job_id,
                "CREDIT_DECISION_GATE_EVALUATED",
                {"decision_support_id": str(row.id), "gate_code": gate.code, "status": gate.status},
            )
        for code, reason, authority, source_type, source_id in exceptions:
            self.session.add(
                CreditPolicyException(
                    credit_decision_support_id=row.id,
                    exception_code=code,
                    reason=reason,
                    required_authority=authority,
                    status="OPEN",
                    resolved=False,
                    source_type=source_type,
                    source_reference_id=source_id,
                )
            )
            self._audit(
                document,
                credit.analysis_job_id,
                "CREDIT_POLICY_EXCEPTION_CREATED",
                {"decision_support_id": str(row.id), "exception_code": code},
            )
        self._review_items(row, reviews, gates)
        self._limit(row, credit, values, gates)
        self.session.flush()
        self._audit(
            document,
            credit.analysis_job_id,
            "CREDIT_DECISION_SUPPORT_COMPLETED",
            {
                "decision_support_id": str(row.id),
                "system_recommendation": recommendation_state,
                "human_decision": None,
            },
        )
        return decision_payload(self.session, row)

    def _recommendation(
        self, document_id: UUID, scope: FinancialScope | None, row_id: UUID | None
    ) -> CreditRecommendationPreparation:
        if row_id:
            row = self.session.get(CreditRecommendationPreparation, row_id)
            if row is None or row.document_id != document_id:
                raise ValueError("RECOMMENDATION_PREPARATION_NOT_FOUND")
            return row
        query = select(CreditRecommendationPreparation).where(
            CreditRecommendationPreparation.document_id == document_id
        )
        if scope:
            query = query.join(
                FiveCsAssessment,
                FiveCsAssessment.id == CreditRecommendationPreparation.five_cs_assessment_id,
            ).where(FiveCsAssessment.statement_scope == scope)
        row = self.session.scalar(
            query.order_by(
                CreditRecommendationPreparation.created_at.desc(),
                CreditRecommendationPreparation.id.desc(),
            )
        )
        if row is None:
            raise ValueError("RECOMMENDATION_PREPARATION_NOT_FOUND")
        return row

    def _financial_values(self, credit: CreditAssessment) -> list[NormalizedFinancialValue]:
        return list(
            self.session.scalars(
                select(NormalizedFinancialValue).where(
                    NormalizedFinancialValue.run_id == credit.financial_analysis_run_id,
                    NormalizedFinancialValue.statement_scope == credit.statement_scope,
                )
            )
        )

    def _gates(
        self,
        credit: CreditAssessment,
        five_cs: FiveCsAssessment,
        recommendation: CreditRecommendationPreparation,
        research: ResearchRun | None,
        factors: list[CreditRecommendationFactor],
    ) -> list[Gate]:
        sections = {
            s.section: s
            for s in self.session.scalars(
                select(FiveCsSection).where(FiveCsSection.five_cs_assessment_id == five_cs.id)
            )
        }
        p = decision_policy()
        critical = {f.factor_code for f in factors if f.category == "CRITICAL_RISK"}
        financial_ok = float(credit.component_coverage) >= number(
            p, "minimum_financial_coverage"
        ) and credit.status.value in {"VERIFIED", "NEEDS_REVIEW"}
        gates = [
            Gate(
                "FINANCIAL_COVERAGE",
                "FINANCIAL",
                "PASS" if financial_ok else "INSUFFICIENT_DATA",
                "INFO" if financial_ok else "CRITICAL",
                not financial_ok,
                False,
                f"Day 10 coverage is {float(credit.component_coverage):.0%} with status {credit.status.value}.",
                float(credit.confidence_score),
                "CREDIT_ASSESSMENT",
                credit.id,
            )
        ]
        for name, category, minimum_key in (
            ("CAPACITY", "REPAYMENT_CAPACITY", "capacity_minimum"),
            ("CAPITAL", "CAPITAL", "capital_minimum"),
        ):
            section = sections.get(name)
            adequate = bool(
                section
                and section.completeness_score >= number(p, minimum_key)
                and section.status != "CONFLICTING"
            )
            gates.append(
                Gate(
                    f"{name}_EVIDENCE",
                    category,
                    "PASS"
                    if adequate and section and section.status == "VERIFIED"
                    else "PASS_WITH_REVIEW"
                    if adequate
                    else "INSUFFICIENT_DATA",
                    "INFO" if adequate else "HIGH",
                    not adequate,
                    False,
                    f"{name.title()} evidence coverage and status require {'no additional policy gate' if adequate else 'human review'}.",
                    section.confidence_score if section else 0.0,
                    "FIVE_CS_SECTION",
                    section.id if section else five_cs.id,
                )
            )
        collateral = sections.get("COLLATERAL")
        collateral_ok = bool(
            collateral and collateral.status == "VERIFIED" and collateral.completeness_score >= 0.8
        )
        gates.append(
            Gate(
                "COLLATERAL_INFORMATION_INCOMPLETE",
                "COLLATERAL",
                "PASS" if collateral_ok else "INSUFFICIENT_DATA",
                "INFO" if collateral_ok else "MEDIUM",
                False,
                not collateral_ok,
                "Collateral evidence is verified."
                if collateral_ok
                else "Collateral valuation or coverage evidence is incomplete; PPE book value was not used.",
                collateral.confidence_score if collateral else 0.0,
                "FIVE_CS_SECTION",
                collateral.id if collateral else five_cs.id,
            )
        )
        for name, category in (("CHARACTER", "CHARACTER_RESEARCH"), ("CONDITIONS", "CONDITIONS")):
            section = sections.get(name)
            status = (
                "CONFLICTING"
                if section and section.status == "CONFLICTING"
                else "PASS_WITH_REVIEW"
                if section and section.status != "VERIFIED"
                else "PASS"
            )
            gates.append(
                Gate(
                    f"{name}_EVIDENCE",
                    category,
                    status,
                    "HIGH" if status == "CONFLICTING" else "MEDIUM" if status != "PASS" else "INFO",
                    status == "CONFLICTING",
                    False,
                    f"{name.title()} status is {section.status if section else 'UNAVAILABLE'}.",
                    section.confidence_score if section else 0.0,
                    "FIVE_CS_SECTION",
                    section.id if section else five_cs.id,
                )
            )
        legal_codes = critical & {"CRITICAL_REGULATORY_ACTION", "CRITICAL_INSOLVENCY_PROCEEDING"}
        legal_status = (
            "FAIL_REVIEW"
            if legal_codes
            else "PASS_WITH_REVIEW"
            if any("REGULATORY" in f.factor_code or "LEGAL" in f.factor_code for f in factors)
            else "PASS"
        )
        gates.append(
            Gate(
                "LEGAL_REGULATORY_REVIEW",
                "LEGAL_REGULATORY",
                legal_status,
                "CRITICAL" if legal_codes else "MEDIUM" if legal_status != "PASS" else "INFO",
                bool("CRITICAL_INSOLVENCY_PROCEEDING" in legal_codes),
                bool(legal_codes),
                "Legal and regulatory evidence retains its reported procedural status.",
                recommendation.overall_confidence,
                "CREDIT_RECOMMENDATION_PREPARATION",
                recommendation.id,
            )
        )
        data_ok = (
            five_cs.overall_completeness >= number(p, "minimum_five_cs_completeness")
            and recommendation.status != "DATA_CONFLICT_REVIEW"
        )
        gates.append(
            Gate(
                "DATA_QUALITY",
                "DATA_QUALITY",
                "PASS"
                if data_ok
                else "CONFLICTING"
                if recommendation.status == "DATA_CONFLICT_REVIEW"
                else "INSUFFICIENT_DATA",
                "INFO" if data_ok else "CRITICAL",
                not data_ok,
                not data_ok and recommendation.status != "DATA_CONFLICT_REVIEW",
                "Completeness and conflict checks use persisted Day 10 and Day 17 records.",
                recommendation.overall_confidence,
                "CREDIT_RECOMMENDATION_PREPARATION",
                recommendation.id,
            )
        )
        required = set(cast(list[str], p["research_required_scopes"]))
        research_ok = bool(
            research
            and required.issubset(set(research.scopes))
            and research.status in {"COMPLETED", "NEEDS_REVIEW"}
        )
        gates.append(
            Gate(
                "RESEARCH_COVERAGE",
                "RESEARCH_COVERAGE",
                "PASS"
                if research_ok and research and research.status == "COMPLETED"
                else "PASS_WITH_REVIEW"
                if research_ok
                else "INSUFFICIENT_DATA",
                "INFO" if research_ok else "HIGH",
                not research_ok,
                False,
                "External research coverage is explicit; no result is not treated as low risk.",
                0.85 if research_ok else 0.4,
                "RESEARCH_RUN",
                research.id if research else None,
            )
        )
        exception_rules = cast(dict[str, list[str]], p["exception_rules"])
        factor_by_code = {factor.factor_code: factor for factor in factors}
        for code in sorted(critical & set(exception_rules)):
            factor = factor_by_code[code]
            category = (
                "LEGAL_REGULATORY"
                if "REGULATORY" in code or "INSOLVENCY" in code
                else "CONDITIONS"
                if "RATING" in code
                else "FINANCIAL"
            )
            gates.append(
                Gate(
                    code,
                    category,
                    "FAIL_REVIEW",
                    "CRITICAL",
                    True,
                    True,
                    factor.description,
                    factor.confidence_score,
                    factor.source_type,
                    factor.source_reference_id,
                )
            )
        return gates

    def _exceptions(self, gates: list[Gate]) -> list[tuple[str, str, str, str | None, UUID | None]]:
        rules = cast(dict[str, list[str]], decision_policy()["exception_rules"])
        result = []
        for gate in gates:
            rule = rules.get(gate.code)
            if gate.exception_eligible and rule:
                result.append((rule[0], gate.message, rule[1], gate.source_type, gate.source_id))
        return result

    def _confidence(
        self,
        credit: CreditAssessment,
        five_cs: FiveCsAssessment,
        recommendation: CreditRecommendationPreparation,
        research: ResearchRun | None,
        gates: list[Gate],
    ) -> float:
        value = (
            float(credit.confidence_score)
            + five_cs.overall_confidence
            + recommendation.overall_confidence
            + (0.85 if research and research.status == "COMPLETED" else 0.65)
        ) / 4
        penalties = cast(dict[str, float], decision_policy()["confidence_penalties"])
        if any(g.category == "COLLATERAL" and g.status != "PASS" for g in gates):
            value -= penalties["missing_collateral"]
        if research and research.status in {"PARTIAL", "NEEDS_REVIEW"}:
            value -= penalties["partial_research"]
        if any(g.category == "LEGAL_REGULATORY" and g.status != "PASS" for g in gates):
            value -= penalties["legal_review"]
        if any(g.status == "CONFLICTING" for g in gates):
            value -= penalties["conflict"]
        return round(max(0.0, min(1.0, value)), 4)

    def _review_items(
        self,
        decision: CreditDecisionSupport,
        source_reviews: list[CreditRecommendationReviewItem],
        gates: list[Gate],
    ) -> None:
        items: dict[str, tuple[str, str, str, bool, str | None, UUID | None]] = {}
        for item in source_reviews:
            items[item.review_code] = (
                item.category,
                item.message,
                "CRITICAL" if item.blocking else "HIGH",
                item.blocking,
                "CREDIT_RECOMMENDATION_REVIEW_ITEM",
                item.id,
            )
        for gate in gates:
            if gate.status != "PASS":
                items.setdefault(
                    gate.code,
                    (
                        gate.category,
                        gate.message,
                        gate.severity
                        if gate.severity in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
                        else "MEDIUM",
                        gate.blocking,
                        gate.source_type,
                        gate.source_id,
                    ),
                )
        for code, (category, message, priority, blocking, source_type, source_id) in items.items():
            self.session.add(
                CreditDecisionReviewItem(
                    credit_decision_support_id=decision.id,
                    review_code=code,
                    category=category,
                    message=message,
                    priority=priority,
                    blocking=blocking,
                    resolved=False,
                    source_type=source_type,
                    source_reference_id=source_id,
                )
            )
            self._audit_by_decision(
                decision, "CREDIT_DECISION_REVIEW_REQUIRED", {"review_code": code}
            )

    def _limit(
        self,
        decision: CreditDecisionSupport,
        credit: CreditAssessment,
        values: list[NormalizedFinancialValue],
        gates: list[Gate],
    ) -> None:
        index = {
            v.canonical_name: v
            for v in values
            if v.normalized_value is not None and v.normalization_status.value == "NORMALIZED"
        }
        currencies = {v.currency for v in index.values() if v.currency}
        currency = next(iter(currencies), "INR")
        conflict = any(g.status == "CONFLICTING" for g in gates)
        mismatch = len(currencies) > 1
        p = limit_policy()

        def val(*names: str) -> tuple[Decimal | None, UUID | None]:
            for name in names:
                if name in index:
                    value = index[name].normalized_value
                    if value is not None:
                        return Decimal(value), index[name].id
            return None, None

        revenue, revenue_id = val("revenue", "revenue_from_operations")
        ebitda, ebitda_id = val("ebitda")
        ocf, ocf_id = val("cash_flow_from_operations", "operating_cash_flow")
        debt, debt_id = val("total_debt", "borrowings")
        equity, equity_id = val("total_equity", "equity")
        current_assets, ca_id = val("current_assets")
        current_liabilities, cl_id = val("current_liabilities")
        collateral, collateral_id = val("verified_collateral_value")
        methods: list[LimitResult] = []

        def method(
            code: str,
            amount: Decimal | None,
            confidence: float,
            config: str,
            inputs: dict[str, object],
            blocked: bool = False,
        ) -> None:
            cfg = cast(dict[str, object], p[config])
            status = (
                "BLOCKED"
                if blocked
                else "AVAILABLE"
                if amount is not None and amount >= 0
                else "UNAVAILABLE"
            )
            methods.append(
                LimitResult(
                    code,
                    status,
                    amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if amount is not None and amount >= 0 and not blocked
                    else None,
                    confidence if status == "AVAILABLE" else 0.0,
                    str(cfg["formula_version"]),
                    inputs,
                )
            )

        cash_cfg = cast(dict[str, object], p["cash_flow_capacity"])
        method(
            "CASH_FLOW_CAPACITY",
            ocf * Decimal(str(cash_cfg["multiplier"])) if ocf and ocf > 0 else None,
            0.8,
            "cash_flow_capacity",
            {
                "operating_cash_flow": str(ocf) if ocf is not None else None,
                "source_id": str(ocf_id) if ocf_id else None,
            },
            conflict or mismatch,
        )
        rev_cfg = cast(dict[str, object], p["revenue_cap"])
        method(
            "REVENUE_CAP",
            revenue * Decimal(str(rev_cfg["fraction"])) if revenue and revenue > 0 else None,
            0.82,
            "revenue_cap",
            {
                "revenue": str(revenue) if revenue is not None else None,
                "source_id": str(revenue_id) if revenue_id else None,
            },
            conflict or mismatch,
        )
        lev_cfg = cast(dict[str, object], p["leverage_cap"])
        leverage_amount = (
            max(Decimal(0), equity * Decimal(str(lev_cfg["maximum_debt_to_equity"])) - debt)
            if equity and equity > 0 and debt is not None
            else None
        )
        method(
            "LEVERAGE_CAP",
            leverage_amount,
            0.85,
            "leverage_cap",
            {
                "equity": str(equity) if equity is not None else None,
                "existing_debt": str(debt) if debt is not None else None,
                "equity_source_id": str(equity_id) if equity_id else None,
                "debt_source_id": str(debt_id) if debt_id else None,
            },
            conflict or mismatch or bool(equity is not None and equity <= 0),
        )
        wc_cfg = cast(dict[str, object], p["working_capital_need"])
        gap = (
            current_assets - current_liabilities
            if current_assets is not None and current_liabilities is not None
            else None
        )
        method(
            "WORKING_CAPITAL_NEED",
            gap * Decimal(str(wc_cfg["eligible_fraction"])) if gap and gap > 0 else None,
            0.75,
            "working_capital_need",
            {
                "current_assets": str(current_assets) if current_assets is not None else None,
                "current_liabilities": str(current_liabilities)
                if current_liabilities is not None
                else None,
                "source_ids": [str(x) for x in (ca_id, cl_id) if x],
            },
            conflict or mismatch,
        )
        col_cfg = cast(dict[str, object], p["collateral_cap"])
        method(
            "COLLATERAL_CAP",
            collateral * Decimal(str(col_cfg["advance_rate"]))
            if collateral and collateral > 0
            else None,
            0.8,
            "collateral_cap",
            {
                "verified_collateral_value": str(collateral) if collateral is not None else None,
                "source_id": str(collateral_id) if collateral_id else None,
            },
            conflict or mismatch,
        )
        available = [m for m in methods if m.status == "AVAILABLE" and m.amount is not None]
        amounts = [cast(Decimal, m.amount) for m in available]
        ceiling = min(amounts, default=None)
        lower = ceiling * Decimal(str(p["lower_bound_factor"])) if ceiling is not None else None
        status = (
            "UNAVAILABLE"
            if not available
            else "AVAILABLE"
            if len(available) >= 2 and debt is not None
            else "PARTIAL"
        )
        confidence = round(
            min((m.confidence for m in available), default=0.0) * (0.9 if debt is None else 1.0), 4
        )
        projected = {
            "debt_to_equity": str((debt + ceiling) / equity)
            if debt is not None and ceiling is not None and equity and equity > 0
            else None,
            "debt_to_ebitda": str((debt + ceiling) / ebitda)
            if debt is not None and ceiling is not None and ebitda and ebitda > 0
            else None,
            "projected_interest_coverage": None,
            "interest_rate_assumed": False,
        }
        self.session.add(
            CreditLimitPreparation(
                credit_decision_support_id=decision.id,
                currency=currency,
                lower_bound=lower,
                upper_bound=ceiling,
                analytical_ceiling=ceiling,
                status=status,
                confidence_score=confidence,
                policy_version=LIMIT_POLICY_VERSION,
                method_count=len(available),
                existing_exposure_status="AVAILABLE"
                if debt is not None
                else "EXISTING_EXPOSURE_INCOMPLETE",
                projected_ratios_json=projected,
            )
        )
        for item in methods:
            self.session.add(
                CreditLimitMethod(
                    credit_decision_support_id=decision.id,
                    method_code=item.code,
                    status=item.status,
                    calculated_limit=item.amount,
                    confidence_score=item.confidence,
                    formula_version=item.version,
                    input_summary_json=item.inputs,
                )
            )
        self._audit_by_decision(
            decision,
            "CREDIT_LIMIT_PREPARATION_CREATED",
            {
                "status": status,
                "method_count": len(available),
                "policy_version": LIMIT_POLICY_VERSION,
            },
        )

    @staticmethod
    def _summary(
        state: str,
        gates: list[Gate],
        exceptions: list[tuple[str, str, str, str | None, UUID | None]],
    ) -> str:
        return f"The system recommends {state}. {sum(g.status == 'PASS' for g in gates)} policy gate(s) passed, {sum(g.status != 'PASS' for g in gates)} require review, and {len(exceptions)} exception(s) are open. No final approval, rejection, sanction, or pricing decision has been issued."

    def _audit(
        self, document: Document, job_id: UUID, event: str, metadata: dict[str, object]
    ) -> None:
        write_audit_log(
            self.session,
            entity_type="credit_decision_support",
            entity_id=document.id,
            action=event,
            event_type=event,
            company_id=document.company_id,
            analysis_job_id=job_id,
            metadata_json=metadata,
        )

    def _audit_by_decision(
        self, decision: CreditDecisionSupport, event: str, metadata: dict[str, object]
    ) -> None:
        write_audit_log(
            self.session,
            entity_type="credit_decision_support",
            entity_id=decision.id,
            action=event,
            event_type=event,
            company_id=decision.company_id,
            analysis_job_id=decision.analysis_job_id,
            metadata_json=metadata,
        )


def decision_payload(
    session: Session, row: CreditDecisionSupport, *, idempotent: bool = False
) -> dict[str, object]:
    gates = list(
        session.scalars(
            select(CreditDecisionGate)
            .where(CreditDecisionGate.credit_decision_support_id == row.id)
            .order_by(CreditDecisionGate.created_at)
        )
    )
    exceptions = list(
        session.scalars(
            select(CreditPolicyException)
            .where(CreditPolicyException.credit_decision_support_id == row.id)
            .order_by(CreditPolicyException.created_at)
        )
    )
    reviews = list(
        session.scalars(
            select(CreditDecisionReviewItem)
            .where(CreditDecisionReviewItem.credit_decision_support_id == row.id)
            .order_by(CreditDecisionReviewItem.blocking.desc(), CreditDecisionReviewItem.created_at)
        )
    )
    limit = session.scalar(
        select(CreditLimitPreparation).where(
            CreditLimitPreparation.credit_decision_support_id == row.id
        )
    )
    methods = list(
        session.scalars(
            select(CreditLimitMethod)
            .where(CreditLimitMethod.credit_decision_support_id == row.id)
            .order_by(CreditLimitMethod.method_code)
        )
    )
    return {
        "decision_support_id": row.id,
        "document_id": row.document_id,
        "scope": row.statement_scope.value,
        "system_recommendation": row.system_recommendation,
        "human_decision": row.human_decision,
        "human_decision_status": "NOT_RECORDED"
        if row.human_decision is None
        else row.human_decision,
        "confidence": row.confidence_score,
        "completeness": row.completeness_score,
        "blocking_gate_count": row.blocking_gate_count,
        "review_gate_count": row.review_gate_count,
        "exception_count": row.exception_count,
        "production_ml_used": row.production_ml_used,
        "experimental_ml_decision_weight": 0,
        "policy_version": row.policy_version,
        "engine_version": row.engine_version,
        "summary_version": row.summary_version,
        "summary": row.summary_text,
        "lineage": {
            "recommendation_preparation_id": row.recommendation_preparation_id,
            "five_cs_assessment_id": row.five_cs_assessment_id,
            "credit_assessment_id": row.credit_assessment_id,
            "research_run_id": row.research_run_id,
            "fusion_experiment_id": row.fusion_experiment_id,
        },
        "gates": [gate_payload(x) for x in gates],
        "exceptions": [exception_payload(x) for x in exceptions],
        "review_items": [review_payload(x) for x in reviews],
        "limit_preparation": limit_payload(limit, methods) if limit else None,
        "warning": WARNING,
        "final_lending_decision": None,
        "sanctioned_limit": None,
        "pricing": None,
        "idempotent": idempotent,
    }


def gate_payload(x: CreditDecisionGate) -> dict[str, object]:
    return {
        "gate_id": x.id,
        "gate_code": x.gate_code,
        "category": x.category,
        "status": x.status,
        "severity": x.severity,
        "blocking": x.blocking,
        "exception_eligible": x.exception_eligible,
        "message": x.message,
        "confidence": x.confidence_score,
        "source_type": x.source_type,
        "source_reference_id": x.source_reference_id,
    }


def exception_payload(x: CreditPolicyException) -> dict[str, object]:
    return {
        "exception_id": x.id,
        "exception_code": x.exception_code,
        "reason": x.reason,
        "required_authority": x.required_authority,
        "status": x.status,
        "resolved": x.resolved,
        "source_type": x.source_type,
        "source_reference_id": x.source_reference_id,
    }


def review_payload(x: CreditDecisionReviewItem) -> dict[str, object]:
    return {
        "review_item_id": x.id,
        "review_code": x.review_code,
        "category": x.category,
        "message": x.message,
        "priority": x.priority,
        "blocking": x.blocking,
        "resolved": x.resolved,
        "source_type": x.source_type,
        "source_reference_id": x.source_reference_id,
    }


def limit_payload(
    row: CreditLimitPreparation, methods: list[CreditLimitMethod]
) -> dict[str, object]:
    return {
        "limit_preparation_id": row.id,
        "currency": row.currency,
        "lower_bound": row.lower_bound,
        "upper_bound": row.upper_bound,
        "analytical_ceiling": row.analytical_ceiling,
        "status": row.status,
        "confidence": row.confidence_score,
        "policy_version": row.policy_version,
        "method_count": row.method_count,
        "existing_exposure_status": row.existing_exposure_status,
        "projected_ratios": row.projected_ratios_json,
        "methods": [
            {
                "method_id": x.id,
                "method_code": x.method_code,
                "status": x.status,
                "calculated_limit": x.calculated_limit,
                "confidence": x.confidence_score,
                "formula_version": x.formula_version,
                "inputs": x.input_summary_json,
            }
            for x in methods
        ],
        "warning": LIMIT_WARNING,
        "sanctioned": False,
    }
