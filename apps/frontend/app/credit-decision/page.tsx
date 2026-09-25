import Link from "next/link";
import { CreditDecisionPanel } from "@/components/credit-decision";

export default function CreditDecisionPage() { return <><Link href="/">← Platform home</Link><p className="eyebrow">Human in the loop commercial credit</p><h1>Credit Decision Support</h1><div className="validation-warning"><strong>Decision support only</strong><span>A qualified credit reviewer must make and record the final lending decision. No automatic approval, rejection, sanction, pricing, or binding limit is generated.</span></div><CreditDecisionPanel /></>; }
