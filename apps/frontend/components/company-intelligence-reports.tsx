"use client";

import { FormEvent, useState } from "react";
import { BROWSER_API_BASE_URL, API_V1_PATH } from "@/lib/config";

type Value = string | number | boolean | null | Value[] | { [key: string]: Value };
type Report = { id: string; company_name: string | null; monitoring_health: string | null; report_version: number; status: string; readiness_status: string; analytical_as_of_date: string; generated_at: string; completeness_ratio: number; evidence_coverage: number; include_credit: boolean; include_stock: boolean };
type Snapshot = { payload_hash: string; payload: { executive_summary: Record<string, Value>; sections: Record<string, { status: string; data: Value }>; disclaimers: Record<string, string>; credit_stock_separation: string; conflicts: Value; manifest: Value } };
const root = `${BROWSER_API_BASE_URL}${API_V1_PATH}/company-intelligence-reports`;
const label = (key: string) => key.replaceAll("_", " ");

function Details({ value }: { value: Value }) {
  if (value === null) return <span className="muted">Unavailable</span>;
  if (Array.isArray(value)) return value.length ? <ul>{value.map((item, i) => <li key={i}><Details value={item} /></li>)}</ul> : <span className="muted">No records</span>;
  if (typeof value === "object") return <dl>{Object.entries(value).map(([key, item]) => <div key={key}><dt><strong>{label(key)}</strong></dt><dd>{typeof item === "object" && item !== null ? <details><summary>Inspect details</summary><Details value={item} /></details> : <Details value={item} />}</dd></div>)}</dl>;
  return <span style={{ overflowWrap: "anywhere" }}>{String(value)}</span>;
}

export function CompanyIntelligenceReports({ initialPreview = null, initialTab = "summary" }: { initialPreview?: Snapshot | null; initialTab?: string } = {}) {
  const [company, setCompany] = useState("");
  const [actor, setActor] = useState("");
  const [job, setJob] = useState("");
  const [asOf, setAsOf] = useState("");
  const [credit, setCredit] = useState(true);
  const [stock, setStock] = useState(true);
  const [reports, setReports] = useState<Report[]>([]);
  const [preview, setPreview] = useState<Snapshot | null>(initialPreview);
  const [evidence, setEvidence] = useState<Value>([]);
  const [tab, setTab] = useState(initialTab);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [successor, setSuccessor] = useState("");
  const [rationale, setRationale] = useState("");

  async function request<T>(path: string, body?: Record<string, unknown>): Promise<T> {
    const response = await fetch(`${root}${path}${path.includes("?") ? "&" : "?"}actor_user_id=${encodeURIComponent(actor)}`, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...body, actor_user_id: actor }) } : { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload?.error?.message ?? `Request failed (${response.status})`);
    return payload as T;
  }
  async function run(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Report request failed"); } finally { setBusy(false); }
  }
  async function refresh() { setReports(await request<Report[]>(`?company=${encodeURIComponent(company)}`)); }
  async function inspect(id: string) {
    const [snapshot, links] = await Promise.all([request<Snapshot>(`/${id}/snapshot`), request<Value>(`/${id}/evidence`)]);
    setPreview(snapshot); setEvidence(links); setTab("summary");
  }
  function generate(event: FormEvent) {
    event.preventDefault();
    void run(async () => { const report = await request<Report>("", { company_id: company, analysis_job_id: job || null, as_of_date: asOf || null, include_credit: credit, include_stock: stock }); await refresh(); await inspect(report.id); });
  }
  const tabs = ["summary", "company_profile", "documents", "financials", "credit", "stock", "validation", "monitoring", "evidence"];
  return <>
    <section><h2>Report scope</h2><form onSubmit={generate}>
      <label htmlFor="ci-company">Company ID</label><input id="ci-company" value={company} onChange={e => setCompany(e.target.value)} required />
      <label htmlFor="ci-actor">Acting user ID</label><input id="ci-actor" value={actor} onChange={e => setActor(e.target.value)} required />
      <label htmlFor="ci-job">Analysis job ID (optional)</label><input id="ci-job" value={job} onChange={e => setJob(e.target.value)} />
      <label htmlFor="ci-date">Analytical as-of date</label><input id="ci-date" type="date" value={asOf} onChange={e => setAsOf(e.target.value)} />
      <label><input type="checkbox" checked={credit} onChange={e => setCredit(e.target.checked)} /> Include credit</label>
      <label><input type="checkbox" checked={stock} onChange={e => setStock(e.target.checked)} /> Include stock research</label>
      <button disabled={busy}>Generate snapshot</button> <button type="button" disabled={busy || !company || !actor} onClick={() => void run(refresh)}>Load versions</button>
    </form><p role="alert">{error}</p><p aria-live="polite">{busy ? "Processing report…" : ""}</p></section>
    <section><h2>Report versions</h2><div className="card-grid">{reports.map(report => <article className="research-card" key={report.id}>
      <h3>{report.company_name ?? "Company report"} · Version {report.report_version}</h3><p>{report.status} · {report.readiness_status}</p><p>Monitoring health: {report.monitoring_health ?? "Unavailable"}</p><p>As of {report.analytical_as_of_date}<br />Generated {new Date(report.generated_at).toLocaleString()}</p>
      <p>Completeness: {(Number(report.completeness_ratio) * 100).toFixed(0)}% · Evidence coverage: {(Number(report.evidence_coverage) * 100).toFixed(0)}%</p><p>Credit {report.include_credit ? "included" : "excluded"} · Stock {report.include_stock ? "included" : "excluded"}</p>
      <button disabled={busy} onClick={() => void run(() => inspect(report.id))}>Preview and evidence</button>{["READY", "NEEDS_REVIEW"].includes(report.status) && <button disabled={busy} onClick={() => void run(async () => { await request(`/${report.id}/finalize`, { rationale }); await refresh(); })}>Finalize</button>}
      {report.status === "FINALIZED" && <button disabled={busy || !successor || !rationale} onClick={() => void run(async () => { await request(`/${report.id}/supersede`, { successor_report_id: successor, rationale }); await refresh(); })}>Supersede with selected version</button>}
      <p>{["json", "pdf"].map(format => <a key={format} className="button" href={`${root}/${report.id}/artifacts/${format}?actor_user_id=${encodeURIComponent(actor)}`}>Download {format.toUpperCase()} </a>)}</p>
    </article>)}</div>{reports.length === 0 && <p>No report versions loaded.</p>}
      <label htmlFor="ci-successor">Successor version</label><select id="ci-successor" value={successor} onChange={e => setSuccessor(e.target.value)}><option value="">Select a newer report</option>{reports.map(report => <option key={report.id} value={report.id}>Version {report.report_version} · {report.status}</option>)}</select>
      <label htmlFor="ci-rationale">Finalization / supersession rationale</label><input id="ci-rationale" value={rationale} onChange={e => setRationale(e.target.value)} />
    </section>
    {preview && <section><h2>Saved report preview</h2><p className="validation-warning">{preview.payload.credit_stock_separation}</p><nav aria-label="Report sections">{tabs.map(item => <button key={item} aria-pressed={tab === item} onClick={() => setTab(item)}>{label(item)}</button>)}</nav>
      {tab === "summary" ? <><h3>Executive summary</h3><Details value={preview.payload.executive_summary} /><h3>Conflicts requiring review</h3><Details value={preview.payload.conflicts} /><details><summary>Snapshot manifest and hash</summary><p>{preview.payload_hash}</p><Details value={preview.payload.manifest} /></details></> : tab === "evidence" ? <><h3>Evidence inspection</h3><Details value={evidence} /></> : <><h3>{tab === "credit" ? "Credit Assessment" : tab === "stock" ? "Stock Intelligence Research" : label(tab)}</h3><p>{preview.payload.sections[tab]?.status ?? "UNAVAILABLE"}</p><Details value={preview.payload.sections[tab]?.data ?? null} /></>}
      {Object.values(preview.payload.disclaimers).map(text => <p className="validation-warning" key={text}>{text}</p>)}
    </section>}
  </>;
}
