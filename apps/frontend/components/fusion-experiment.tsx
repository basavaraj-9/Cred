"use client";

import { FormEvent, useState } from "react";
import { createCreditFusionExperiment } from "@/lib/api";
import type { CreditFusionExperiment } from "@/types/api";

export function FusionExperimentPanel() {
  const [assessmentId, setAssessmentId] = useState("");
  const [snapshotId, setSnapshotId] = useState("");
  const [strategy, setStrategy] = useState("WEIGHTED_BLEND");
  const [result, setResult] = useState<CreditFusionExperiment | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await createCreditFusionExperiment(assessmentId, snapshotId, strategy));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Experiment failed");
    } finally {
      setBusy(false);
    }
  }

  return <>
    <section>
      <h2>Run an internal experiment</h2>
      <form onSubmit={submit}>
        <label htmlFor="assessment">Day 10 assessment ID</label>
        <input id="assessment" value={assessmentId} onChange={(event) => setAssessmentId(event.target.value)} required />
        <label htmlFor="snapshot">Eligible ML feature snapshot ID</label>
        <input id="snapshot" value={snapshotId} onChange={(event) => setSnapshotId(event.target.value)} required />
        <label htmlFor="strategy">Strategy</label>
        <select id="strategy" value={strategy} onChange={(event) => setStrategy(event.target.value)}>
          <option value="WEIGHTED_BLEND">Weighted blend</option>
          <option value="CONSENSUS_GATED">Consensus gated</option>
        </select>
        <button disabled={busy}>{busy ? "Running…" : "Run experimental fusion"}</button>
      </form>
      {error ? <p className="error">{error}</p> : null}
    </section>
    {result ? <>
      <section>
        <h2>Experimental result</h2>
        <dl className="metric-grid">
          <div><dt>Rule score</dt><dd>{result.rule_score?.toFixed(2) ?? "Unavailable"}</dd></div>
          <div><dt>Rule risk index</dt><dd>{result.rule_risk_index?.toFixed(4) ?? "Unavailable"}</dd></div>
          <div><dt>ML probability</dt><dd>{result.ml_probability?.toFixed(4) ?? "Unavailable"}</dd></div>
          <div><dt>Rule / ML gap</dt><dd>{result.rule_ml_gap?.toFixed(4) ?? "Unavailable"}</dd></div>
          <div><dt>Hybrid risk</dt><dd>{result.experimental_hybrid_risk_index?.toFixed(4) ?? "Not produced"}</dd></div>
          <div><dt>Confidence</dt><dd>{result.fusion_confidence.toFixed(2)}</dd></div>
        </dl>
        <p><strong>Status:</strong> {result.status.replaceAll("_", " ")}</p>
        <p><strong>Production use:</strong> BLOCKED</p>
      </section>
      <section>
        <h2>Safety gates</h2>
        <ul>{Object.entries(result.readiness.checks ?? {}).map(([name, gate]) =>
          <li key={name}><span>{name.replaceAll("_", " ")}</span><strong>{gate.passed ? "PASS" : "FAIL"}</strong></li>
        )}</ul>
      </section>
      <section>
        <h2>Contribution math</h2>
        <p>Rule weight: {(result.rule_weight * 100).toFixed(0)}%</p>
        <p>ML weight: {(result.ml_weight * 100).toFixed(0)}%</p>
        <p className="muted">The rule risk index and hybrid index are not calibrated probabilities of default.</p>
      </section>
    </> : null}
  </>;
}
