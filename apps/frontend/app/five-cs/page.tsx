import Link from "next/link";
import { FiveCsAssessmentPanel } from "@/components/five-cs-assessment";

export default function FiveCsPage() {
  return <>
    <Link href="/upload">← Document workflow</Link>
    <p className="eyebrow">Evidence-backed underwriting structure</p>
    <h1>5 Cs of Credit</h1>
    <div className="validation-warning">
      <strong>No total credit score or lending decision</strong>
      <span>Unavailable promoter, bureau, legal, collateral valuation, industry, regulatory, and macroeconomic evidence remains explicit.</span>
    </div>
    <FiveCsAssessmentPanel />
  </>;
}
