import Link from "next/link";
import { ExternalResearchPanel } from "@/components/external-research";

export default function ResearchPage() {
  return <>
    <Link href="/">← Platform home</Link>
    <p className="eyebrow">Traceable external intelligence</p>
    <h1>External Research</h1>
    <div className="validation-warning"><strong>Evidence and candidates only</strong><span>Legal claims preserve their reported status. No lending decision, stock recommendation, or automatic 5 Cs refresh is generated.</span></div>
    <ExternalResearchPanel />
  </>;
}
