"use client";

import { FormEvent, useState } from "react";
import { analyzeFiveCs, getFiveCsEvidence, getFiveCsReviewItems, refreshFiveCs } from "@/lib/api";
import type { FiveCsAssessment, FiveCsEvidence, FiveCsReviewItem } from "@/types/api";

const ORDER = ["character", "capacity", "capital", "collateral", "conditions"];

export function FiveCsAssessmentPanel() {
  const [documentId, setDocumentId] = useState("");
  const [scope, setScope] = useState("CONSOLIDATED");
  const [assessment, setAssessment] = useState<FiveCsAssessment | null>(null);
  const [baseAssessment, setBaseAssessment] = useState<FiveCsAssessment | null>(null);
  const [researchRunId, setResearchRunId] = useState("");
  const [evidence, setEvidence] = useState<FiveCsEvidence[]>([]);
  const [reviews, setReviews] = useState<FiveCsReviewItem[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await analyzeFiveCs(documentId, scope);
      const [sourceRows, reviewRows] = await Promise.all([
        getFiveCsEvidence(result.assessment_id),
        getFiveCsReviewItems(result.assessment_id),
      ]);
      setAssessment(result);
      setEvidence(sourceRows);
      setReviews(reviewRows);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "5 Cs analysis failed");
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    if (!assessment || !researchRunId) return;
    setBusy(true);
    setError("");
    try {
      const result = await refreshFiveCs(assessment.assessment_id, researchRunId);
      const [sourceRows, reviewRows] = await Promise.all([getFiveCsEvidence(result.refreshed_assessment_id), getFiveCsReviewItems(result.refreshed_assessment_id)]);
      setBaseAssessment(assessment);
      setAssessment(result.assessment);
      setEvidence(sourceRows);
      setReviews(reviewRows);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Research refresh failed");
    } finally { setBusy(false); }
  }

  return <>
    <section>
      <h2>Analyze persisted evidence</h2>
      <form onSubmit={submit}>
        <label htmlFor="five-cs-document">Document ID</label>
        <input id="five-cs-document" value={documentId} onChange={(event) => setDocumentId(event.target.value)} required />
        <label htmlFor="five-cs-scope">Statement scope</label>
        <select id="five-cs-scope" value={scope} onChange={(event) => setScope(event.target.value)}>
          <option value="CONSOLIDATED">Consolidated</option>
          <option value="STANDALONE">Standalone</option>
        </select>
        <button disabled={busy}>{busy ? "Analyzing…" : "Build 5 Cs evidence"}</button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {assessment && assessment.engine_version === "five_cs_engine_v1" ? <div><label htmlFor="research-run">Research run ID</label><input id="research-run" value={researchRunId} onChange={(event) => setResearchRunId(event.target.value)} placeholder="Day 16 research run" /><button type="button" onClick={refresh} disabled={busy || !researchRunId}>Refresh with research</button></div> : null}
    </section>
    {assessment ? <>
      <section>
        <p className="eyebrow">{assessment.scope} · {assessment.status.replaceAll("_", " ")}</p>
        <h2>Evidence completeness</h2>
        <p><strong>{(assessment.overall_completeness * 100).toFixed(0)}%</strong> complete · {(assessment.overall_confidence * 100).toFixed(0)}% confidence</p>
        {assessment.stale ? <p className="error">A newer Day 10 assessment exists. Run the 5 Cs analysis again.</p> : null}
        <p className="muted">{assessment.disclaimer}</p>
        {baseAssessment ? <div className="validation-warning"><strong>Base vs refreshed 5 Cs</strong><span>Base {baseAssessment.status.replaceAll("_", " ")} · {(baseAssessment.overall_completeness * 100).toFixed(0)}% complete → Refreshed {assessment.status.replaceAll("_", " ")} · {(assessment.overall_completeness * 100).toFixed(0)}% complete. Character and Conditions may use eligible research; Capacity, Capital, and Collateral retain validated financial evidence.</span></div> : null}
      </section>
      {ORDER.map((name) => {
        const section = assessment.sections[name];
        const rows = evidence.filter((item) => item.section.toLowerCase() === name);
        if (!section) return null;
        return <section key={name}>
          <p className="eyebrow">{section.status.replaceAll("_", " ")}</p>
          <h2>{name[0].toUpperCase() + name.slice(1)}</h2>
          <p>{(section.completeness * 100).toFixed(0)}% complete · {(section.confidence * 100).toFixed(0)}% confidence</p>
          <p>{section.summary}</p>
          {(["POSITIVE", "NEGATIVE", "REVIEW"] as const).map((impact) => {
            const items = rows.filter((item) => item.impact === impact);
            return items.length ? <div key={impact}><h3>{impact === "REVIEW" ? "Review or missing evidence" : `${impact.toLowerCase()} evidence`}</h3><ul>{items.map((item) => <li key={item.evidence_id}><span>{item.title}</span><strong>{item.normalized_value ?? item.status.replaceAll("_", " ")}</strong>{item.source_url ? <a href={item.source_url}>View source{item.page_number ? ` · page ${item.page_number}` : ""}</a> : null}</li>)}</ul></div> : null;
          })}
        </section>;
      })}
      <section><h2>Human review</h2>{reviews.length ? <ul>{reviews.map((item) => <li key={item.review_item_id}><span>{item.section}: {item.message}</span><strong>{item.priority}</strong></li>)}</ul> : <p>No open review items.</p>}</section>
    </> : null}
  </>;
}
