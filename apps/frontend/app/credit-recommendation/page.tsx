import Link from "next/link";
import { CreditRecommendationPanel } from "@/components/credit-recommendation";

export default function CreditRecommendationPage() {
  return <><Link href="/">← Platform home</Link><p className="eyebrow">Deterministic evidence preparation</p><h1>Credit Recommendation Preparation</h1><div className="validation-warning"><strong>Human decision review required</strong><span>This is a credit recommendation preparation layer, not a final lending decision. No approval, rejection, sanction amount, pricing, or credit limit has been generated.</span></div><CreditRecommendationPanel /></>;
}
