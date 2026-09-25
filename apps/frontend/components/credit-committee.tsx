"use client";
import { FormEvent, useState } from "react";
import { createCommitteePackage, listCommitteePackages } from "@/lib/api";
import type { CommitteePackage } from "@/types/api";
export function CreditCommitteePanel() {
  const [caseId, setCaseId] = useState(""); const [actorId, setActorId] = useState(""); const [packages, setPackages] = useState<CommitteePackage[]>([]); const [error, setError] = useState("");
  async function load(event: FormEvent) { event.preventDefault(); try { setPackages(await listCommitteePackages(caseId)); } catch (e) { setError(e instanceof Error ? e.message : "Committee lookup failed"); } }
  async function create() { try { await createCommitteePackage(caseId, actorId); setPackages(await listCommitteePackages(caseId)); } catch (e) { setError(e instanceof Error ? e.message : "Committee preparation failed"); } }
  return <><section><form onSubmit={load}><label>Review case ID</label><input value={caseId} onChange={(e) => setCaseId(e.target.value)} required /><label>Acting user ID</label><input value={actorId} onChange={(e) => setActorId(e.target.value)} required /><button>Load packages</button> <button type="button" onClick={create}>Prepare package</button></form>{error ? <p className="error">{error}</p> : null}</section>{packages.map((p) => <section key={p.id}><p className="eyebrow">Package v{p.package_version} · {p.status}</p><h2>{p.summary}</h2>{p.sections.map((s) => <details key={s.id}><summary>{s.title}</summary><pre>{JSON.stringify(s.payload, null, 2)}</pre></details>)}</section>)}</>;
}
