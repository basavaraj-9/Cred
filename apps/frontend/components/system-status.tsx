"use client";
import { useState } from "react";
import { getHealth, getStatus } from "@/lib/api";
import type { HealthResponse, StatusResponse } from "@/types/api";

async function loadSystemStatus(): Promise<[HealthResponse, StatusResponse] | null> {
  try {
    return await Promise.all([getHealth(), getStatus()]);
  } catch {
    return null;
  }
}

export function SystemStatus() {
  const [result, setResult] = useState<[HealthResponse, StatusResponse] | null>(null);
  if (!result) {
    return <section role="status"><p className="badge unavailable">API unavailable</p><p>Sign in and load platform status.</p><button onClick={() => void loadSystemStatus().then(setResult)}>Load status</button></section>;
  }
  const [health, status] = result;
  const labels: Record<string, string> = {
    api: "API",
    database: "Database",
    file_upload: "File Upload",
    local_storage: "Local Storage",
    duplicate_detection: "Duplicate Detection",
    pdf_parsing: "PDF Parsing",
    page_level_extraction: "Page-Level Extraction",
    company_identity_extraction: "Company Identity Extraction",
    business_profile_extraction: "Business Profile Extraction",
    evidence_mapping: "Evidence Mapping",
    domain_ml_dataset: "Domain ML Dataset",
    domain_model_training: "Domain Model Training",
    ocr_fallback: "OCR Fallback",
    document_intelligence: "Document Intelligence",
    domain_classification: "Domain Classification",
    financial_engine: "Financial Engine",
    financial_statement_schema: "Financial Statement Schema",
    financial_extraction: "Financial Extraction",
    financial_normalization: "Financial Normalization",
    financial_validation: "Financial Validation",
    financial_ratios: "Financial Ratio Engine",
    financial_trends: "Financial Trend Engine",
    financial_anomalies: "Financial Anomaly Engine",
    credit_engine: "Credit Engine",
    stock_intelligence: "Stock Intelligence",
    rag: "RAG",
  };
  return (
      <section aria-label="System status">
        <p className={health.status === "healthy" ? "badge" : "badge unavailable"}>
          {health.status === "healthy" ? "System healthy" : "System degraded"}
        </p>
        <h2>{status.application.name}</h2>
        <p>Version {status.application.version} · {status.application.environment}</p>
        <ul>
          {Object.entries(status.components).map(([name, state]) => (
            <li key={name}><span>{labels[name] ?? name.replaceAll("_", " ")}</span><strong>{state === "not_implemented" ? "Planned" : state.replaceAll("_", " ")}</strong></li>
          ))}
        </ul>
        <h3>Core models</h3>
        <ul>
          {Object.entries(status.core_models).map(([name, state]) => (
            <li key={name}><span>{name.replaceAll("_", " ")}</span><strong>{state}</strong></li>
          ))}
        </ul>
        <p>Development Stage: Day {status.development_stage.day} — {status.development_stage.name}</p>
      </section>
  );
}
