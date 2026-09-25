import Link from "next/link";
import { CreditCommitteePanel } from "@/components/credit-committee";
export default function CreditCommitteePage() { return <><Link href="/credit-review">← Human credit review</Link><p className="eyebrow">Structured governance package</p><h1>Credit Committee Preparation</h1><div className="validation-warning"><strong>Preparation only</strong><span>A READY committee package is not a credit approval or sanctioned facility.</span></div><CreditCommitteePanel /></>; }
