"use client";

import { FormEvent, useState } from "react";
import { getResearchCandidates, getResearchFindings, getResearchSources, startCompanyResearch } from "@/lib/api";
import type { ResearchCandidates, ResearchFinding, ResearchRun, ResearchSource } from "@/types/api";

const SCOPES = ["COMPANY", "PROMOTER", "LEGAL", "RATINGS", "INDUSTRY", "SECTOR"];

export function ExternalResearchPanel() {
  const [companyId, setCompanyId] = useState("");
  const [selected, setSelected] = useState(SCOPES);
  const [refresh, setRefresh] = useState(false);
  const [run, setRun] = useState<ResearchRun | null>(null);
  const [sources, setSources] = useState<ResearchSource[]>([]);
  const [findings, setFindings] = useState<ResearchFinding[]>([]);
  const [candidates, setCandidates] = useState<ResearchCandidates | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await startCompanyResearch(companyId, selected, refresh);
      const [sourceRows, findingRows, candidateRows] = await Promise.all([
        getResearchSources(result.research_run_id), getResearchFindings(result.research_run_id),
        getResearchCandidates(result.research_run_id),
      ]);
      setRun(result); setSources(sourceRows); setFindings(findingRows); setCandidates(candidateRows);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Research failed");
    } finally { setBusy(false); }
  }

  function toggle(scope: string) {
    setSelected((items) => items.includes(scope) ? items.filter((item) => item !== scope) : [...items, scope]);
  }

  return <>
    <section><h2>Start company research</h2><form onSubmit={submit}>
      <label htmlFor="research-company">Company ID</label>
      <input id="research-company" value={companyId} onChange={(event) => setCompanyId(event.target.value)} required />
      <fieldset><legend>Research scope</legend><div className="scope-grid">{SCOPES.map((scope) => <label key={scope}><input type="checkbox" checked={selected.includes(scope)} onChange={() => toggle(scope)} /> {scope}</label>)}</div></fieldset>
      <label><input type="checkbox" checked={refresh} onChange={(event) => setRefresh(event.target.checked)} /> Retrieve a new immutable version</label>
      <button disabled={busy || selected.length === 0}>{busy ? "Researching…" : "Build external evidence"}</button>
    </form>{error ? <p className="error">{error}</p> : null}</section>
    {run ? <>
      <section><p className="eyebrow">{run.status.replaceAll("_", " ")} · {run.provider.name}</p><h2>Research coverage</h2>
        <dl className="metric-grid"><div><dt>Queries</dt><dd>{run.query_count}</dd></div><div><dt>Sources</dt><dd>{run.source_count}</dd></div><div><dt>Evidence</dt><dd>{run.evidence_count}</dd></div><div><dt>Findings</dt><dd>{run.finding_count}</dd></div><div><dt>Review</dt><dd>{run.review_count}</dd></div></dl>
        <p className="muted">No result does not establish low risk. External findings have not changed the Day 15 assessment.</p></section>
      <section><h2>Findings</h2>{findings.length ? <div className="card-grid">{findings.map((item) => <article className="research-card" key={item.finding_id}><p className="eyebrow">{item.category} · {item.status.replaceAll("_", " ")}</p><h3>{item.finding_code.replaceAll("_", " ")}</h3><p>{item.summary}</p><dl><dt>Impact</dt><dd>{item.impact}</dd><dt>Confidence</dt><dd>{(item.confidence * 100).toFixed(0)}%</dd><dt>Sources</dt><dd>{item.source_count}</dd><dt>5 Cs candidate</dt><dd>{item.candidate_section ?? "None"}</dd></dl></article>)}</div> : <p>No verified findings.</p>}</section>
      <section><h2>Sources</h2><div className="card-grid">{sources.map((item) => <article className="research-card" key={item.source_id}><p className="eyebrow">Tier {item.source_tier} · {item.status.replaceAll("_", " ")}</p><h3>{item.title}</h3><p>{item.publisher} · {item.source_type.replaceAll("_", " ")}</p><dl><dt>Quality</dt><dd>{(item.quality * 100).toFixed(0)}%</dd><dt>Published</dt><dd>{item.publication_date ?? "Unknown"}</dd><dt>Event</dt><dd>{item.event_date ?? "Unknown"}</dd><dt>Retrieved</dt><dd>{new Date(item.retrieved_at).toLocaleDateString()}</dd><dt>Freshness</dt><dd>{item.freshness}</dd></dl>{item.status !== "FAILED" ? <a href={item.url} target="_blank" rel="noreferrer">Open source</a> : <p className="error">{item.error_code}</p>}</article>)}</div></section>
      <section><h2>5 Cs candidates</h2><p><strong>Character:</strong> {candidates?.character.length ?? 0} · <strong>Conditions:</strong> {candidates?.conditions.length ?? 0}</p><p className="muted">Candidate evidence is shown for analyst review and is not applied automatically.</p></section>
    </> : null}
  </>;
}
