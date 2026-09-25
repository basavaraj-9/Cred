import Link from "next/link";
import { SystemStatus } from "@/components/system-status";

export default function HealthPage() {
  return <>
    <Link href="/">← Home</Link>
    <p className="eyebrow">System health</p>
    <h1>Platform status</h1>
    <SystemStatus />
  </>;
}
