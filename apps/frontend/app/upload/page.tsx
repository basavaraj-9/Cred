import Link from "next/link";
import { UploadForm } from "@/components/upload-form";

export default function UploadPage() {
  return <>
    <Link href="/">← Home</Link>
    <p className="eyebrow">Document ingestion</p>
    <h1>Upload a company PDF</h1>
    <p className="intro">Upload an annual report or financial document. The file will be validated and stored with its analysis record.</p>
    <section><UploadForm /></section>
  </>;
}
