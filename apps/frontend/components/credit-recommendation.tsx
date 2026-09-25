"use client";

import { FormEvent, useState } from "react";
import { prepareCreditRecommendation } from "@/lib/api";
import type { CreditRecommendation } from "@/types/api";

const CATEGORIES = ["STRENGTH", "RISK", "CRITICAL_RISK", "MISSING_EVIDENCE", "REVIEW_REQUIRED", "EXPERIMENTAL_CONTEXT"];

export function CreditRecommendationPanel() {
  const [documentId, setDocumentId] = useState("");
  const [scope, setScope] = useState("CONSOLIDATED");
  const [fiveCsId, setFiveCsId] = useState("");
  const [researchRunId, setResearchRunId] = useState("");
  const [fusionId, setFusionId] = useState("");
  const [result, setResult] = useState<CreditRecommendation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { setResult(await prepareCreditRecommendation(documentId, scope, fiveCsId, researchRunId, fusionId)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Preparation failed"); }
    finally { setBusy(false); }
  }

  return <>
    <section><h2>Prepare review inputs</h2><form onSubmit={submit}>
      <label htmlFor="recommendation-document">Document ID</label><input id="recommendation-document" value={documentId} onChange={(e) => setDocumentId(e.target.value)} required />
      <label htmlFor="recommendation-scope">Statement scope</label><select id="recommendation-scope" value={scope} onChange={(e) => setScope(e.target.value)}><option value="CONSOLIDATED">Consolidated</option><option value="STANDALONE">Standalone</option></select>
      <label htmlFor="recommendation-five-cs">Refreshed 5 Cs ID (optional)</label><input id="recommendation-five-cs" value={fiveCsId} onChange={(e) => setFiveCsId(e.target.value)} />
      <label htmlFor="recommendation-research">Research run ID (optional)</label><input id="recommendation-research" value={researchRunId} onChange={(e) => setResearchRunId(e.target.value)} />
      <label htmlFor="recommendation-fusion">Experimental fusion ID (optional)</label><input id="recommendation-fusion" value={fusionId} onChange={(e) => setFusionId(e.target.value)} />
      <button disabled={busy}>{busy ? "Preparing…" : "Prepare credit review"}</button>
    </form>{error ? <p className="error">{error}</p> : null}</section>
    {result ? <>
      <section><p className="eyebrow">Preparation status</p><h2>{result.status.replaceAll("_", " ")}</h2><p><strong>{(result.overall_confidence * 100).toFixed(0)}%</strong> confidence · {(result.overall_completeness * 100).toFixed(0)}% complete</p><p>{result.summary}</p><p className="muted">{result.disclaimer}</p></section>
      {CATEGORIES.map((category) => { const rows = result.factors.filter((item) => item.category === category); return rows.length ? <section key={category}><h2>{category.replaceAll("_", " ")}</h2><ul>{rows.map((item) => <li key={item.factor_id}><span><strong>{item.title}</strong><br />{item.description}</span><small>{Math.round(item.confidence * 100)}% · {item.source_type.replaceAll("_", " ")}</small></li>)}</ul></section> : null; })}
      <section><h2>Human review items</h2>{result.review_items.length ? <ul>{result.review_items.map((item) => <li key={item.review_item_id}><span>{item.message}</span><strong>{item.blocking ? "BLOCKING" : item.category}</strong></li>)}</ul> : <p>No open review items.</p>}</section>
      <section><h2>Lineage</h2><p>Day 10: {result.lineage.credit_assessment_id}<br />Refreshed 5 Cs: {result.lineage.five_cs_assessment_id}<br />Research: {result.lineage.research_run_id}</p>{result.lineage.fusion_experiment_id ? <p className="muted">Experimental context: {result.lineage.fusion_experiment_id}. This does not change readiness or production confidence.</p> : null}</section>
    </> : null}
  </>;
}
