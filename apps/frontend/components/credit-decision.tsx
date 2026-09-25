"use client";

import { FormEvent, useState } from "react";
import { prepareCreditDecision } from "@/lib/api";
import type { CreditDecisionSupport } from "@/types/api";

function money(value: string | null, currency: string) { return value === null ? "Unavailable" : `${currency} ${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`; }

export function CreditDecisionPanel() {
  const [documentId, setDocumentId] = useState(""); const [scope, setScope] = useState("CONSOLIDATED"); const [recommendationId, setRecommendationId] = useState("");
  const [result, setResult] = useState<CreditDecisionSupport | null>(null); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(""); try { setResult(await prepareCreditDecision(documentId, scope, recommendationId)); } catch (caught) { setError(caught instanceof Error ? caught.message : "Decision support failed"); } finally { setBusy(false); } }
  return <><section><h2>Prepare human review package</h2><form onSubmit={submit}><label htmlFor="decision-document">Document ID</label><input id="decision-document" value={documentId} onChange={(e) => setDocumentId(e.target.value)} required /><label htmlFor="decision-scope">Scope</label><select id="decision-scope" value={scope} onChange={(e) => setScope(e.target.value)}><option>CONSOLIDATED</option><option>STANDALONE</option></select><label htmlFor="decision-recommendation">Day 17 preparation ID (optional)</label><input id="decision-recommendation" value={recommendationId} onChange={(e) => setRecommendationId(e.target.value)} /><button disabled={busy}>{busy ? "Preparing…" : "Prepare decision support"}</button></form>{error ? <p className="error">{error}</p> : null}</section>
  {result ? <><section><p className="eyebrow">Credit decision support</p><h2>{result.system_recommendation.replaceAll("_", " ")}</h2><p><strong>Human decision: {result.human_decision_status.replaceAll("_", " ")}</strong></p><p>{(result.confidence * 100).toFixed(0)}% confidence · {(result.completeness * 100).toFixed(0)}% complete</p><p>{result.summary}</p><div className="validation-warning"><strong>Human reviewer required</strong><span>{result.warning}</span></div></section>
  <section><h2>Policy gates</h2><ul>{result.gates.map((g) => <li key={g.gate_id}><span><strong>{g.category.replaceAll("_", " ")}</strong><br />{g.message}</span><strong>{g.status.replaceAll("_", " ")}</strong></li>)}</ul></section>
  <section><h2>Open policy exceptions</h2>{result.exceptions.length ? <ul>{result.exceptions.map((e) => <li key={e.exception_id}><span><strong>{e.exception_code.replaceAll("_", " ")}</strong><br />Required authority: {e.required_authority}</span><strong>{e.status}</strong></li>)}</ul> : <p>No open policy exceptions.</p>}</section>
  <section><h2>Review checklist</h2><ul>{result.review_items.map((i) => <li key={i.review_item_id}><span>{i.message}</span><strong>{i.priority}</strong></li>)}</ul></section>
  {result.limit_preparation ? <section><p className="eyebrow">Proposed limit preparation</p><h2>{money(result.limit_preparation.analytical_ceiling, result.limit_preparation.currency)}</h2><p>Status: {result.limit_preparation.status} · Confidence: {(result.limit_preparation.confidence * 100).toFixed(0)}%</p><ul>{result.limit_preparation.methods.map((m) => <li key={m.method_id}><span>{m.method_code.replaceAll("_", " ")}</span><strong>{money(m.calculated_limit, result.limit_preparation!.currency)}</strong></li>)}</ul><div className="validation-warning"><strong>Analytical preparation only</strong><span>{result.limit_preparation.warning}</span></div></section> : null}
  <section><h2>Experimental ML context</h2><p>Lifecycle: PIPELINE_VALIDATION_ONLY<br />Decision weight: NONE<br />Production impact: NONE</p></section></> : null}</>;
}
