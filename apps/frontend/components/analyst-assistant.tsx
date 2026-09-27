"use client";

import { FormEvent, useState } from "react";
import { askCreditAnalyst, buildRagIndex, getRagIndex, submitAnalystFeedback } from "@/lib/api";
import type { AnalystAnswer, RagIndexStatus } from "@/types/api";

export function AnalystAssistant() {
  const [companyId, setCompanyId] = useState("");
  const [actorId, setActorId] = useState("");
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState("");
  const [period, setPeriod] = useState("");
  const [index, setIndex] = useState<RagIndexStatus | null>(null);
  const [answer, setAnswer] = useState<AnalystAnswer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function build() {
    setBusy(true); setError("");
    try { setIndex(await buildRagIndex(companyId, actorId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Index build failed"); }
    finally { setBusy(false); }
  }
  async function load() {
    setBusy(true); setError("");
    try { setIndex(await getRagIndex(companyId, actorId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Index lookup failed"); }
    finally { setBusy(false); }
  }
  async function ask(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setAnswer(null);
    try { setAnswer(await askCreditAnalyst(companyId, { actor_user_id: actorId, question, scope: scope || null, period: period || null })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Question failed"); }
    finally { setBusy(false); }
  }
  async function feedback(rating: string) {
    if (!answer) return;
    try { await submitAnalystFeedback(answer.answer_id, actorId, rating); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Feedback failed"); }
  }

  return <>
    <section><h2>Company evidence index</h2><form>
      <label>Company ID</label><input value={companyId} onChange={(event) => setCompanyId(event.target.value)} required />
      <label>Acting user ID</label><input value={actorId} onChange={(event) => setActorId(event.target.value)} required />
      <div><button type="button" disabled={busy || !companyId || !actorId} onClick={() => void build()}>Build or refresh index</button> <button type="button" disabled={busy || !companyId || !actorId} onClick={() => void load()}>Load status</button></div>
    </form>{index ? <div className="result"><span className="badge">{index.status}</span><p>{index.chunk_count} chunks from {index.source_count} sources<br /><span className="muted">{index.index_version} · {index.embedding_provider}/{index.embedding_model}</span></p></div> : null}{error ? <p className="error">{error}</p> : null}</section>
    <section><h2>Ask about persisted evidence</h2><form onSubmit={ask}>
      <label>Question</label><textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={4} maxLength={2000} required />
      <label>Statement scope (optional)</label><select value={scope} onChange={(event) => setScope(event.target.value)}><option value="">All scopes</option><option value="STANDALONE">Standalone</option><option value="CONSOLIDATED">Consolidated</option></select>
      <label>Period (optional)</label><input value={period} onChange={(event) => setPeriod(event.target.value)} placeholder="For example, FY2025" />
      <button disabled={busy || !companyId || !actorId}>Ask analyst assistant</button>
    </form></section>
    {answer ? <section><h2>Grounded answer</h2><p><span className="badge">{answer.status.replaceAll("_", " ")}</span> <strong>{Math.round(answer.confidence * 100)}% retrieval confidence</strong></p>{answer.status !== "ANSWERED" ? <div className="validation-warning"><strong>{answer.status.replaceAll("_", " ")}</strong><span>Review the cited evidence and complete the decision through the human workflow.</span></div> : null}<div className="answer-text">{answer.answer}</div><p className="muted">Citation coverage {Math.round(answer.citation_coverage_ratio * 100)}% · Unsupported claims {answer.unsupported_claim_count}</p><h3>Sources</h3><div className="card-grid">{answer.citations.map((citation) => <details className="research-card" key={citation.chunk_id}><summary>[{citation.index}] {citation.source_type.replaceAll("_", " ")}</summary><p>{citation.evidence_text}</p><p className="muted">Reference {citation.source_reference_id}<br />Page {citation.page_number ?? "N/A"} · Status {citation.status ?? "N/A"} · Confidence {citation.confidence ?? "N/A"}</p></details>)}</div><p><button onClick={() => void feedback("HELPFUL")}>Helpful</button> <button onClick={() => void feedback("NOT_HELPFUL")}>Needs work</button></p></section> : null}
  </>;
}
