import Link from "next/link";
import { StockIntelligence } from "@/components/stock-intelligence";
export default function Page(){return <><Link href="/">← Platform home</Link><p className="eyebrow">Day 22 · Indian listed universe</p><h1>Peer Discovery and Market Data</h1><div className="validation-warning"><strong>Business comparability only</strong><span>No BUY, SELL, HOLD, valuation, target price, return forecast, or investment recommendation is generated.</span></div><StockIntelligence/></>}
