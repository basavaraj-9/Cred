import { API_BASE_URL, API_V1_PATH, BROWSER_API_BASE_URL } from "@/lib/config";
import type { ClassificationEvidence, CompanyProfile, CreditAssessment, CreditEvidence, CreditFusionExperiment, CreditMLEvaluationSummary, CreditReason, DocumentMetadata, DomainClassification, FinancialAnalysisSummary, FinancialAnomaly, FinancialAnomalyDetail, FinancialExtractionSummary, FinancialLineItem, FinancialRatio, FinancialRatioDetail, FinancialStatement, FinancialTrend, FinancialTrendAnalysisSummary, FinancialTrendDetail, FinancialValidation, FiveCsAssessment, FiveCsEvidence, FiveCsReviewItem, HealthResponse, PageSummary, ParseSummary, ProfileEvidence, StatusResponse, UploadResult } from "@/types/api";
import type { CommitteePackage, CreditDecisionSupport, CreditRecommendation, CreditReviewCase, FiveCsRefresh, GeneratedReport, ReportEvidenceLink, ReportSnapshot, ResearchCandidates, ResearchFinding, ResearchRun, ResearchSource } from "@/types/api";
import type { AnalystAnswer, RagIndexStatus } from "@/types/api";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${API_V1_PATH}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return (await response.json()) as T;
}

export const getHealth = () => getJson<HealthResponse>("/health");
export const getStatus = () => getJson<StatusResponse>("/status");
export const getCreditMLEvaluations = () =>
  getJson<CreditMLEvaluationSummary[]>("/ml/credit/evaluations");

async function analystMutation<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Analyst request failed (${response.status})`);
  return payload as T;
}

export const buildRagIndex = (companyId: string, actorId: string) =>
  analystMutation<RagIndexStatus>(`/companies/${encodeURIComponent(companyId)}/rag/index`, { actor_user_id: actorId });

export async function getRagIndex(companyId: string, actorId: string): Promise<RagIndexStatus> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/companies/${encodeURIComponent(companyId)}/rag/index?actor_user_id=${encodeURIComponent(actorId)}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Index lookup failed (${response.status})`);
  return payload as RagIndexStatus;
}

export const askCreditAnalyst = (companyId: string, body: Record<string, unknown>) =>
  analystMutation<AnalystAnswer>(`/companies/${encodeURIComponent(companyId)}/analyst/ask`, body);

export const submitAnalystFeedback = (answerId: string, actorId: string, rating: string, comment?: string) =>
  analystMutation<Record<string, unknown>>(`/analyst/answers/${encodeURIComponent(answerId)}/feedback`, { actor_user_id: actorId, rating, comment: comment || null });

export async function createCreditFusionExperiment(
  creditAssessmentId: string,
  featureSnapshotId: string,
  strategy: string,
): Promise<CreditFusionExperiment> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/credit-fusion/experiments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credit_assessment_id: creditAssessmentId, feature_snapshot_id: featureSnapshotId, strategy }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Fusion experiment failed (${response.status})`);
  return payload as CreditFusionExperiment;
}

export async function analyzeFiveCs(documentId: string, scope: string): Promise<FiveCsAssessment> {
  const query = scope ? `?scope=${encodeURIComponent(scope)}` : "";
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/five-cs/analyze${query}`, { method: "POST" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `5 Cs analysis failed (${response.status})`);
  return (Array.isArray(payload) ? payload[0] : payload) as FiveCsAssessment;
}

export async function getFiveCsEvidence(assessmentId: string): Promise<FiveCsEvidence[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/five-cs/${encodeURIComponent(assessmentId)}/evidence`);
  if (!response.ok) throw new Error(`5 Cs evidence lookup failed (${response.status})`);
  return (await response.json()) as FiveCsEvidence[];
}

export async function getFiveCsReviewItems(assessmentId: string): Promise<FiveCsReviewItem[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/five-cs/${encodeURIComponent(assessmentId)}/review-items`);
  if (!response.ok) throw new Error(`5 Cs review lookup failed (${response.status})`);
  return (await response.json()) as FiveCsReviewItem[];
}

export async function refreshFiveCs(assessmentId: string, researchRunId: string): Promise<FiveCsRefresh> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/five-cs/${encodeURIComponent(assessmentId)}/refresh-with-research`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ research_run_id: researchRunId }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `5 Cs refresh failed (${response.status})`);
  return payload as FiveCsRefresh;
}

export async function prepareCreditRecommendation(documentId: string, scope: string, fiveCsAssessmentId?: string, researchRunId?: string, fusionExperimentId?: string): Promise<CreditRecommendation> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/credit-recommendation/prepare`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope, five_cs_assessment_id: fiveCsAssessmentId || null, research_run_id: researchRunId || null, fusion_experiment_id: fusionExperimentId || null }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Recommendation preparation failed (${response.status})`);
  return payload as CreditRecommendation;
}

export async function prepareCreditDecision(documentId: string, scope: string, recommendationPreparationId?: string): Promise<CreditDecisionSupport> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/credit-decision/prepare`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope, recommendation_preparation_id: recommendationPreparationId || null }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Decision support preparation failed (${response.status})`);
  return payload as CreditDecisionSupport;
}

async function reviewMutation<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Review action failed (${response.status})`);
  return payload as T;
}
export const listCreditReviewCases = async () => {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/credit-review-cases`);
  if (!response.ok) throw new Error(`Review case lookup failed (${response.status})`);
  return (await response.json()) as CreditReviewCase[];
};
export const getCreditReviewCase = async (id: string) => {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/credit-review-cases/${encodeURIComponent(id)}`);
  if (!response.ok) throw new Error(`Review case lookup failed (${response.status})`);
  return (await response.json()) as CreditReviewCase;
};
export const createCreditReviewCase = (decisionId: string, actorId: string) => reviewMutation<CreditReviewCase>(`/credit-decisions/${encodeURIComponent(decisionId)}/review-case`, { actor_user_id: actorId });
export const assignCreditReviewCase = (caseId: string, actorId: string, reviewerId: string) => reviewMutation<CreditReviewCase>(`/credit-review-cases/${encodeURIComponent(caseId)}/assign`, { actor_user_id: actorId, reviewer_user_id: reviewerId });
export const startCreditReview = (caseId: string, actorId: string) => reviewMutation<CreditReviewCase>(`/credit-review-cases/${encodeURIComponent(caseId)}/start`, { actor_user_id: actorId });
export const recordHumanDecision = (caseId: string, body: Record<string, unknown>) => reviewMutation<Record<string, unknown>>(`/credit-review-cases/${encodeURIComponent(caseId)}/decision`, body);
export const createCommitteePackage = (caseId: string, actorId: string) => reviewMutation<CommitteePackage>(`/credit-review-cases/${encodeURIComponent(caseId)}/committee-package`, { actor_user_id: actorId });
export const listCommitteePackages = async (caseId: string) => {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/credit-review-cases/${encodeURIComponent(caseId)}/committee-packages`);
  if (!response.ok) throw new Error(`Committee package lookup failed (${response.status})`);
  return (await response.json()) as CommitteePackage[];
};
export const generateCreditReport = (caseId: string, body: Record<string, unknown>) => reviewMutation<GeneratedReport>(`/credit-review-cases/${encodeURIComponent(caseId)}/reports`, body);
export const listCreditReports = async (caseId: string) => {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/credit-review-cases/${encodeURIComponent(caseId)}/reports`);
  if (!response.ok) throw new Error(`Credit report lookup failed (${response.status})`);
  return (await response.json()) as GeneratedReport[];
};
export const finalizeCreditReport = (reportId: string, actorId: string, rationale: string) => reviewMutation<GeneratedReport>(`/reports/${encodeURIComponent(reportId)}/finalize`, { actor_user_id: actorId, rationale });
export const getCreditReportSnapshot = async (reportId: string, actorId: string) => {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/reports/${encodeURIComponent(reportId)}/snapshot?actor_user_id=${encodeURIComponent(actorId)}`);
  if (!response.ok) throw new Error(`Report preview failed (${response.status})`);
  return (await response.json()) as ReportSnapshot;
};
export const getCreditReportEvidence = async (reportId: string, actorId: string) => {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/reports/${encodeURIComponent(reportId)}/evidence?actor_user_id=${encodeURIComponent(actorId)}`);
  if (!response.ok) throw new Error(`Report evidence lookup failed (${response.status})`);
  return (await response.json()) as ReportEvidenceLink[];
};
export const creditReportDownloadUrl = (reportId: string, actorId: string) => `${BROWSER_API_BASE_URL}${API_V1_PATH}/reports/${encodeURIComponent(reportId)}/download?actor_user_id=${encodeURIComponent(actorId)}`;

export async function startCompanyResearch(companyId: string, scopes: string[], refresh: boolean): Promise<ResearchRun> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/companies/${encodeURIComponent(companyId)}/research`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scopes, refresh }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Research failed (${response.status})`);
  return payload as ResearchRun;
}

export async function getResearchSources(runId: string): Promise<ResearchSource[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/research-runs/${encodeURIComponent(runId)}/sources`);
  if (!response.ok) throw new Error(`Research sources lookup failed (${response.status})`);
  return (await response.json()) as ResearchSource[];
}

export async function getResearchFindings(runId: string): Promise<ResearchFinding[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/research-runs/${encodeURIComponent(runId)}/findings`);
  if (!response.ok) throw new Error(`Research findings lookup failed (${response.status})`);
  return (await response.json()) as ResearchFinding[];
}

export async function getResearchCandidates(runId: string): Promise<ResearchCandidates> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/research-runs/${encodeURIComponent(runId)}/five-cs-candidates`);
  if (!response.ok) throw new Error(`5 Cs candidate lookup failed (${response.status})`);
  return (await response.json()) as ResearchCandidates;
}

export async function uploadDocument(
  companyLegalName: string,
  displayName: string,
  file: File,
): Promise<UploadResult> {
  const body = new FormData();
  body.append("company_legal_name", companyLegalName);
  if (displayName.trim()) body.append("display_name", displayName.trim());
  body.append("file", file);
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/upload`, {
    method: "POST",
    body,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.error?.message ?? `Upload failed (${response.status})`);
  }
  return payload as UploadResult;
}

export async function getDocument(documentId: string): Promise<DocumentMetadata> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}`);
  if (!response.ok) throw new Error(`Document lookup failed (${response.status})`);
  return (await response.json()) as DocumentMetadata;
}

export async function getAnalysisDocuments(analysisId: string): Promise<DocumentMetadata[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/analysis/${encodeURIComponent(analysisId)}/documents`);
  if (!response.ok) throw new Error(`Document list failed (${response.status})`);
  return (await response.json()) as DocumentMetadata[];
}

export async function parseDocument(documentId: string): Promise<ParseSummary> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/parse`, {
    method: "POST",
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Parsing failed (${response.status})`);
  return payload as ParseSummary;
}

export async function getDocumentPages(documentId: string): Promise<PageSummary[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/pages`);
  if (!response.ok) throw new Error(`Page lookup failed (${response.status})`);
  return (await response.json()) as PageSummary[];
}

export async function extractCompanyProfile(documentId: string): Promise<CompanyProfile> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/company-profile/extract`, { method: "POST" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Profile extraction failed (${response.status})`);
  return payload as CompanyProfile;
}

export async function getCompanyProfile(documentId: string): Promise<CompanyProfile> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/company-profile`);
  if (!response.ok) throw new Error(`Profile lookup failed (${response.status})`);
  return (await response.json()) as CompanyProfile;
}

export async function getProfileEvidence(profileId: string): Promise<ProfileEvidence[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/company-profiles/${encodeURIComponent(profileId)}/evidence`);
  if (!response.ok) throw new Error(`Evidence lookup failed (${response.status})`);
  return (await response.json()) as ProfileEvidence[];
}

export async function classifyDomain(profileId: string): Promise<DomainClassification> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/company-profiles/${encodeURIComponent(profileId)}/domain-classification`, { method: "POST" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Domain classification failed (${response.status})`);
  return payload as DomainClassification;
}

export async function getDomainClassification(profileId: string): Promise<DomainClassification> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/company-profiles/${encodeURIComponent(profileId)}/domain-classification`);
  if (!response.ok) throw new Error(`Domain classification lookup failed (${response.status})`);
  return (await response.json()) as DomainClassification;
}

export async function getDomainClassificationEvidence(classificationId: string): Promise<ClassificationEvidence[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/domain-classifications/${encodeURIComponent(classificationId)}/evidence`);
  if (!response.ok) throw new Error(`Classification evidence lookup failed (${response.status})`);
  return (await response.json()) as ClassificationEvidence[];
}

export async function extractFinancialStatements(documentId: string): Promise<FinancialExtractionSummary> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/financial-statements/extract`, { method: "POST" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Financial extraction failed (${response.status})`);
  return payload as FinancialExtractionSummary;
}

export async function getFinancialStatements(documentId: string): Promise<FinancialStatement[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/financial-statements`);
  if (!response.ok) throw new Error(`Financial statements lookup failed (${response.status})`);
  return (await response.json()) as FinancialStatement[];
}

export async function getFinancialLineItems(statementId: string): Promise<FinancialLineItem[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/financial-statements/${encodeURIComponent(statementId)}/line-items`);
  if (!response.ok) throw new Error(`Financial line items lookup failed (${response.status})`);
  return (await response.json()) as FinancialLineItem[];
}

export async function runFinancialAnalysis(documentId: string): Promise<FinancialAnalysisSummary> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/financial-analysis`, { method: "POST" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Financial analysis failed (${response.status})`);
  return payload as FinancialAnalysisSummary;
}

export async function getFinancialValidation(documentId: string): Promise<FinancialValidation> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/financial-validation`);
  if (!response.ok) throw new Error(`Financial validation lookup failed (${response.status})`);
  return (await response.json()) as FinancialValidation;
}

export async function getFinancialRatios(documentId: string): Promise<FinancialRatio[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/financial-ratios`);
  if (!response.ok) throw new Error(`Financial ratio lookup failed (${response.status})`);
  return (await response.json()) as FinancialRatio[];
}

export async function getFinancialRatio(ratioId: string): Promise<FinancialRatioDetail> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/financial-ratios/${encodeURIComponent(ratioId)}`);
  if (!response.ok) throw new Error(`Financial ratio evidence lookup failed (${response.status})`);
  return (await response.json()) as FinancialRatioDetail;
}

export async function runFinancialTrendAnalysis(documentId: string): Promise<FinancialTrendAnalysisSummary> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/financial-trends/analyze`, { method: "POST" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Trend analysis failed (${response.status})`);
  return payload as FinancialTrendAnalysisSummary;
}

export async function getFinancialTrends(documentId: string): Promise<FinancialTrend[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/financial-trends`);
  if (!response.ok) throw new Error(`Financial trend lookup failed (${response.status})`);
  return (await response.json()) as FinancialTrend[];
}

export async function getFinancialTrend(trendId: string): Promise<FinancialTrendDetail> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/financial-trends/${encodeURIComponent(trendId)}`);
  if (!response.ok) throw new Error(`Financial trend evidence lookup failed (${response.status})`);
  return (await response.json()) as FinancialTrendDetail;
}

export async function getFinancialAnomalies(documentId: string): Promise<FinancialAnomaly[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/financial-anomalies`);
  if (!response.ok) throw new Error(`Financial anomaly lookup failed (${response.status})`);
  return (await response.json()) as FinancialAnomaly[];
}

export async function getFinancialAnomaly(anomalyId: string): Promise<FinancialAnomalyDetail> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/financial-anomalies/${encodeURIComponent(anomalyId)}`);
  if (!response.ok) throw new Error(`Financial anomaly evidence lookup failed (${response.status})`);
  return (await response.json()) as FinancialAnomalyDetail;
}

export async function runCreditAnalysis(documentId: string): Promise<CreditAssessment[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/documents/${encodeURIComponent(documentId)}/credit-risk/analyze`, { method: "POST" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? `Credit analysis failed (${response.status})`);
  return (Array.isArray(payload) ? payload : [payload]) as CreditAssessment[];
}

export async function getCreditReasons(assessmentId: string): Promise<CreditReason[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/credit-assessments/${encodeURIComponent(assessmentId)}/reasons`);
  if (!response.ok) throw new Error(`Credit reasons lookup failed (${response.status})`);
  const groups = (await response.json()) as Record<string, CreditReason[]>;
  return ["positive", "negative", "review", "neutral"].flatMap((name) => groups[name] ?? []);
}

export async function getCreditEvidence(assessmentId: string): Promise<CreditEvidence[]> {
  const response = await fetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/credit-assessments/${encodeURIComponent(assessmentId)}/evidence`);
  if (!response.ok) throw new Error(`Credit evidence lookup failed (${response.status})`);
  return (await response.json()) as CreditEvidence[];
}
