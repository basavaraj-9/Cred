import Link from "next/link";
import { AnalystAssistant } from "@/components/analyst-assistant";

export default function AnalystAssistantPage() {
  return <>
    <Link href="/">← Platform home</Link>
    <p className="eyebrow">Evidence grounded analysis</p>
    <h1>Credit Analyst Assistant</h1>
    <div className="validation-warning"><strong>Advisory evidence summary</strong><span>Answers cite persisted sources and cannot approve, decline, price, sanction, book, or disburse credit.</span></div>
    <AnalystAssistant />
  </>;
}
