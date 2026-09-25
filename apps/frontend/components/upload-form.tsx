"use client";

import { useState, type FormEvent } from "react";
import { FinancialStatements } from "@/components/financial-statements";
import { classifyDomain, extractCompanyProfile, getDomainClassificationEvidence, getProfileEvidence, parseDocument, uploadDocument } from "@/lib/api";
import type { ClassificationEvidence, CompanyProfile, DomainClassification, ParseSummary, ProfileEvidence, UploadResult } from "@/types/api";

type UploadState = "idle" | "validating" | "uploading" | "success" | "error";

export function UploadForm() {
  const [companyName, setCompanyName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>("idle");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [parseState, setParseState] = useState<"idle" | "parsing" | "parsed" | "partial" | "failed">("idle");
  const [parseMessage, setParseMessage] = useState("");
  const [summary, setSummary] = useState<ParseSummary | null>(null);
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [profileState, setProfileState] = useState<"idle" | "extracting" | "done" | "error">("idle");
  const [profileMessage, setProfileMessage] = useState("");
  const [evidence, setEvidence] = useState<ProfileEvidence[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [classification, setClassification] = useState<DomainClassification | null>(null);
  const [classificationEvidence, setClassificationEvidence] = useState<ClassificationEvidence[]>([]);
  const [classificationState, setClassificationState] = useState<"idle" | "classifying" | "done" | "error">("idle");
  const [classificationMessage, setClassificationMessage] = useState("");
  const [showClassificationEvidence, setShowClassificationEvidence] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("validating");
    setMessage("");
    setResult(null);
    setSummary(null);
    setParseState("idle");
    setParseMessage("");
    setProfile(null);
    setProfileState("idle");
    setEvidence([]);
    setSelectedEvidenceId(null);
    setClassification(null);
    setClassificationEvidence([]);
    setClassificationState("idle");
    setClassificationMessage("");
    setShowClassificationEvidence(false);
    if (!companyName.trim()) {
      setState("error");
      setMessage("Enter the company legal name.");
      return;
    }
    if (!file || !file.name.toLowerCase().endsWith(".pdf")) {
      setState("error");
      setMessage("Choose a PDF file.");
      return;
    }
    if (file.size === 0) {
      setState("error");
      setMessage("The selected file is empty.");
      return;
    }
    setState("uploading");
    try {
      const uploaded = await uploadDocument(companyName.trim(), displayName, file);
      setResult(uploaded);
      setState("success");
      setMessage(uploaded.message);
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Upload failed. Please try again.");
    }
  }

  async function parseUploadedDocument() {
    if (!result) return;
    setParseState("parsing");
    setParseMessage("");
    try {
      const parsed = await parseDocument(result.document.id);
      setSummary(parsed);
      setParseState(parsed.parser_status === "PARSED" ? "parsed" : "partial");
    } catch (error) {
      setParseState("failed");
      setParseMessage(error instanceof Error ? error.message : "Parsing failed. Please try again.");
    }
  }

  async function extractProfile() {
    if (!result) return;
    setProfileState("extracting");
    setProfileMessage("");
    setClassification(null);
    try {
      const extracted = await extractCompanyProfile(result.document.id);
      setProfile(extracted);
      setEvidence(await getProfileEvidence(extracted.profile_id));
      setProfileState("done");
    } catch (error) {
      setProfileState("error");
      setProfileMessage(error instanceof Error ? error.message : "Profile extraction failed.");
    }
  }

  async function runClassification() {
    if (!profile) return;
    setClassificationState("classifying");
    setClassificationMessage("");
    try {
      const predicted = await classifyDomain(profile.profile_id);
      setClassification(predicted);
      setClassificationEvidence(await getDomainClassificationEvidence(predicted.classification_id));
      setClassificationState("done");
    } catch (error) {
      setClassificationState("error");
      setClassificationMessage(error instanceof Error ? error.message : "Domain classification failed.");
    }
  }

  const fieldLabels: Record<string, string> = {
    legal_name: "Legal name", reporting_period: "Reporting period", business_description: "Business description",
    headquarters: "Headquarters", registered_office: "Registered office", country: "Country", website: "Website",
    product: "Products", service: "Services", operating_segment: "Operating segments",
  };
  const selectedEvidence = evidence.find((item) => item.id === selectedEvidenceId);

  return <form onSubmit={submit}>
    <label htmlFor="company-name">Company Legal Name</label>
    <input id="company-name" value={companyName} onChange={(event) => setCompanyName(event.target.value)} required maxLength={255} />
    <label htmlFor="display-name">Display Name <span className="muted">(optional)</span></label>
    <input id="display-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} maxLength={255} />
    <label htmlFor="document-file">PDF document</label>
    <input id="document-file" type="file" accept=".pdf,application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required />
    {file && <p className="muted">Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)</p>}
    <button type="submit" disabled={state === "uploading" || state === "validating"}>
      {state === "uploading" ? "Uploading…" : "Upload document"}
    </button>
    {state === "validating" && <p role="status">Validating selection…</p>}
    {state === "uploading" && <p role="status">Uploading document…</p>}
    {message && <p role={state === "error" ? "alert" : "status"} className={state === "error" ? "error" : "success"}>{message}</p>}
    {result && <div className="result">
      <p><strong>Analysis ID:</strong> {result.analysis_id}</p>
      <p><strong>Document ID:</strong> {result.document.id}</p>
      <p><strong>Status:</strong> {result.document.status}</p>
      <p><strong>SHA-256:</strong> <code>{result.document.sha256_hash}</code></p>
      <button type="button" onClick={parseUploadedDocument} disabled={parseState === "parsing"}>
        {parseState === "parsing" ? "Parsing…" : "Parse document"}
      </button>
      {parseState === "parsing" && <p role="status">Parsing the PDF page by page…</p>}
      {parseMessage && <p role="alert" className="error">{parseMessage}</p>}
      {summary && <div className="result" role="status">
        <p><strong>Parser status:</strong> {summary.parser_status}</p>
        <p><strong>Pages:</strong> {summary.page_count}</p>
        <p><strong>Native text:</strong> {summary.native_text_pages} · <strong>OCR:</strong> {summary.ocr_pages} · <strong>Blank:</strong> {summary.blank_pages} · <strong>Failed:</strong> {summary.failed_pages}</p>
        <p><strong>Extraction method:</strong> {summary.extraction_method}</p>
        <p><strong>Parser:</strong> {summary.parser_version}</p>
        <button type="button" onClick={extractProfile} disabled={profileState === "extracting" || summary.native_text_pages + summary.ocr_pages === 0}>
          {profileState === "extracting" ? "Extracting profile…" : "Extract company profile"}
        </button>
        {profileState === "extracting" && <p role="status">Reading stored page text and mapping evidence…</p>}
        {profileMessage && <p role="alert" className="error">{profileMessage}</p>}
      </div>}
      {summary && summary.native_text_pages + summary.ocr_pages > 0 && <FinancialStatements key={result.document.id} documentId={result.document.id} />}
      {profile && <section className="result" aria-label="Company profile">
        <h2>Company profile</h2>
        <p><strong>Status:</strong> {profile.status} · <strong>Extractor:</strong> {profile.extractor_version}</p>
        {profile.identity_match_status !== "MATCHED" && <p role="alert" className="error">
          COMPANY IDENTITY REVIEW REQUIRED · Uploaded name: {profile.uploaded_company_name} · Match: {profile.identity_match_status}
        </p>}
        {Object.entries(fieldLabels).map(([key, label]) => <div key={key}>
          <h3>{label}</h3>
          {(profile.fields[key] ?? []).length === 0 ? <p className="muted">Unavailable in this document</p> :
            <ul>{profile.fields[key].map((field) => <li key={field.id}>
              <span>{field.value}</span> · {field.status} · {Math.round(field.confidence * 100)}% · Page {field.page_number}{" "}
              <button type="button" onClick={() => setSelectedEvidenceId(selectedEvidenceId === field.id ? null : field.id)}>View evidence</button>
            </li>)}</ul>}
        </div>)}
        {selectedEvidence && <aside className="result" aria-label="Field evidence">
          <strong>Evidence · Page {selectedEvidence.page_number}</strong>
          <p>{selectedEvidence.evidence_text}</p>
          <p className="muted">Method: {selectedEvidence.extraction_method} · Confidence: {Math.round(selectedEvidence.confidence_score * 100)}%</p>
        </aside>}
        <button type="button" onClick={runClassification} disabled={classificationState === "classifying"}>
          {classificationState === "classifying" ? "Classifying…" : "Classify sector and domain"}
        </button>
        {classificationState === "classifying" && <p role="status">Classifying the evidenced business profile…</p>}
        {classificationMessage && <p role="alert" className="error">{classificationMessage}</p>}
      </section>}
      {classification && <section className="result" aria-label="Domain classification">
        <h2>Domain classification</h2>
        {classification.status !== "VERIFIED" && <p role="alert" className="error">
          {classification.status === "UNAVAILABLE" ? "No reliable classification; the candidate labels below require review." : "Classification requires review."} · {classification.status}
        </p>}
        <ul>
          {(["sector", "industry", "domain", "sub_domain"] as const).map((level) => <li key={level}>
            <strong>{level.replaceAll("_", " ")}:</strong> {classification[level].label} · {Math.round(classification[level].confidence * 100)}%
          </li>)}
        </ul>
        <p><strong>Overall confidence:</strong> {Math.round(classification.overall_confidence * 100)}% · <strong>Status:</strong> {classification.status}</p>
        {classification.alternative_sub_domain && <p><strong>Alternative:</strong> {classification.alternative_sub_domain.label} · {Math.round(classification.alternative_sub_domain.confidence * 100)}%</p>}
        <p><strong>Model:</strong> {classification.model_version} · <strong>Dataset:</strong> {classification.dataset_version} · <strong>Taxonomy:</strong> {classification.taxonomy_version}</p>
        <p className="muted">Development baseline trained on a small synthetic dataset; confidence is not a production accuracy guarantee.</p>
        <button type="button" onClick={() => setShowClassificationEvidence(!showClassificationEvidence)}>{showClassificationEvidence ? "Hide evidence" : "View evidence"}</button>
        {showClassificationEvidence && <ul>{classificationEvidence.map((item) => <li key={item.extracted_field_id}>
          <strong>{item.field_name.replaceAll("_", " ")} · Page {item.page_number}</strong><p>{item.evidence_text}</p>
        </li>)}</ul>}
      </section>}
    </div>}
  </form>;
}
