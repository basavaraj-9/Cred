import hashlib
import logging

# ruff: noqa: E501
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.models.document import Document
from app.models.enums import (
    AnalysisStage,
    FinancialStatus,
    NormalizationStatus,
    RatioStatus,
    ValidationSeverity,
    ValidationStatus,
    ValueOrigin,
)
from app.models.financial import FinancialExtractionRun, FinancialLineItem, FinancialStatement
from app.models.financial_analysis import (
    FinancialAnalysisRun,
    FinancialRatio,
    FinancialRatioInput,
    FinancialValidationIssue,
    NormalizedFinancialValue,
)
from app.services.financial_engine.normalization import normalize_line_item
from app.services.financial_engine.ratio_definitions import (
    RATIO_TAXONOMY_VERSION,
    RatioDefinition,
    ratio_definitions,
)

VALIDATOR_VERSION = "financial_validator_v1"
CALCULATOR_VERSION = "financial_ratio_calculator_v1"
FORMULA_VERSION = "financial_ratio_formulas_v1"
CORE_FIELDS = {
    "revenue",
    "profit_after_tax",
    "total_assets",
    "total_equity",
    "total_debt",
    "cash_flow_from_operations",
}
logger = logging.getLogger(__name__)


def _input_hash(rows: list[tuple[FinancialLineItem, FinancialStatement]]) -> str:
    digest = hashlib.sha256()
    for item, statement in sorted(rows, key=lambda pair: str(pair[0].id)):
        digest.update(
            f"{item.id}|{item.numeric_value}|{item.currency}|{item.unit_multiplier}|{item.status}|"
            f"{statement.statement_scope}|{item.fiscal_year}\n".encode()
        )
    return digest.hexdigest()


def _latest_extraction_rows(
    session: Session, document_id: UUID
) -> list[tuple[FinancialLineItem, FinancialStatement]]:
    run = session.scalar(
        select(FinancialExtractionRun)
        .where(FinancialExtractionRun.document_id == document_id)
        .order_by(FinancialExtractionRun.created_at.desc())
    )
    if run is None:
        raise AppError(
            "FINANCIAL_EXTRACTION_REQUIRED",
            "Extract financial statements before financial analysis",
            409,
        )
    result = (
        session.execute(
            select(FinancialLineItem, FinancialStatement)
            .join(
                FinancialStatement,
                FinancialLineItem.financial_statement_id == FinancialStatement.id,
            )
            .where(FinancialStatement.run_id == run.id)
        )
        .tuples()
        .all()
    )
    return [(item, statement) for item, statement in result]


def _issue(
    session: Session,
    run: FinancialAnalysisRun,
    document: Document,
    scope: object,
    year: str,
    issue_type: str,
    severity: ValidationSeverity,
    message: str,
    status: ValidationStatus,
    values: list[NormalizedFinancialValue] | None = None,
    expected: Decimal | None = None,
    actual: Decimal | None = None,
    difference: Decimal | None = None,
    tolerance: Decimal | None = None,
) -> None:
    session.add(
        FinancialValidationIssue(
            run_id=run.id,
            analysis_job_id=document.analysis_job_id,
            company_id=document.company_id,
            document_id=document.id,
            statement_scope=scope,
            fiscal_year=year,
            issue_type=issue_type,
            severity=severity,
            message=message,
            related_line_item_ids=[
                str(value.financial_line_item_id)
                for value in values or []
                if value.financial_line_item_id
            ],
            related_value_ids=[str(value.id) for value in values or []],
            expected_value=expected,
            actual_value=actual,
            difference=difference,
            tolerance=tolerance,
            status=status,
            validator_version=VALIDATOR_VERSION,
        )
    )


def _derive(
    session: Session,
    run: FinancialAnalysisRun,
    document: Document,
    name: str,
    inputs: list[NormalizedFinancialValue],
    formula: str,
    value: Decimal,
) -> NormalizedFinancialValue:
    first = inputs[0]
    derived = NormalizedFinancialValue(
        run_id=run.id,
        analysis_job_id=document.analysis_job_id,
        company_id=document.company_id,
        document_id=document.id,
        canonical_name=name,
        statement_type=first.statement_type,
        statement_scope=first.statement_scope,
        fiscal_year=first.fiscal_year,
        measurement_type=first.measurement_type,
        raw_numeric_value=None,
        normalized_value=value,
        currency=first.currency,
        normalized_currency=first.normalized_currency,
        canonical_unit=first.canonical_unit,
        unit_multiplier=Decimal(1),
        normalization_status=(
            NormalizationStatus.NORMALIZED
            if all(item.normalization_status == NormalizationStatus.NORMALIZED for item in inputs)
            else NormalizationStatus.NEEDS_REVIEW
        ),
        normalization_confidence=max(
            0, round(min(item.normalization_confidence for item in inputs) - 0.05, 2)
        ),
        value_origin=ValueOrigin.DERIVED,
        formula=formula,
        input_value_ids=[str(item.id) for item in inputs],
    )
    session.add(derived)
    session.flush()
    return derived


def _validate_relation(
    session: Session,
    run: FinancialAnalysisRun,
    document: Document,
    values: dict[str, NormalizedFinancialValue],
    names: list[str],
    issue_type: str,
    message: str,
    actual: Decimal | None,
    expected: Decimal | None,
    tolerance_percent: Decimal,
    warning_only: bool = False,
) -> bool:
    present = [values[name] for name in names if name in values]
    if len(present) != len(names) or actual is None or expected is None:
        return False
    if len({value.normalized_currency for value in present}) != 1:
        _issue(
            session,
            run,
            document,
            present[0].statement_scope,
            present[0].fiscal_year,
            "CURRENCY_MISMATCH",
            ValidationSeverity.ERROR,
            f"{message}: inputs use different currencies.",
            ValidationStatus.FAIL,
            present,
        )
        return False
    difference = abs(actual - expected)
    tolerance = max(abs(expected), abs(actual), Decimal(1)) * tolerance_percent / Decimal(100)
    passed = difference <= tolerance
    _issue(
        session,
        run,
        document,
        present[0].statement_scope,
        present[0].fiscal_year,
        issue_type,
        ValidationSeverity.INFO
        if passed
        else ValidationSeverity.WARNING
        if warning_only
        else ValidationSeverity.ERROR,
        f"{message}: {'within' if passed else 'outside'} tolerance.",
        ValidationStatus.PASS
        if passed
        else ValidationStatus.WARNING
        if warning_only
        else ValidationStatus.FAIL,
        present,
        expected,
        actual,
        difference,
        tolerance,
    )
    return passed


def _calculate_ratio(
    definition: RatioDefinition,
    values: dict[str, NormalizedFinancialValue],
    prior: dict[str, NormalizedFinancialValue],
) -> tuple[
    Decimal | None, RatioStatus, float, str, list[tuple[str, NormalizedFinancialValue]], str | None
]:
    name = str(definition["name"])
    required = definition["required_inputs"]
    if any(item not in values for item in required):
        return None, RatioStatus.UNAVAILABLE, 0, "ENDING_BALANCE", [], None
    inputs = [(item, values[item]) for item in required]
    if any(value.normalization_status == NormalizationStatus.CONFLICTING for _, value in inputs):
        return None, RatioStatus.CONFLICTING, 0, "ENDING_BALANCE", inputs, None
    if any(value.normalized_value is None for _, value in inputs):
        return None, RatioStatus.UNAVAILABLE, 0, "ENDING_BALANCE", inputs, None
    if len({value.normalized_currency for _, value in inputs}) != 1:
        return None, RatioStatus.UNAVAILABLE, 0, "ENDING_BALANCE", inputs, "CURRENCY_MISMATCH"
    data: dict[str, Decimal] = {}
    for role, input_value in inputs:
        assert input_value.normalized_value is not None
        data[role] = input_value.normalized_value
    basis = "ENDING_BALANCE"
    denominator_name = {
        "current_ratio": "current_liabilities",
        "quick_ratio": "current_liabilities",
        "debt_to_equity": "total_equity",
        "debt_to_assets": "total_assets",
        "interest_coverage": "finance_cost",
        "debt_to_ebitda": "ebitda",
        "ebitda_margin": "revenue",
        "ebit_margin": "revenue",
        "net_profit_margin": "revenue",
        "operating_cash_flow_to_debt": "total_debt",
    }.get(name)
    if name in {"return_on_assets", "asset_turnover"}:
        denominator_name = "total_assets"
    elif name == "return_on_equity":
        denominator_name = "total_equity"
    assert denominator_name is not None
    denominator = data[denominator_name]
    if (
        name in {"return_on_assets", "return_on_equity", "asset_turnover"}
        and denominator_name in prior
    ):
        previous = prior[denominator_name]
        if (
            previous.normalized_value is not None
            and previous.normalized_currency == values[denominator_name].normalized_currency
        ):
            denominator = (denominator + previous.normalized_value) / Decimal(2)
            inputs.append((f"{denominator_name}_prior", previous))
            basis = "AVERAGE_BALANCE"
    if denominator == 0:
        return None, RatioStatus.UNAVAILABLE, 0, basis, inputs, "ZERO_DENOMINATOR"
    if denominator < 0 and name in {"debt_to_equity", "debt_to_ebitda"}:
        return (
            None,
            RatioStatus.NOT_MEANINGFUL,
            min(value.normalization_confidence for _, value in inputs),
            basis,
            inputs,
            "NEGATIVE_DENOMINATOR",
        )
    if name == "quick_ratio":
        numerator = data["current_assets"] - data["inventory"]
    else:
        numerator_name = {
            "current_ratio": "current_assets",
            "debt_to_equity": "total_debt",
            "debt_to_assets": "total_debt",
            "interest_coverage": "ebit",
            "debt_to_ebitda": "total_debt",
            "ebitda_margin": "ebitda",
            "ebit_margin": "ebit",
            "net_profit_margin": "profit_after_tax",
            "return_on_assets": "profit_after_tax",
            "return_on_equity": "profit_after_tax",
            "operating_cash_flow_to_debt": "cash_flow_from_operations",
            "asset_turnover": "revenue",
        }[name]
        numerator = data[numerator_name]
    result = numerator / denominator
    confidence = min(value.normalization_confidence for _, value in inputs)
    status = (
        RatioStatus.VERIFIED
        if all(value.normalization_status == NormalizationStatus.NORMALIZED for _, value in inputs)
        else RatioStatus.NEEDS_REVIEW
    )
    if denominator < 0:
        status = RatioStatus.NEEDS_REVIEW
    return (
        result.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
        status,
        confidence,
        basis,
        inputs,
        None,
    )


def _summary(session: Session, run: FinancialAnalysisRun) -> dict[str, object]:
    issues = Counter(
        session.scalars(
            select(FinancialValidationIssue.status).where(FinancialValidationIssue.run_id == run.id)
        ).all()
    )
    review = (
        session.scalar(
            select(func.count())
            .select_from(FinancialRatio)
            .where(
                FinancialRatio.run_id == run.id,
                FinancialRatio.status == RatioStatus.NEEDS_REVIEW,
            )
        )
        or 0
    )
    return {
        "document_id": run.document_id,
        "status": run.status,
        "normalized_values": run.normalized_value_count,
        "derived_values": run.derived_value_count,
        "validation": {
            "passed_checks": issues[ValidationStatus.PASS],
            "warnings": issues[ValidationStatus.WARNING],
            "errors": issues[ValidationStatus.FAIL],
        },
        "ratios_calculated": run.ratio_count,
        "ratios_review_required": review,
        "completeness_score": run.completeness_score,
        "validator_version": run.validator_version,
        "ratio_calculator_version": run.calculator_version,
        "ratio_taxonomy_version": run.ratio_taxonomy_version,
    }


def _run_financial_analysis(
    session: Session,
    document_id: UUID,
    tolerance_percent: float = 1.0,
    debt_tolerance_percent: float | None = None,
    cash_tolerance_percent: float | None = None,
) -> dict[str, object]:
    with session.begin():
        document = session.get(Document, document_id, with_for_update=True)
        if document is None:
            raise AppError("DOCUMENT_NOT_FOUND", "Document not found", 404)
        rows = _latest_extraction_rows(session, document_id)
        fingerprint = _input_hash(rows)
        logger.info("Financial analysis started: document=%s inputs=%s", document_id, len(rows))
        existing = session.scalar(
            select(FinancialAnalysisRun).where(
                FinancialAnalysisRun.document_id == document_id,
                FinancialAnalysisRun.input_hash == fingerprint,
                FinancialAnalysisRun.validator_version == VALIDATOR_VERSION,
                FinancialAnalysisRun.calculator_version == CALCULATOR_VERSION,
                FinancialAnalysisRun.ratio_taxonomy_version == RATIO_TAXONOMY_VERSION,
            )
        )
        if existing:
            return _summary(session, existing)
        document.analysis_job.current_stage = AnalysisStage.FINANCIAL_VALIDATION

        def audit(action: str, metadata: dict[str, object]) -> None:
            write_audit_log(
                session,
                entity_type="document",
                entity_id=document.id,
                action=action,
                event_type=action,
                company_id=document.company_id,
                analysis_job_id=document.analysis_job_id,
                metadata_json=metadata,
            )

        audit("FINANCIAL_NORMALIZATION_STARTED", {"input_hash": fingerprint})
        run = FinancialAnalysisRun(
            document_id=document.id,
            analysis_job_id=document.analysis_job_id,
            input_hash=fingerprint,
            status="PROCESSING",
            completeness_score=0,
            validator_version=VALIDATOR_VERSION,
            calculator_version=CALCULATOR_VERSION,
            ratio_taxonomy_version=RATIO_TAXONOMY_VERSION,
        )
        session.add(run)
        session.flush()
        groups: dict[
            tuple[object, str, str], list[tuple[FinancialLineItem, FinancialStatement]]
        ] = defaultdict(list)
        for item, statement in rows:
            if item.canonical_name and item.fiscal_year:
                groups[(statement.statement_scope, item.fiscal_year, item.canonical_name)].append(
                    (item, statement)
                )
        selected: dict[tuple[object, str], dict[str, NormalizedFinancialValue]] = defaultdict(dict)
        for (scope, year, name), candidates in groups.items():
            normalized_candidates = [
                (item, statement, *normalize_line_item(item)) for item, statement in candidates
            ]
            reliable = [
                entry
                for entry in normalized_candidates
                if entry[2] is not None
                and entry[4]
                not in {NormalizationStatus.CONFLICTING, NormalizationStatus.INVALID_VALUE}
            ]
            signatures = {(entry[2], entry[0].currency) for entry in reliable}
            currencies = {entry[0].currency for entry in reliable}
            currency_mismatch = len(currencies) > 1
            conflicting = len(signatures) > 1 and not currency_mismatch
            ordered = sorted(
                normalized_candidates,
                key=lambda entry: (
                    entry[0].status != FinancialStatus.VERIFIED,
                    entry[0].source_priority,
                    -entry[0].confidence_score,
                    entry[0].page_number,
                ),
            )
            item, statement, value, canonical_unit, norm_status = ordered[0]
            if currency_mismatch:
                norm_status = NormalizationStatus.CURRENCY_MISMATCH
                value = None
            elif conflicting:
                norm_status = NormalizationStatus.CONFLICTING
                value = None
            normalized = NormalizedFinancialValue(
                run_id=run.id,
                financial_line_item_id=item.id,
                analysis_job_id=document.analysis_job_id,
                company_id=document.company_id,
                document_id=document.id,
                canonical_name=name,
                statement_type=statement.statement_type,
                statement_scope=scope,
                fiscal_year=year,
                measurement_type=item.measurement_type,
                raw_numeric_value=item.numeric_value,
                normalized_value=value,
                currency=item.currency,
                normalized_currency=item.currency,
                raw_unit=item.raw_unit,
                canonical_unit=canonical_unit,
                unit_multiplier=item.unit_multiplier,
                normalization_status=norm_status,
                normalization_confidence=item.confidence_score,
                value_origin=ValueOrigin.EXTRACTED,
            )
            session.add(normalized)
            session.flush()
            run.normalized_value_count += 1
            selected[(scope, year)][name] = normalized
            if currency_mismatch:
                _issue(
                    session,
                    run,
                    document,
                    scope,
                    year,
                    "CURRENCY_MISMATCH",
                    ValidationSeverity.ERROR,
                    f"Candidates for {name} use different currencies; no FX conversion was attempted.",
                    ValidationStatus.FAIL,
                    [normalized],
                )
            elif conflicting:
                _issue(
                    session,
                    run,
                    document,
                    scope,
                    year,
                    "CONFLICTING_FINANCIAL_VALUE",
                    ValidationSeverity.ERROR,
                    f"Conflicting candidates exist for {name}.",
                    ValidationStatus.FAIL,
                    [normalized],
                )
            elif len(candidates) > 1:
                _issue(
                    session,
                    run,
                    document,
                    scope,
                    year,
                    "DUPLICATE_FINANCIAL_VALUE",
                    ValidationSeverity.INFO,
                    f"Consistent duplicate candidates exist for {name}; the highest-priority source was selected.",
                    ValidationStatus.PASS,
                    [normalized],
                )
            if norm_status == NormalizationStatus.INVALID_VALUE:
                _issue(
                    session,
                    run,
                    document,
                    scope,
                    year,
                    "UNIT_NORMALIZATION_FAILED",
                    ValidationSeverity.ERROR,
                    f"{name} could not be normalized because currency or unit metadata is invalid.",
                    ValidationStatus.FAIL,
                    [normalized],
                )
        # A revenue-from-operations value is a safe analytical revenue alias when total revenue is absent.
        for key, values in selected.items():
            if "revenue" not in values and "revenue_from_operations" in values:
                values["revenue"] = _derive(
                    session,
                    run,
                    document,
                    "revenue",
                    [values["revenue_from_operations"]],
                    "revenue = revenue_from_operations",
                    values["revenue_from_operations"].normalized_value or Decimal(0),
                )
                run.derived_value_count += 1
            if (
                "total_debt" not in values
                and {"short_term_borrowings", "long_term_borrowings"} <= values.keys()
            ):
                debt_inputs = [values["short_term_borrowings"], values["long_term_borrowings"]]
                if (
                    all(item.normalized_value is not None for item in debt_inputs)
                    and len({item.normalized_currency for item in debt_inputs}) == 1
                ):
                    values["total_debt"] = _derive(
                        session,
                        run,
                        document,
                        "total_debt",
                        debt_inputs,
                        "total_debt = short_term_borrowings + long_term_borrowings",
                        sum(
                            (item.normalized_value or Decimal(0) for item in debt_inputs),
                            Decimal(0),
                        ),
                    )
                    run.derived_value_count += 1
                elif len({item.normalized_currency for item in debt_inputs}) > 1:
                    _issue(
                        session,
                        run,
                        document,
                        key[0],
                        key[1],
                        "CURRENCY_MISMATCH",
                        ValidationSeverity.ERROR,
                        "Short-term and long-term borrowings use different currencies; total debt was not derived.",
                        ValidationStatus.FAIL,
                        debt_inputs,
                    )
        audit(
            "FINANCIAL_NORMALIZATION_COMPLETED",
            {
                "normalized_count": run.normalized_value_count,
                "derived_count": run.derived_value_count,
            },
        )
        scope_years: dict[object, set[str]] = defaultdict(set)
        for scope, year in selected:
            scope_years[scope].add(year)
        for scope, years in scope_years.items():
            names = {
                name
                for (value_scope, _), values in selected.items()
                if value_scope == scope
                for name in values
            }
            for name in names:
                across_years = [
                    selected[(scope, year)][name]
                    for year in years
                    if name in selected[(scope, year)]
                ]
                if name in CORE_FIELDS and len(across_years) != len(years):
                    _issue(
                        session,
                        run,
                        document,
                        scope,
                        max(years),
                        "PERIOD_MISMATCH",
                        ValidationSeverity.WARNING,
                        f"{name} is not available for every detected fiscal year in this scope.",
                        ValidationStatus.WARNING,
                        across_years,
                    )
                if len({item.normalized_currency for item in across_years}) > 1:
                    _issue(
                        session,
                        run,
                        document,
                        scope,
                        max(years),
                        "CURRENCY_MISMATCH",
                        ValidationSeverity.ERROR,
                        f"{name} uses different currencies across fiscal years.",
                        ValidationStatus.FAIL,
                        across_years,
                    )
                raw_units = {item.raw_unit for item in across_years if item.raw_unit}
                if len(raw_units) > 1 and all(
                    item.normalized_value is not None for item in across_years
                ):
                    _issue(
                        session,
                        run,
                        document,
                        scope,
                        max(years),
                        "UNIT_NORMALIZATION_CHECK",
                        ValidationSeverity.INFO,
                        f"{name} uses multiple source units across years; all were normalized to base units.",
                        ValidationStatus.PASS,
                        across_years,
                    )
        tolerance = Decimal(str(tolerance_percent))
        completeness_scores: list[float] = []
        for (scope, year), values in selected.items():
            reliable_names = {
                name
                for name, value in values.items()
                if value.normalized_value is not None
                and value.normalization_status
                in {NormalizationStatus.NORMALIZED, NormalizationStatus.NEEDS_REVIEW}
            }
            completeness_scores.append(len(CORE_FIELDS & reliable_names) / len(CORE_FIELDS))
            for missing in sorted(CORE_FIELDS - reliable_names):
                _issue(
                    session,
                    run,
                    document,
                    scope,
                    year,
                    "MISSING_REQUIRED_INPUT",
                    ValidationSeverity.INFO,
                    f"Core completeness input {missing} is unavailable.",
                    ValidationStatus.SKIPPED,
                )
            if {"total_assets", "total_liabilities", "total_equity"} <= values.keys():
                _validate_relation(
                    session,
                    run,
                    document,
                    values,
                    ["total_assets", "total_liabilities", "total_equity"],
                    "ACCOUNTING_EQUATION_MISMATCH",
                    "Assets compared with liabilities plus equity",
                    values["total_assets"].normalized_value,
                    (values["total_liabilities"].normalized_value or Decimal(0))
                    + (values["total_equity"].normalized_value or Decimal(0)),
                    tolerance,
                )
            else:
                _issue(
                    session,
                    run,
                    document,
                    scope,
                    year,
                    "ACCOUNTING_EQUATION_MISMATCH",
                    ValidationSeverity.INFO,
                    "Accounting equation check skipped because one or more inputs are unavailable.",
                    ValidationStatus.SKIPPED,
                )
            for child, total in (
                ("current_assets", "total_assets"),
                ("non_current_assets", "total_assets"),
                ("current_liabilities", "total_liabilities"),
            ):
                if (
                    child in values
                    and total in values
                    and values[child].normalized_value is not None
                    and values[total].normalized_value is not None
                ):
                    child_value = values[child].normalized_value
                    total_value = values[total].normalized_value
                    assert child_value is not None and total_value is not None
                    failed = child_value > total_value
                    _issue(
                        session,
                        run,
                        document,
                        scope,
                        year,
                        "BALANCE_SHEET_RECONCILIATION",
                        ValidationSeverity.ERROR if failed else ValidationSeverity.INFO,
                        f"{child} must not exceed {total}.",
                        ValidationStatus.FAIL if failed else ValidationStatus.PASS,
                        [values[child], values[total]],
                        values[total].normalized_value,
                        values[child].normalized_value,
                    )
            if {"short_term_borrowings", "long_term_borrowings", "total_debt"} <= values.keys():
                _validate_relation(
                    session,
                    run,
                    document,
                    values,
                    ["short_term_borrowings", "long_term_borrowings", "total_debt"],
                    "DEBT_RECONCILIATION_MISMATCH",
                    "Short-term plus long-term borrowings compared with total debt",
                    values["total_debt"].normalized_value,
                    (values["short_term_borrowings"].normalized_value or Decimal(0))
                    + (values["long_term_borrowings"].normalized_value or Decimal(0)),
                    Decimal(str(debt_tolerance_percent))
                    if debt_tolerance_percent is not None
                    else tolerance,
                )
            else:
                _issue(
                    session,
                    run,
                    document,
                    scope,
                    year,
                    "DEBT_RECONCILIATION_MISMATCH",
                    ValidationSeverity.INFO,
                    "Debt reconciliation skipped because one or more inputs are unavailable.",
                    ValidationStatus.SKIPPED,
                )
            if {"opening_cash", "net_change_in_cash", "closing_cash"} <= values.keys():
                _validate_relation(
                    session,
                    run,
                    document,
                    values,
                    ["opening_cash", "net_change_in_cash", "closing_cash"],
                    "CASH_RECONCILIATION_MISMATCH",
                    "Opening cash plus net change compared with closing cash",
                    values["closing_cash"].normalized_value,
                    (values["opening_cash"].normalized_value or Decimal(0))
                    + (values["net_change_in_cash"].normalized_value or Decimal(0)),
                    Decimal(str(cash_tolerance_percent))
                    if cash_tolerance_percent is not None
                    else tolerance,
                )
            else:
                _issue(
                    session,
                    run,
                    document,
                    scope,
                    year,
                    "CASH_RECONCILIATION_MISMATCH",
                    ValidationSeverity.INFO,
                    "Cash reconciliation skipped because one or more inputs are unavailable.",
                    ValidationStatus.SKIPPED,
                )
            if {"profit_before_tax", "tax_expense", "profit_after_tax"} <= values.keys():
                _validate_relation(
                    session,
                    run,
                    document,
                    values,
                    ["profit_before_tax", "tax_expense", "profit_after_tax"],
                    "INCOME_RECONCILIATION_MISMATCH",
                    "PBT less tax compared with PAT",
                    values["profit_after_tax"].normalized_value,
                    (values["profit_before_tax"].normalized_value or Decimal(0))
                    - (values["tax_expense"].normalized_value or Decimal(0)),
                    tolerance,
                    True,
                )
            else:
                _issue(
                    session,
                    run,
                    document,
                    scope,
                    year,
                    "INCOME_RECONCILIATION_MISMATCH",
                    ValidationSeverity.INFO,
                    "Income reconciliation skipped because one or more inputs are unavailable.",
                    ValidationStatus.SKIPPED,
                )
        run.completeness_score = round(max(completeness_scores, default=0), 4)
        session.flush()
        validation_issue_count = (
            session.scalar(
                select(func.count())
                .select_from(FinancialValidationIssue)
                .where(
                    FinancialValidationIssue.run_id == run.id,
                    FinancialValidationIssue.status.in_(
                        [ValidationStatus.WARNING, ValidationStatus.FAIL]
                    ),
                )
            )
            or 0
        )
        audit(
            "FINANCIAL_VALIDATION_COMPLETED",
            {
                "validation_issue_count": validation_issue_count,
                "completeness_score": run.completeness_score,
                "validator_version": VALIDATOR_VERSION,
            },
        )
        if validation_issue_count:
            audit(
                "FINANCIAL_VALIDATION_ISSUE_FOUND",
                {"validation_issue_count": validation_issue_count},
            )
        for (scope, year), values in selected.items():
            year_number = int(year.removeprefix("FY")) if year.removeprefix("FY").isdigit() else 0
            prior = selected.get((scope, f"FY{year_number - 1}"), {})
            for definition in ratio_definitions():
                result, ratio_status, confidence, basis, inputs, issue_type = _calculate_ratio(
                    definition, values, prior
                )
                ratio = FinancialRatio(
                    run_id=run.id,
                    analysis_job_id=document.analysis_job_id,
                    company_id=document.company_id,
                    document_id=document.id,
                    statement_scope=scope,
                    fiscal_year=year,
                    ratio_name=str(definition["name"]),
                    ratio_category=str(definition["category"]),
                    ratio_value=result,
                    ratio_unit=str(definition["unit"]),
                    status=ratio_status,
                    confidence_score=confidence,
                    calculation_basis=basis,
                    formula=str(definition["formula"]),
                    formula_version=FORMULA_VERSION,
                    ratio_taxonomy_version=RATIO_TAXONOMY_VERSION,
                    calculator_version=CALCULATOR_VERSION,
                )
                session.add(ratio)
                session.flush()
                for role, ratio_input in inputs:
                    session.add(
                        FinancialRatioInput(
                            financial_ratio_id=ratio.id,
                            normalized_financial_value_id=ratio_input.id,
                            input_role=role,
                        )
                    )
                if result is not None:
                    run.ratio_count += 1
                if issue_type:
                    _issue(
                        session,
                        run,
                        document,
                        scope,
                        year,
                        issue_type,
                        ValidationSeverity.WARNING,
                        f"{definition['display_name']} could not be presented normally: {issue_type}.",
                        ValidationStatus.WARNING,
                        [ratio_input for _, ratio_input in inputs],
                    )
        audit(
            "FINANCIAL_RATIOS_CALCULATED",
            {
                "ratio_count": run.ratio_count,
                "calculator_version": CALCULATOR_VERSION,
                "ratio_taxonomy_version": RATIO_TAXONOMY_VERSION,
            },
        )
        session.flush()
        failures = (
            session.scalar(
                select(func.count())
                .select_from(FinancialValidationIssue)
                .where(
                    FinancialValidationIssue.run_id == run.id,
                    FinancialValidationIssue.status == ValidationStatus.FAIL,
                )
            )
            or 0
        )
        warnings = (
            session.scalar(
                select(func.count())
                .select_from(FinancialValidationIssue)
                .where(
                    FinancialValidationIssue.run_id == run.id,
                    FinancialValidationIssue.status == ValidationStatus.WARNING,
                )
            )
            or 0
        )
        run.status = (
            "NEEDS_REVIEW"
            if failures
            else "PARTIAL"
            if warnings or run.completeness_score < 1
            else "VERIFIED"
        )
        run.completed_at = datetime.now(UTC)
        audit(
            "FINANCIAL_ANALYSIS_COMPLETED"
            if not failures
            else "FINANCIAL_ANALYSIS_REVIEW_REQUIRED",
            {"run_id": str(run.id), "status": run.status},
        )
        logger.info(
            "Financial analysis completed: document=%s normalized=%s derived=%s ratios=%s issues=%s",
            document_id,
            run.normalized_value_count,
            run.derived_value_count,
            run.ratio_count,
            failures + warnings,
        )
        return _summary(session, run)


def run_financial_analysis(
    session: Session,
    document_id: UUID,
    tolerance_percent: float = 1.0,
    debt_tolerance_percent: float | None = None,
    cash_tolerance_percent: float | None = None,
) -> dict[str, object]:
    try:
        return _run_financial_analysis(
            session,
            document_id,
            tolerance_percent,
            debt_tolerance_percent,
            cash_tolerance_percent,
        )
    except AppError:
        raise
    except Exception as exc:
        logger.exception(
            "Financial analysis failed: document=%s error=%s", document_id, type(exc).__name__
        )
        session.rollback()
        try:
            with session.begin():
                document = session.get(Document, document_id)
                if document:
                    write_audit_log(
                        session,
                        entity_type="document",
                        entity_id=document.id,
                        action="FINANCIAL_ANALYSIS_FAILED",
                        event_type="FINANCIAL_ANALYSIS_FAILED",
                        company_id=document.company_id,
                        analysis_job_id=document.analysis_job_id,
                        metadata_json={"error_type": type(exc).__name__},
                    )
        except Exception:
            session.rollback()
        raise


def latest_analysis_run(session: Session, document_id: UUID) -> FinancialAnalysisRun | None:
    return session.scalar(
        select(FinancialAnalysisRun)
        .where(FinancialAnalysisRun.document_id == document_id)
        .order_by(FinancialAnalysisRun.created_at.desc())
    )
