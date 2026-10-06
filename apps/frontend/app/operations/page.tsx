"use client";
import { useState } from "react";
import { apiFetch, sessionIdentity } from "@/lib/http";
import { API_V1_PATH, BROWSER_API_BASE_URL } from "@/lib/config";

type Job = { id: string; job_type: string; status: string; attempt_count: number; error_code: string | null; result_json: unknown };
const root = `${BROWSER_API_BASE_URL}${API_V1_PATH}`;
export default function Operations() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [runtime, setRuntime] = useState<unknown>(null);
  const [company, setCompany] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    const response = await apiFetch(`${root}/jobs`);
    if (!response.ok) throw new Error("Unable to load jobs.");
    setJobs(await response.json());
    if (sessionIdentity()?.role === "ADMIN") {
      const health = await apiFetch(`${root}/admin/runtime`);
      if (health.ok) setRuntime(await health.json());
    }
  }
  async function run(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); } catch (cause) { setError(cause instanceof Error ? cause.message : "Request failed"); }
    finally { setBusy(false); }
  }
  async function change(id: string, action: string) {
    const response = await apiFetch(`${root}/jobs/${id}/${action}`, { method: "POST" });
    if (!response.ok) throw new Error("This job cannot be changed in its current state.");
    await load();
  }
  return <>
    <h1>Jobs and system status</h1>
    <button disabled={busy} onClick={() => void run(load)}>Refresh status</button>
    <p role="alert">{error}</p>
    <section><h2>Queue a company report</h2><form onSubmit={event => {
      event.preventDefault(); void run(async () => {
        const response = await apiFetch(`${root}/jobs`, { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ job_type: "REPORT_360", company_id: company, idempotency_key: crypto.randomUUID() }) });
        if (!response.ok) throw new Error("Report could not be queued.");
        await load();
      });
    }}><label>Company ID <input value={company} onChange={event => setCompany(event.target.value)} required /></label>
      <button disabled={busy}>Queue report</button></form></section>
    <section><h2>Your jobs</h2><p>Refresh to see progress. Completed report versions are available in the company report workspace.</p>
      {jobs.map(job => <article key={job.id}><h3>{job.job_type.replaceAll("_", " ")}</h3>
        <p>{job.status} · Attempts: {job.attempt_count}</p><p>{job.error_code}</p>
        {!['COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT'].includes(job.status) && <button disabled={busy} onClick={() => void run(() => change(job.id, "cancel"))}>Cancel</button>}
        {['FAILED', 'TIMED_OUT'].includes(job.status) && <button disabled={busy} onClick={() => void run(() => change(job.id, "retry"))}>Retry if eligible</button>}
      </article>)}
    </section>
    {runtime !== null && <section><h2>Administrator runtime status</h2><pre>{JSON.stringify(runtime, null, 2)}</pre></section>}
  </>;
}
