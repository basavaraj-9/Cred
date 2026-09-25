import Link from "next/link";
import { CreditReviewDashboard } from "@/components/credit-review";
export default function CreditReviewPage() { return <><Link href="/">← Platform home</Link><p className="eyebrow">Human credit governance</p><h1>Human Credit Review</h1><div className="validation-warning"><strong>Explicit human action required</strong><span>System recommendations remain advisory. Decisions recorded here do not book a facility, generate sanction documents, price credit, or disburse funds.</span></div><CreditReviewDashboard /></>; }
