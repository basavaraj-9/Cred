import Link from "next/link";
import { CreditReports } from "@/components/credit-reports";

export default function CreditReportsPage() {
  return <>
    <Link href="/">← Platform home</Link>
    <p className="eyebrow">Controlled credit reporting</p>
    <h1>CAM and Evidence Exports</h1>
    <div className="validation-warning"><strong>Reports reproduce a fixed review snapshot</strong><span>Generation adds no new score, recommendation, approval, pricing, sanction, or disbursement decision.</span></div>
    <CreditReports />
  </>;
}
