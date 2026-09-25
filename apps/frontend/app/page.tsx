import Link from "next/link";

export default function Home() {
  return <>
    <p className="eyebrow">Company Intelligence Platform</p>
    <h1>Reliable foundations for informed decisions.</h1>
    <p className="intro">Upload a company PDF to create an analysis record. Document parsing and financial analysis will follow in later stages.</p>
    <Link className="button" href="/upload">Upload a PDF →</Link>
    {" "}
    <Link className="button" href="/health">View system status →</Link>
    {" "}
    <Link className="button" href="/model-validation">Model validation →</Link>
    {" "}
    <Link className="button" href="/research">External research →</Link>
    {" "}
    <Link className="button" href="/credit-recommendation">Credit review preparation →</Link>
    {" "}
    <Link className="button" href="/credit-decision">Credit decision support →</Link>
    {" "}
    <Link className="button" href="/credit-review">Human credit review →</Link>
    {" "}
    <Link className="button" href="/credit-committee">Credit committee →</Link>
    {" "}
    <Link className="button" href="/credit-reports">Credit reports →</Link>
  </>;
}
