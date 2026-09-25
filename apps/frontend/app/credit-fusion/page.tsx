import Link from "next/link";
import { FusionExperimentPanel } from "@/components/fusion-experiment";

export default function CreditFusionPage() {
  return <>
    <Link href="/model-validation">← Model validation</Link>
    <p className="eyebrow">Internal development experiment</p>
    <h1>Experimental rule + ML fusion</h1>
    <div className="validation-warning">
      <strong>Pipeline-validation output only</strong>
      <span>The ML model uses synthetic development data. No result on this page may be used for a real lending decision.</span>
    </div>
    <FusionExperimentPanel />
  </>;
}
