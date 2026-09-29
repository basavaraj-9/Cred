export type HealthResponse = {
  status: "healthy" | "degraded";
  service: string;
  version: string;
  environment: string;
  dependencies: {
    database: "connected" | "unavailable" | "not_configured";
    storage: "ready" | "unavailable";
    ocr: "available" | "unavailable" | "disabled";
  };
};

export type ComponentState = "ready" | "connected" | "unavailable" | "not_configured" | "not_implemented" | "foundation_ready" | "pipeline_validated" | "experimental" | "disabled" | "not_recorded";

export type StatusResponse = {
  application: { name: string; version: string; environment: string };
  components: Record<string, ComponentState>;
  core_models: Record<string, "ready">;
  development_stage: { day: number; name: string };
};

export type RagIndexStatus = {
  id: string;
  index_version: string;
  status: string;
  chunk_count: number;
  source_count: number;
  source_coverage?: Record<string, number>;
  embedding_provider: string;
  embedding_model: string;
  completed_at: string | null;
};

export type AnalystCitation = {
  index: number;
  source_type: string;
  source_reference_id: string;
  chunk_id: string;
  evidence_text: string;
  page_number: number | null;
  status: string | null;
  confidence: number | null;
  metadata: Record<string, unknown> | null;
};

export type AnalystAnswer = {
  answer_id: string;
  query_run_id: string;
  answer: string;
  status: "ANSWERED" | "PARTIAL" | "INSUFFICIENT_EVIDENCE" | "CONFLICTING_EVIDENCE" | "REQUIRES_HUMAN_REVIEW" | "FAILED";
  confidence: number;
  citation_coverage_ratio: number;
  unsupported_claim_count: number;
  citations: AnalystCitation[];
};

export type PeerGroup = { peer_group_id:string; document_id:string; status:string; policy_version:string; engine_version:string; universe_version:string; universe_snapshot_hash:string; disclaimer:string; peers:Array<{rank:number;company_id:string;company_name:string;listing_id:string;exchange:string;symbol:string;similarity_score:number;components:Record<string,number>;status:string;review_required:boolean;rationale:string[];market_data:{status:string;latest_date:string|null}}> };
export type MarketDataRun = { run_id:string; provider:string; provider_version:string; status:string; symbol_count:number; success_count:number; failure_count:number; start_date:string; end_date:string };
export type Fundamental = {id:string;metric_code:string;value:string;unit:string;currency:string|null;period:string;period_end:string;availability_date:string;scope:string;provenance:string;provider:string;status:string};
export type ValuationResult = {run_id:string;valuation_date:string;status:string;metrics:Array<{code:string;value:string|null;status:string}>};
export type FeatureResult = {run_id:string;as_of_date:string;feature_set_version:string;status:string;features:Array<{name:string;group:string;value:string|null;status:string;source_count:number}>};
export type RelativeMetric = {group_type:"PEER_GROUP"|"INDUSTRY"|"SECTOR";group:string;as_of_date:string;metric_code:string;value:string|null;percentile:string|null;z_score:string|null;rank:number|null;group_size:number;status:string};
export type StockMLDataset = {id:string;dataset_version:string;feature_set_version:string;label_policy_version:string;benchmark_policy_version:string;split_policy_version:string;label_horizon:string;status:string;readiness:string;row_count:number;company_count:number;listing_count:number;positive_count:number;negative_count:number;neutral_count:number;censored_count:number;start_date:string;end_date:string;feature_count:number;feature_schema_hash:string};
export type StockMLSplit = {id:string;split_index:number;policy_version:string;train_start:string;train_end:string;validation_start:string;validation_end:string;test_start:string;test_end:string;embargo_days:number;purged_count:number;status:string;partition_counts:Record<string,number>};
export type StockMLRun = {id:string;dataset_id:string;split_id:string;model_name:string;model_version:string;task_type:string;lifecycle:string;status:string;random_state:number};
export type StockMLMetric = {partition:string;name:string;value:string|null;details:Record<string,unknown>|null};
export type StockMLModel = {id:string;run_id:string;model_name:string;model_version:string;lifecycle:string;selected_for_research:boolean;production_use_permitted:false;artifact_hash:string;feature_schema_hash:string};
export type StockIntelligenceScore = {id:string;listed_company_id:string;stock_listing_id:string;as_of_date:string;score_version:string;fusion_policy_version:string;normalization_policy_version:string;ranking_policy_version:string;watchlist_policy_version:string;status:string;score:string|null;confidence:string;coverage:string;available_weight:string;available_component_count:number;missing_component_count:number;band:string|null;agreement_score:string|null;production_use_permitted:false;research_only:true};
export type StockIntelligenceComponent = {id:string;name:string;score:string|null;weight:string;effective_weight:string;contribution:string|null;confidence:string;status:string;explanation:string;inputs:Array<{source_type:string;source_id:string;feature_name:string;source_value:string|null;source_status:string}>};
export type StockIntelligenceDriver = {component:string;impact:number;explanation:string};
export type StockIntelligenceExplanation = {score_run_id:string;positive_drivers:StockIntelligenceDriver[];negative_drivers:StockIntelligenceDriver[];neutral_factors:string[];missing_evidence:string[];contradictions:string[];confidence_limitations:string[];research_only:true};
export type StockRankingMember = {stock_intelligence_run_id:string;listed_company_id:string;stock_listing_id:string;company_name:string;ticker:string;score:string;confidence:string;coverage:string;rank:number;percentile:string;rank_status:string;research_priority:"RESEARCH_PRIORITY_HIGH"|"RESEARCH_PRIORITY_MEDIUM"|"RESEARCH_PRIORITY_LOW"|"INSUFFICIENT_DATA"};
export type StockRanking = {id:string;as_of_date:string;ranking_policy_version:string;watchlist_policy_version:string;universe_hash:string;status:string;eligible_company_count:number;members:StockRankingMember[];research_only:true};

export type CreditMLEvaluationSummary = {
  evaluation_id: string;
  dataset_id: string;
  evaluation_version: string;
  mode: string;
  window_mode: string;
  status: string;
  valid_window_count: number;
  skipped_window_count: number;
  fusion_readiness: string;
  fusion_allowed: boolean;
  production_use_permitted: false;
  created_at: string;
};

export type CreditFusionExperiment = {
  experiment_id: string;
  strategy: string;
  mode: "EXPERIMENTAL";
  rule_score: number | null;
  rule_risk_index: number | null;
  rule_risk_index_is_probability: false;
  ml_probability: number | null;
  rule_ml_gap: number | null;
  rule_weight: number;
  ml_weight: number;
  experimental_hybrid_risk_index: number | null;
  experimental_hybrid_is_calibrated_pd: false;
  experimental_strength_score: number | null;
  experimental_band: string | null;
  fusion_confidence: number;
  status: string;
  fusion_not_executed: boolean;
  fallback_source: string | null;
  production_use_permitted: false;
  readiness: { checks?: Record<string, { passed: boolean; status?: string; value?: number }> };
  warning: string;
};

export type FiveCsSection = {
  section_id: string;
  status: string;
  confidence: number;
  completeness: number;
  positive_count: number;
  negative_count: number;
  review_count: number;
  summary: string;
};

export type FiveCsAssessment = {
  assessment_id: string;
  document_id: string;
  scope: string;
  status: string;
  overall_completeness: number;
  overall_confidence: number;
  policy_version: string;
  engine_version: string;
  summary_version: string;
  stale: boolean;
  sections: Record<string, FiveCsSection>;
  no_total_credit_score: true;
  lending_decision: null;
  disclaimer: string;
};

export type FiveCsEvidence = {
  evidence_id: string;
  section: string;
  observation_code: string;
  title: string;
  description: string;
  impact: "POSITIVE" | "NEGATIVE" | "NEUTRAL" | "REVIEW";
  source_type: string | null;
  page_number: number | null;
  raw_value: string | null;
  normalized_value: string | null;
  confidence: number;
  status: string;
  source_url: string | null;
};

export type FiveCsReviewItem = {
  review_item_id: string;
  section: string;
  reason_code: string;
  message: string;
  priority: string;
  status: string;
};

export type FiveCsRefresh = {
  refresh_run_id: string;
  base_assessment_id: string;
  refreshed_assessment_id: string;
  research_run_id: string;
  updated_sections: string[];
  status: string;
  policy_version: string;
  assessment: FiveCsAssessment;
  idempotent: boolean;
};

export type CreditRecommendationFactor = {
  factor_id: string;
  factor_code: string;
  category: "STRENGTH" | "RISK" | "CRITICAL_RISK" | "MISSING_EVIDENCE" | "REVIEW_REQUIRED" | "EXPERIMENTAL_CONTEXT";
  title: string;
  description: string;
  source_type: string;
  source_reference_id: string;
  confidence: number;
  severity: string | null;
};

export type CreditRecommendationReviewItem = {
  review_item_id: string;
  review_code: string;
  category: string;
  message: string;
  blocking: boolean;
  resolved: boolean;
};

export type CreditRecommendation = {
  preparation_id: string;
  document_id: string;
  status: string;
  overall_confidence: number;
  overall_completeness: number;
  counts: Record<string, number>;
  summary: string;
  policy_version: string;
  engine_version: string;
  lineage: { credit_assessment_id: string; five_cs_assessment_id: string; research_run_id: string; fusion_experiment_id: string | null };
  factors: CreditRecommendationFactor[];
  review_items: CreditRecommendationReviewItem[];
  disclaimer: string;
  idempotent: boolean;
};

export type CreditDecisionGate = { gate_id: string; gate_code: string; category: string; status: string; severity: string; blocking: boolean; exception_eligible: boolean; message: string; confidence: number };
export type CreditPolicyException = { exception_id: string; exception_code: string; reason: string; required_authority: string; status: string; resolved: boolean };
export type CreditDecisionReviewItem = { review_item_id: string; review_code: string; category: string; message: string; priority: string; blocking: boolean; resolved: boolean };
export type CreditLimitMethod = { method_id: string; method_code: string; status: string; calculated_limit: string | null; confidence: number; formula_version: string; inputs: Record<string, unknown> };
export type CreditLimitPreparation = { currency: string; lower_bound: string | null; upper_bound: string | null; analytical_ceiling: string | null; status: string; confidence: number; policy_version: string; method_count: number; existing_exposure_status: string; projected_ratios: Record<string, unknown>; methods: CreditLimitMethod[]; warning: string; sanctioned: false };
export type CreditDecisionSupport = { decision_support_id: string; document_id: string; scope: string; system_recommendation: string; human_decision: null; human_decision_status: string; confidence: number; completeness: number; blocking_gate_count: number; review_gate_count: number; exception_count: number; production_ml_used: false; experimental_ml_decision_weight: 0; policy_version: string; engine_version: string; summary: string; gates: CreditDecisionGate[]; exceptions: CreditPolicyException[]; review_items: CreditDecisionReviewItem[]; limit_preparation: CreditLimitPreparation | null; warning: string; final_lending_decision: null; sanctioned_limit: null; pricing: null };

export type HumanDecision = { id: string; decision: string; rationale: string; decided_by_user_id: string; authority_role: string; approved_limit: string | null; currency: string | null; conditions: Array<Record<string, unknown>> | null; decision_version: number; is_current: boolean; decision_timestamp: string };
export type CreditReviewCase = { id: string; decision_support_id: string; company_id: string; document_id: string; workflow_status: string; stored_workflow_status: string; primary_reviewer_id: string | null; priority: string; sla_due_at: string | null; case_version: number; human_decision: HumanDecision | null; updated_analysis_available: boolean; created_at: string; updated_at: string };
export type CommitteePackage = { id: string; review_case_id: string; decision_support_id: string; package_version: number; status: string; summary: string; summary_version: string; prepared_by_user_id: string; prepared_at: string; ready_at: string | null; sections: Array<{ id: string; section_code: string; title: string; payload: Record<string, unknown>; source_count: number }> };

export type ReportArtifact = { id: string; format: "PDF" | "JSON"; mime_type: string; file_size_bytes: number; sha256: string; download_available: boolean };
export type GeneratedReport = { id: string; review_case_id: string; decision_support_id: string; human_decision_id: string | null; committee_package_id: string | null; report_type: "CAM" | "CREDIT_COMMITTEE_MEMO" | "DECISION_EVIDENCE_PACK" | "STRUCTURED_JSON_EXPORT"; status: "DRAFT" | "GENERATED" | "FINALIZED" | "SUPERSEDED" | "FAILED"; report_version: number; template_version: string; renderer_version: string; input_hash: string; confidentiality_label: string; generated_by_user_id: string; finalized_by_user_id: string | null; generated_at: string; finalized_at: string | null; supersedes_report_id: string | null; superseded_by_report_id: string | null; artifact: ReportArtifact | null; snapshot_hash: string | null };
export type ReportSnapshot = { report_id: string; snapshot_version: number; payload_hash: string; payload: Record<string, unknown> };
export type ReportEvidenceLink = { id: string; source_type: string; source_reference_id: string; lineage_role: string; metadata: Record<string, unknown> | null };

export type DocumentStatus = "REGISTERED" | "UPLOADED" | "PROCESSING" | "PROCESSED" | "FAILED" | "REJECTED";
export type ParserStatus = "NOT_STARTED" | "PARSING" | "PARSED" | "PARTIAL" | "FAILED" | "REVIEW_REQUIRED";
export type DocumentExtractionMethod = "NATIVE_TEXT" | "OCR" | "HYBRID" | "BLANK" | "FAILED";
export type PageExtractionMethod = "NATIVE_TEXT" | "OCR" | "BLANK" | "FAILED";

export type DocumentMetadata = {
  id: string;
  analysis_job_id: string;
  company_id: string;
  original_filename: string;
  file_type: string | null;
  mime_type: string | null;
  file_size_bytes: number | null;
  sha256_hash: string | null;
  status: DocumentStatus;
  created_at: string;
  parser_status: ParserStatus;
  page_count: number | null;
  extraction_method: DocumentExtractionMethod | null;
  parser_version: string | null;
  parsed_at: string | null;
  parse_error_code: string | null;
};

export type ParseSummary = {
  document_id: string;
  parser_status: ParserStatus;
  page_count: number;
  native_text_pages: number;
  ocr_pages: number;
  blank_pages: number;
  failed_pages: number;
  extraction_method: DocumentExtractionMethod;
  parser_version: string;
};

export type FieldStatus = "VERIFIED" | "NEEDS_REVIEW" | "CONFLICTING" | "UNAVAILABLE";
export type ProfileStatus = "VERIFIED" | "PARTIAL" | "NEEDS_REVIEW" | "CONFLICTING";
export type IdentityMatchStatus = "MATCHED" | "POSSIBLE_MATCH" | "MISMATCH" | "UNAVAILABLE";
export type ProfileField = {
  id: string;
  field_name: string;
  value: string;
  confidence: number;
  status: FieldStatus;
  page_number: number;
};
export type CompanyProfile = {
  profile_id: string;
  document_id: string;
  company_id: string;
  analysis_job_id: string;
  uploaded_company_name: string;
  status: ProfileStatus;
  identity_match_status: IdentityMatchStatus;
  overall_confidence: number;
  extractor_version: string;
  fields: Record<string, ProfileField[]>;
};
export type ProfileEvidence = {
  id: string;
  document_id: string;
  document_page_id: string;
  page_number: number;
  field_group: string;
  field_name: string;
  raw_value: string;
  normalized_value: string;
  evidence_text: string;
  confidence_score: number;
  status: FieldStatus;
  extraction_method: string;
  extractor_version: string;
};

export type ClassificationStatus = "VERIFIED" | "NEEDS_REVIEW" | "UNAVAILABLE" | "CONFLICTING";
export type LabelConfidence = { label: string; confidence: number };
export type DomainClassification = {
  classification_id: string;
  company_profile_id: string;
  sector: LabelConfidence;
  industry: LabelConfidence;
  domain: LabelConfidence;
  sub_domain: LabelConfidence;
  overall_confidence: number;
  status: ClassificationStatus;
  alternative_sub_domain: LabelConfidence | null;
  taxonomy_version: string;
  model_version: string;
  dataset_version: string;
  input_builder_version: string;
  input_text_hash: string;
  stale: boolean;
};
export type ClassificationEvidence = {
  extracted_field_id: string;
  document_page_id: string;
  document_id: string;
  page_number: number;
  field_name: string;
  evidence_role: string;
  evidence_text: string;
  confidence_score: number;
};

export type PageSummary = {
  page_number: number;
  extraction_method: PageExtractionMethod;
  character_count: number;
  word_count: number;
  text_quality_score: number;
  ocr_required: boolean;
  ocr_attempted: boolean;
  ocr_succeeded: boolean;
  error_code: string | null;
};

export type UploadResult = {
  analysis_id: string;
  company_id: string;
  document: {
    id: string;
    original_filename: string;
    mime_type: string;
    file_size_bytes: number;
    sha256_hash: string;
    status: DocumentStatus;
  };
  message: string;
};

export type FinancialExtractionSummary = {
  document_id: string;
  extractor_version: string;
  taxonomy_version: string;
  status: string;
  statements_found: number;
  line_items_extracted: number;
  verified_items: number;
  review_items: number;
  conflicting_items: number;
  unmapped_items: number;
};

export type FinancialStatement = {
  id: string;
  statement_type: string;
  statement_scope: string;
  fiscal_year: string | null;
  currency: string | null;
  normalized_unit: string | null;
  status: string;
  confidence_score: number;
  start_page_number: number;
  end_page_number: number;
};

export type FinancialLineItem = {
  id: string;
  canonical_name: string | null;
  raw_label: string;
  raw_value: string;
  numeric_value: string | null;
  raw_column_header: string | null;
  fiscal_year: string | null;
  currency: string | null;
  normalized_unit: string | null;
  measurement_type: string;
  status: string;
  confidence_score: number;
  page_number: number;
  evidence_text: string;
};

export type FinancialAnalysisSummary = {
  document_id: string;
  status: string;
  normalized_values: number;
  derived_values: number;
  validation: { passed_checks: number; warnings: number; errors: number };
  ratios_calculated: number;
  ratios_review_required: number;
  completeness_score: number;
  validator_version: string;
  ratio_calculator_version: string;
  ratio_taxonomy_version: string;
};

export type NormalizedFinancialValue = {
  id: string;
  canonical_name: string;
  statement_scope: string;
  fiscal_year: string;
  raw_numeric_value: string | null;
  normalized_value: string | null;
  currency: string | null;
  canonical_unit: string;
  status: string;
  confidence_score: number;
  origin: "EXTRACTED" | "DERIVED";
  formula: string | null;
  input_value_ids: string[] | null;
  source: { page_number: number; raw_label: string; raw_value: string; raw_unit: string | null; evidence_text: string } | null;
};

export type FinancialValidationIssue = {
  id: string;
  statement_scope: string;
  fiscal_year: string;
  issue_type: string;
  severity: string;
  message: string;
  status: string;
};

export type FinancialValidation = {
  document_id: string;
  status: string;
  completeness_score: number;
  validator_version: string;
  normalized_values: NormalizedFinancialValue[];
  issues: FinancialValidationIssue[];
};

export type FinancialRatio = {
  id: string;
  statement_scope: string;
  fiscal_year: string;
  ratio_name: string;
  ratio_category: string;
  ratio_value: string | null;
  ratio_unit: string;
  status: string;
  confidence_score: number;
  calculation_basis: string;
  formula: string;
};

export type FinancialRatioDetail = FinancialRatio & {
  inputs: Array<{
    input_role: string;
    canonical_name: string;
    normalized_value: string | null;
    currency: string | null;
    origin: string;
    confidence_score: number;
    source: { page_number: number; raw_label: string; raw_value: string; evidence_text: string } | null;
    derived_sources: Array<{ canonical_name: string; page_number: number; raw_label: string; raw_value: string; evidence_text: string }>;
  }>;
};

export type FinancialTrendAnalysisSummary = {
  document_id: string;
  run_id: string;
  status: string;
  trend_count: number;
  anomaly_count: number;
  verified_anomalies: number;
  review_anomalies: number;
  scopes: string[];
  years: string[];
  trend_calculator_version: string;
  anomaly_rule_version: string;
};

export type FinancialTrendPoint = {
  fiscal_year: string;
  period_year: number;
  value: string;
  confidence_score: number;
  status: string;
  absolute_change?: string;
  percentage_change?: string | null;
  percentage_point_change?: string | null;
  state_transition?: string | null;
  reason?: string | null;
};

export type FinancialTrend = {
  id: string;
  statement_scope: string;
  metric_name: string;
  metric_source_type: "NORMALIZED_VALUE" | "RATIO";
  currency: string;
  start_fiscal_year: string;
  end_fiscal_year: string;
  period_count: number;
  start_value: string | null;
  end_value: string | null;
  absolute_change: string | null;
  percentage_change: string | null;
  cagr: string | null;
  percentage_point_change: string | null;
  change_type: string;
  state_transition: string | null;
  trend_direction: string;
  trend_strength: string | null;
  status: string;
  confidence_score: number;
  series: FinancialTrendPoint[];
  missing_periods: string[] | null;
  calculator_version: string;
};

export type TrendEvidence = {
  canonical_name: string;
  fiscal_year: string;
  value: string;
  currency: string | null;
  confidence_score: number;
  page_number: number | null;
  raw_label: string | null;
  raw_value: string | null;
  evidence_text: string | null;
};

export type FinancialTrendDetail = FinancialTrend & {
  formula: string;
  inputs: Array<{
    input_role: string;
    fiscal_year: string;
    source_type: string;
    source_id: string;
    metric_name: string;
    evidence: TrendEvidence[];
  }>;
};

export type FinancialAnomaly = {
  id: string;
  statement_scope: string;
  anomaly_type: string;
  category: string;
  severity: "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  title: string;
  description: string;
  start_fiscal_year: string;
  end_fiscal_year: string;
  confidence_score: number;
  status: string;
  persistence_count: number;
  rule_version: string;
};

export type FinancialAnomalyDetail = FinancialAnomaly & {
  inputs: Array<{ input_role: string; source_type: string; source: FinancialTrendDetail }>;
};

export type CreditFactor = {
  rule_code: string;
  component: string;
  impact: string;
  message: string;
};

export type CreditSubscore = {
  component: string;
  score: string;
  weight: string;
  weighted_score: string | null;
  coverage: string;
  confidence_score: string;
  status: string;
};

export type CreditAssessment = {
  assessment_id: string;
  document_id: string;
  statement_scope: string;
  overall_score: string | null;
  risk_band: string | null;
  component_coverage: string;
  confidence_score: string;
  status: string;
  policy_version: string;
  feature_builder_version: string;
  score_engine_version: string;
  subscores: CreditSubscore[];
  top_positive_factors: CreditFactor[];
  top_negative_factors: CreditFactor[];
  disclaimer: string;
};

export type CreditReason = {
  id: string;
  component: string;
  rule_code: string;
  rule_version: string;
  input_metric: string;
  input_value: string | null;
  input_status: string;
  score_impact: string;
  max_score_impact: string;
  message: string;
  reason_type: string;
  confidence_score: number;
  status: string;
  assessment_input_id: string | null;
  evidence_url: string | null;
};

export type CreditEvidence = {
  assessment_input_id: string;
  input_role: string;
  evidence: Array<{
    source_type: string;
    source_id: string;
    metric: string;
    fiscal_year?: string;
    value: string | null;
    page_number: number | null;
    evidence_text: string | null;
    raw_label?: string | null;
    raw_value?: string | null;
  }>;
};

export type ResearchRun = {
  research_run_id: string;
  company_id: string;
  status: string;
  scopes: string[];
  provider: { name: string; version: string };
  versions: Record<string, string>;
  query_count: number;
  source_count: number;
  evidence_count: number;
  finding_count: number;
  review_count: number;
  refresh_number: number;
  coverage: Record<string, { queried: boolean; verified_findings: number }>;
  day15_automatically_modified: boolean;
  final_lending_decision: string;
};

export type ResearchSource = {
  source_id: string;
  title: string;
  publisher: string;
  source_type: string;
  source_tier: number;
  quality: number;
  url: string;
  publication_date: string | null;
  event_date: string | null;
  retrieved_at: string;
  freshness: string;
  entity_match_status: string;
  status: string;
  error_code: string | null;
};

export type ResearchFinding = {
  finding_id: string;
  finding_code: string;
  category: string;
  summary: string;
  impact: string;
  status: string;
  confidence: number;
  source_count: number;
  candidate_section: string | null;
  event_date: string | null;
  applied_to_day15: boolean;
};

export type ResearchCandidates = {
  research_run_id: string;
  character: ResearchFinding[];
  conditions: ResearchFinding[];
  applied_to_day15: boolean;
};
