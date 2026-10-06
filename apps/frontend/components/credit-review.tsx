"use client";
import { useRuntimeActor } from "@/lib/use-runtime-actor";
import { FormEvent, useEffect, useState } from "react";
import { assignCreditReviewCase, createCreditReviewCase, listCreditReviewCases, recordHumanDecision, startCreditReview } from "@/lib/api";
import type { CreditReviewCase } from "@/types/api";

export function CreditReviewDashboard() {
  const [cases, setCases] = useState<CreditReviewCase[]>([]); const [decisionId, setDecisionId] = useState(""); const [actorId, setActorId] = useRuntimeActor(); const [reviewerId, setReviewerId] = useState(""); const [rationale, setRationale] = useState(""); const [error, setError] = useState("");
  const refresh = () => listCreditReviewCases().then(setCases).catch((e: Error) => setError(e.message));
  useEffect(() => { void refresh(); }, []);
  async function create(event: FormEvent) { event.preventDefault(); try { await createCreditReviewCase(decisionId, actorId); await refresh(); } catch (e) { setError(e instanceof Error ? e.message : "Review action failed"); } }
  async function act(caseId: string, action: "assign" | "start" | "committee") { try { if (action === "assign") await assignCreditReviewCase(caseId, actorId, reviewerId); else if (action === "start") await startCreditReview(caseId, actorId); else await recordHumanDecision(caseId, { actor_user_id: actorId, decision: "REFERRED_TO_COMMITTEE", decision_rationale: rationale }); await refresh(); } catch (e) { setError(e instanceof Error ? e.message : "Review action failed"); } }
  return <><section><h2>Create review case</h2><form onSubmit={create}><label>Day 18 decision ID</label><input value={decisionId} onChange={(e) => setDecisionId(e.target.value)} required /><label>Acting user ID</label><input value={actorId} onChange={(e) => setActorId(e.target.value)} required /><label>Reviewer user ID</label><input value={reviewerId} onChange={(e) => setReviewerId(e.target.value)} /><label>Decision or referral rationale</label><textarea value={rationale} onChange={(e) => setRationale(e.target.value)} /><button>Create case</button></form>{error ? <p className="error">{error}</p> : null}</section><section><h2>Review cases</h2>{cases.length ? <ul>{cases.map((c) => <li key={c.id}><span><strong>{c.workflow_status.replaceAll("_", " ")}</strong><br />Case {c.id}<br />Reviewer: {c.primary_reviewer_id ?? "Unassigned"}<br />Human decision: {c.human_decision?.decision ?? "NOT RECORDED"}{c.updated_analysis_available ? <><br /><strong>Updated analysis available</strong></> : null}</span><span><button onClick={() => act(c.id, "assign")}>Assign</button> <button onClick={() => act(c.id, "start")}>Start review</button> <button onClick={() => act(c.id, "committee")}>Refer to committee</button></span></li>)}</ul> : <p>No review cases.</p>}</section></>;
}
