"use client";

import { useState } from "react";
import { extractFinancialStatements, getCreditEvidence, getCreditReasons, getFinancialAnomalies, getFinancialAnomaly, getFinancialLineItems, getFinancialRatio, getFinancialRatios, getFinancialStatements, getFinancialTrend, getFinancialTrends, getFinancialValidation, runCreditAnalysis, runFinancialAnalysis, runFinancialTrendAnalysis } from "@/lib/api";
import type { CreditAssessment, CreditEvidence, CreditReason, FinancialAnalysisSummary, FinancialAnomaly, FinancialAnomalyDetail, FinancialExtractionSummary, FinancialLineItem, FinancialRatio, FinancialRatioDetail, FinancialStatement, FinancialTrend, FinancialTrendAnalysisSummary, FinancialTrendDetail, FinancialValidation } from "@/types/api";

export function FinancialStatements({ documentId }: { documentId: string }) {
  const [summary, setSummary] = useState<FinancialExtractionSummary | null>(null);
  const [statements, setStatements] = useState<FinancialStatement[]>([]);
  const [items, setItems] = useState<Record<string, FinancialLineItem[]>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [analysis, setAnalysis] = useState<FinancialAnalysisSummary | null>(null);
  const [validation, setValidation] = useState<FinancialValidation | null>(null);
  const [ratios, setRatios] = useState<FinancialRatio[]>([]);
  const [ratioDetail, setRatioDetail] = useState<FinancialRatioDetail | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [trendAnalysis, setTrendAnalysis] = useState<FinancialTrendAnalysisSummary | null>(null);
  const [trends, setTrends] = useState<FinancialTrend[]>([]);
  const [anomalies, setAnomalies] = useState<FinancialAnomaly[]>([]);
  const [trendDetail, setTrendDetail] = useState<FinancialTrendDetail | null>(null);
  const [anomalyDetail, setAnomalyDetail] = useState<FinancialAnomalyDetail | null>(null);
  const [trendBusy, setTrendBusy] = useState(false);
  const [creditAssessments, setCreditAssessments] = useState<CreditAssessment[]>([]);
  const [creditReasons, setCreditReasons] = useState<Record<string, CreditReason[]>>({});
  const [creditEvidence, setCreditEvidence] = useState<Record<string, CreditEvidence[]>>({});
  const [creditBusy, setCreditBusy] = useState(false);
  const [activeView, setActiveView] = useState<"normalized" | "validation" | "ratios" | "trends" | "anomalies" | "credit">("normalized");
  const ratioDisplay = (ratio: FinancialRatio) => ratio.ratio_value === null
    ? "Unavailable"
    : ratio.ratio_unit === "%"
      ? `${(Number(ratio.ratio_value) * 100).toFixed(2)}%`
      : `${Number(ratio.ratio_value).toFixed(2)}x`;

  async function run() {
    setBusy(true);
    setError("");
    try {
      setSummary(await extractFinancialStatements(documentId));
      setStatements(await getFinancialStatements(documentId));
      setItems({});
      setAnalysis(null);
      setValidation(null);
      setRatios([]);
      setTrendAnalysis(null);
      setTrends([]);
      setAnomalies([]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Financial extraction failed.");
    } finally {
      setBusy(false);
    }
  }

  async function analyzeTrends() {
    setTrendBusy(true);
    setError("");
    try {
      setTrendAnalysis(await runFinancialTrendAnalysis(documentId));
      setTrends(await getFinancialTrends(documentId));
      setAnomalies(await getFinancialAnomalies(documentId));
      setActiveView("trends");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Trend analysis failed.");
    } finally {
      setTrendBusy(false);
    }
  }

  async function showTrendEvidence(trendId: string) {
    try {
      setTrendDetail(await getFinancialTrend(trendId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load trend evidence.");
    }
  }

  async function showAnomalyEvidence(anomalyId: string) {
    try {
      setAnomalyDetail(await getFinancialAnomaly(anomalyId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load anomaly evidence.");
    }
  }

  async function analyzeCredit() {
    setCreditBusy(true);
    setError("");
    try {
      const assessments = await runCreditAnalysis(documentId);
      setCreditAssessments(assessments);
      setActiveView("credit");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Credit analysis failed.");
    } finally {
      setCreditBusy(false);
    }
  }

  async function showCreditEvidence(assessmentId: string) {
    try {
      const [reasons, evidence] = await Promise.all([getCreditReasons(assessmentId), getCreditEvidence(assessmentId)]);
      setCreditReasons((current) => ({ ...current, [assessmentId]: reasons }));
      setCreditEvidence((current) => ({ ...current, [assessmentId]: evidence }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load credit evidence.");
    }
  }

  const trendValue = (trend: FinancialTrend, value: string) => {
    const number = Number(value);
    if (trend.metric_source_type === "RATIO") {
      return ["ebitda_margin", "ebit_margin", "net_profit_margin", "return_on_assets", "return_on_equity"].includes(trend.metric_name)
        ? `${(number * 100).toFixed(2)}%`
        : `${number.toFixed(2)}x`;
    }
    return `${number.toLocaleString()} ${trend.currency === "N/A" ? "" : trend.currency}`;
  };

  async function analyze() {
    setAnalyzing(true);
    setError("");
    try {
      setAnalysis(await runFinancialAnalysis(documentId));
      setValidation(await getFinancialValidation(documentId));
      setRatios(await getFinancialRatios(documentId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Financial analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function showRatioEvidence(ratioId: string) {
    try {
      setRatioDetail(await getFinancialRatio(ratioId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load ratio evidence.");
    }
  }

  async function toggle(statementId: string) {
    if (items[statementId]) {
      setItems((current) => { const next = { ...current }; delete next[statementId]; return next; });
      return;
    }
    try {
      const loaded = await getFinancialLineItems(statementId);
      setItems((current) => ({ ...current, [statementId]: loaded }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load line items.");
    }
  }

  return <section className="result" aria-label="Financial statements">
    <h2>Financial statements</h2>
    <button type="button" onClick={run} disabled={busy}>{busy ? "Extracting…" : "Extract financial statements"}</button>
    {error && <p role="alert" className="error">{error}</p>}
    {summary && <p role="status">{summary.status} · {summary.statements_found} statements · {summary.line_items_extracted} rows · {summary.review_items} review · {summary.conflicting_items} conflicts · {summary.unmapped_items} unmapped</p>}
    {summary && <button type="button" onClick={analyze} disabled={analyzing}>{analyzing ? "Analyzing…" : "Normalize, validate, and calculate ratios"}</button>}
    {analysis && <div className="result" role="status">
      <h3>Financial analysis</h3>
      <p><strong>{analysis.status}</strong> · Completeness {Math.round(analysis.completeness_score * 100)}% · {analysis.normalized_values} normalized · {analysis.derived_values} derived · {analysis.ratios_calculated} ratios</p>
      <p>Validation: {analysis.validation.passed_checks} passed · {analysis.validation.warnings} warnings · {analysis.validation.errors} errors</p>
      <button type="button" onClick={analyzeTrends} disabled={trendBusy}>{trendBusy ? "Analyzing trends…" : "Analyze trends and anomalies"}</button>
      {trendAnalysis && <p>{trendAnalysis.trend_count} trends · {trendAnalysis.anomaly_count} alerts · {trendAnalysis.years.join(" → ")}</p>}
      {trendAnalysis && <button type="button" onClick={analyzeCredit} disabled={creditBusy}>{creditBusy ? "Calculating credit risk…" : "Calculate credit risk"}</button>}
    </div>}
    {validation && <nav aria-label="Financial analysis views">
      {(["normalized", "validation", "ratios", "trends", "anomalies", "credit"] as const).map((view) => <button type="button" key={view} aria-pressed={activeView === view} onClick={() => setActiveView(view)}>{view === "credit" ? "Credit risk" : view[0].toUpperCase() + view.slice(1)}</button>)}
    </nav>}
    {validation && activeView === "normalized" && <div className="result">
      <h3>Normalized financials</h3>
      <ul>{validation.normalized_values.map((value) => <li key={value.id}>
        <strong>{value.canonical_name.replaceAll("_", " ")}</strong> · {value.statement_scope} {value.fiscal_year}: {value.normalized_value ?? "Unavailable"} {value.currency ?? ""} · {value.origin} · {value.status}
        {value.source && <details><summary>Original value and source</summary><p>Raw: {value.source.raw_value} {value.source.raw_unit ?? ""} · Page {value.source.page_number}</p><p>{value.source.evidence_text}</p></details>}
        {value.formula && <details><summary>Derived formula</summary><p>{value.formula}</p></details>}
      </li>)}</ul>
    </div>}
    {validation && activeView === "validation" && <div className="result">
      <h3>Validation</h3>
      <ul>{validation.issues.filter((issue) => issue.status !== "SKIPPED").map((issue) => <li key={issue.id}>
        <strong>{issue.issue_type.replaceAll("_", " ")}</strong> · {issue.statement_scope} {issue.fiscal_year} · {issue.status}<p>{issue.message}</p>
      </li>)}</ul>
    </div>}
    {ratios.length > 0 && activeView === "ratios" && <div className="result">
      <h3>Financial ratios</h3>
      <ul>{ratios.map((ratio) => <li key={ratio.id}>
        <strong>{ratio.ratio_name.replaceAll("_", " ")}</strong> · {ratio.statement_scope} {ratio.fiscal_year}: {ratioDisplay(ratio)} · {ratio.status} · {Math.round(ratio.confidence_score * 100)}% · {ratio.calculation_basis.replaceAll("_", " ")}{" "}
        <button type="button" onClick={() => void showRatioEvidence(ratio.id)}>View formula and evidence</button>
      </li>)}</ul>
      {ratioDetail && <aside className="result" aria-label="Ratio evidence">
        <strong>{ratioDetail.ratio_name.replaceAll("_", " ")} · {ratioDetail.formula}</strong>
        <ul>{ratioDetail.inputs.map((input) => <li key={`${input.input_role}-${input.canonical_name}`}>
          {input.input_role.replaceAll("_", " ")}: {input.normalized_value ?? "Unavailable"} {input.currency ?? ""} · {input.origin}
          {input.source && <details><summary>Page {input.source.page_number} evidence</summary><p>{input.source.evidence_text}</p><p>Raw: {input.source.raw_label} · {input.source.raw_value}</p></details>}
          {input.derived_sources.map((source) => <details key={`${source.canonical_name}-${source.page_number}`}><summary>{source.canonical_name.replaceAll("_", " ")} · Page {source.page_number}</summary><p>{source.evidence_text}</p><p>Raw: {source.raw_label} · {source.raw_value}</p></details>)}
        </li>)}</ul>
      </aside>}
    </div>}
    {activeView === "trends" && trends.length > 0 && <div className="result">
      <h3>Financial trends</h3>
      <ul>{trends.map((trend) => <li key={trend.id}>
        <strong>{trend.metric_name.replaceAll("_", " ")}</strong> · {trend.statement_scope} · {trend.trend_direction} {trend.trend_strength ?? ""} · {trend.status} · {Math.round(trend.confidence_score * 100)}%
        <ul>{trend.series.map((point) => <li key={point.fiscal_year}>{point.fiscal_year}: {trendValue(trend, point.value)}{point.percentage_change ? ` · ${(Number(point.percentage_change) * 100).toFixed(1)}%` : ""}{point.percentage_point_change ? ` · ${Number(point.percentage_point_change).toFixed(1)} pp` : ""}{point.state_transition ? ` · ${point.state_transition.replaceAll("_", " ")}` : ""}</li>)}</ul>
        <p>{trend.cagr ? `CAGR ${(Number(trend.cagr) * 100).toFixed(1)}% · ` : ""}{trend.percentage_point_change ? `Change ${Number(trend.percentage_point_change).toFixed(1)} percentage points · ` : ""}{trend.missing_periods?.length ? `Missing ${trend.missing_periods.join(", ")} · ` : ""}<button type="button" onClick={() => void showTrendEvidence(trend.id)}>View evidence</button></p>
      </li>)}</ul>
      {trendDetail && <aside className="result" aria-label="Trend evidence"><strong>{trendDetail.metric_name.replaceAll("_", " ")} · {trendDetail.formula}</strong><ul>{trendDetail.inputs.flatMap((input) => input.evidence).map((source, index) => <li key={`${source.canonical_name}-${source.fiscal_year}-${index}`}>{source.canonical_name.replaceAll("_", " ")} {source.fiscal_year}: {source.value} {source.currency ?? ""}{source.page_number ? ` · Page ${source.page_number}` : ""}{source.evidence_text && <details><summary>Source evidence</summary><p>{source.evidence_text}</p><p>Raw: {source.raw_label} · {source.raw_value}</p></details>}</li>)}</ul></aside>}
    </div>}
    {activeView === "anomalies" && <div className="result">
      <h3>Financial alerts</h3>
      {anomalies.length === 0 ? <p>No configured anomaly rules were triggered by the available comparable periods.</p> : <ul>{anomalies.map((anomaly) => <li key={anomaly.id}>
        <strong>{anomaly.severity} · {anomaly.title}</strong> · {anomaly.statement_scope} · {anomaly.status} · {Math.round(anomaly.confidence_score * 100)}%<p>{anomaly.description}</p><p>{anomaly.start_fiscal_year} → {anomaly.end_fiscal_year} · {anomaly.rule_version} · <button type="button" onClick={() => void showAnomalyEvidence(anomaly.id)}>View evidence</button></p>
      </li>)}</ul>}
      {anomalyDetail && <aside className="result" aria-label="Anomaly evidence"><strong>{anomalyDetail.title}</strong><ul>{anomalyDetail.inputs.flatMap((input) => input.source.inputs).flatMap((input) => input.evidence).map((source, index) => <li key={`${source.canonical_name}-${source.fiscal_year}-${index}`}>{source.canonical_name.replaceAll("_", " ")} {source.fiscal_year}: {source.value} {source.currency ?? ""}{source.page_number ? ` · Page ${source.page_number}` : ""}{source.evidence_text && <details><summary>Source evidence</summary><p>{source.evidence_text}</p></details>}</li>)}</ul></aside>}
    </div>}
    {activeView === "credit" && <div className="result">
      <h3>Credit risk assessment</h3>
      {creditAssessments.length === 0 ? <p>Calculate credit risk after completing financial trends.</p> : creditAssessments.map((assessment) => <article key={assessment.assessment_id} className="result">
        <h4>{assessment.statement_scope.replaceAll("_", " ")}</h4>
        <p><strong>{assessment.overall_score === null ? "Insufficient data" : `${Number(assessment.overall_score).toFixed(1)} · ${assessment.risk_band?.replaceAll("_", " ")}`}</strong> · {assessment.status.replaceAll("_", " ")} · Coverage {Math.round(Number(assessment.component_coverage) * 100)}% · Confidence {Math.round(Number(assessment.confidence_score) * 100)}%</p>
        <ul>{assessment.subscores.map((score) => <li key={score.component}><strong>{score.component.replaceAll("_", " ")}</strong>: {Number(score.score).toFixed(1)} · weight {Math.round(Number(score.weight) * 100)}% · coverage {Math.round(Number(score.coverage) * 100)}% · {score.status.replaceAll("_", " ")}</li>)}</ul>
        {assessment.top_positive_factors.length > 0 && <><h4>Positive factors</h4><ul>{assessment.top_positive_factors.map((factor) => <li key={factor.rule_code}>+{factor.impact} · {factor.message}</li>)}</ul></>}
        {assessment.top_negative_factors.length > 0 && <><h4>Risk factors</h4><ul>{assessment.top_negative_factors.map((factor) => <li key={factor.rule_code}>{factor.impact} · {factor.message}</li>)}</ul></>}
        <button type="button" onClick={() => void showCreditEvidence(assessment.assessment_id)}>View all reasons and source evidence</button>
        {creditReasons[assessment.assessment_id] && <details open><summary>Policy reasons</summary><ul>{creditReasons[assessment.assessment_id].map((reason) => <li key={reason.id}><strong>{reason.rule_code.replaceAll("_", " ")}</strong> · {reason.score_impact} · {reason.message} · {reason.input_status.replaceAll("_", " ")}</li>)}</ul></details>}
        {creditEvidence[assessment.assessment_id] && <details><summary>Source evidence</summary><ul>{creditEvidence[assessment.assessment_id].flatMap((input) => input.evidence.map((source, index) => <li key={`${input.assessment_input_id}-${index}`}><strong>{input.input_role.replaceAll("_", " ")}</strong> · {source.metric.replaceAll("_", " ")}{source.fiscal_year ? ` ${source.fiscal_year}` : ""}{source.value !== null ? `: ${source.value}` : ""}{source.page_number ? ` · Page ${source.page_number}` : ""}{source.evidence_text && <details><summary>Evidence text</summary><p>{source.evidence_text}</p></details>}</li>))}</ul></details>}
        <p><small>{assessment.disclaimer} Policy: {assessment.policy_version}</small></p>
      </article>)}
    </div>}
    {statements.map((statement) => <div key={statement.id} className="result">
      <h3>{statement.statement_type.replaceAll("_", " ")} · {statement.statement_scope} · {statement.fiscal_year ?? "Period unknown"}</h3>
      <p>{statement.currency ?? "Currency unknown"} · {statement.normalized_unit ?? "Unit unknown"} · {statement.status} · Pages {statement.start_page_number}–{statement.end_page_number}</p>
      <button type="button" onClick={() => void toggle(statement.id)}>{items[statement.id] ? "Hide line items" : "View line items"}</button>
      {items[statement.id] && <ul>{items[statement.id].map((item) => <li key={item.id}>
        <strong>{item.canonical_name?.replaceAll("_", " ") ?? "Unmapped"}</strong>: {item.raw_value} ({item.raw_label}) · {item.status} · {Math.round(item.confidence_score * 100)}% · Page {item.page_number}
        <details><summary>Evidence</summary><p>{item.evidence_text}</p><p>Column: {item.raw_column_header ?? "Unknown"} · {item.currency ?? "Currency unknown"} · {item.measurement_type === "MONETARY" ? item.normalized_unit ?? "Unit unknown" : item.measurement_type}</p></details>
      </li>)}</ul>}
    </div>)}
  </section>;
}
