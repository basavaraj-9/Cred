"use client";
import { useState } from "react";
import Link from "next/link";
import { getCreditMLEvaluations } from "@/lib/api";
import type { CreditMLEvaluationSummary } from "@/types/api";

export default function ModelValidationPage() {
  const [evaluations, setEvaluations] = useState<CreditMLEvaluationSummary[]>([]);
  const [unavailable, setUnavailable] = useState(false);
  async function load() {
    try { setEvaluations(await getCreditMLEvaluations()); setUnavailable(false); }
    catch { setUnavailable(true); }
  }
  const latest = evaluations[0];
  return <>
    <Link href="/">← Home</Link>
    <p className="eyebrow">Internal model validation</p>
    <h1>Credit ML evaluation</h1><button onClick={() => void load()}>Load evaluations</button>
    <Link className="button" href="/credit-fusion">Open fusion experiments →</Link>
    <div className="validation-warning">
      <strong>Development synthetic dataset</strong>
      <span>Evaluation results are pipeline diagnostics only. Production fusion is blocked.</span>
    </div>
    {unavailable ? <section><p className="muted">The evaluation API is currently unavailable.</p></section> : null}
    {!unavailable && !latest ? <section><p className="muted">No evaluation run has been recorded.</p></section> : null}
    {latest ? <>
      <section>
        <h2>Walk-forward summary</h2>
        <dl className="metric-grid">
          <div><dt>Mode</dt><dd>{latest.window_mode.replaceAll("_", " ")}</dd></div>
          <div><dt>Valid windows</dt><dd>{latest.valid_window_count}</dd></div>
          <div><dt>Skipped windows</dt><dd>{latest.skipped_window_count}</dd></div>
          <div><dt>Status</dt><dd>{latest.status}</dd></div>
        </dl>
      </section>
      <section>
        <h2>Fusion readiness</h2>
        <p className="readiness">{latest.fusion_readiness.replaceAll("_", " ")}</p>
        <p><strong>Production fusion allowed:</strong> {latest.fusion_allowed ? "Yes" : "No"}</p>
        <p className="muted">Rule scores remain ranking diagnostics and are not calibrated probabilities of default.</p>
      </section>
      <section>
        <h2>Validation areas</h2>
        <ul>
          <li><span>Model stability</span><strong>Pipeline diagnostic</strong></li>
          <li><span>Calibration drift</span><strong>Support gated</strong></li>
          <li><span>Feature and prediction drift</span><strong>Development only</strong></li>
          <li><span>Rule versus ML</span><strong>No automatic resolution</strong></li>
        </ul>
      </section>
    </> : null}
  </>;
}
