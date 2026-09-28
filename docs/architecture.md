# Architecture

## Current system

The frontend is a Next.js App Router application with a status page and PDF upload form. FastAPI owns configuration, route contracts, validation, logging, exception handling, CORS, and database checks. SQLAlchemy models and explicit repositories isolate persistence from routes. Alembic owns schema changes.

```text
Browser → Next.js upload form → FastAPI /api/v1/documents/upload
                                  ↓
                           Validation + SHA-256
                                  ↓
                         Local storage service
                                  ↓
                              PostgreSQL
```

Core tables are `users`, `companies`, `analysis_jobs`, `documents`, `document_pages`, `company_profiles`, `extracted_fields`, `ml_datasets`, `ml_runs`, `ml_metrics`, `ml_models`, `domain_classifications`, `domain_classification_evidence`, `financial_extraction_runs`, `financial_statements`, `financial_line_items`, and `audit_logs`. UUIDs are application-generated. PostgreSQL stores document metadata, extracted page text, and evidence-backed profile and financial fields; original PDF files use generated names in `storage/uploads`. Storage paths are translated from logical URIs by the storage adapter. Foreign keys restrict deletion of referenced entities; no relationship silently cascades deletes. Database roles should further restrict audit log deletion in a later security increment.

The API health check performs bounded `SELECT 1` and checks local upload directory readiness; unavailable dependencies produce a controlled degraded response. It does not verify migration state. Indexes on email, company name, job company/status, document job/company/hash, and audit job/entity support expected lookups. A unique constraint on company ID plus SHA-256 prevents exact duplicate content for the same company. Audit metadata uses JSONB.

The upload service validates and hashes before writing. It uses a caller-owned database transaction, writes through the storage interface, and deletes the newly stored file if a later database step fails. This compensating cleanup handles ordinary failures. A process crash between file write and database commit can still leave a file; future operations tooling should reconcile such files. No cloud adapter exists yet.

Credit Risk Score and Stock Intelligence Score will be separate domain outputs with separate data, models, and evidence. Their implementations remain planned.

## Day 4 document intelligence

```text
Upload → Local storage → PyMuPDF parser → Native text quality check
                                      ↘ OCR fallback on eligible pages
                         ↓
                 DocumentPage records
                         ↓
              Profile, domain, and financial extraction
```

The parsing service retrieves the uploaded PDF through the storage adapter. It marks the document `PARSING` in a short transaction, processes pages sequentially outside a database transaction, and atomically writes page rows with the final document summary. The upload status remains separate from parser status. `document_pages` holds 1-based page numbers, full extracted text, extraction method, quality score, OCR flags, error metadata, and parser version. A unique document and page number constraint protects provenance. The API exposes a small parse summary, a page metadata list, and individual page text. Profile, domain, and financial services cite document IDs and 1-based page numbers.


## Day 5 company profile

```text
DocumentPage → section and candidate rules → evidence-linked ExtractedField
                                               ↓
                                      CompanyProfile status
                                               ↓
                                      domain classification
```

The profile extractor reads only stored `document_pages` rows. It never opens the original PDF or calls OCR. `company_profiles` stores the document, company, analysis job, extractor version, overall status, identity match status, and verified canonical values. `extracted_fields` stores each candidate's document page ID, 1-based page number, raw and normalized value, concise source snippet, confidence, status, and version. The profile and all candidate fields commit in one transaction. The unique `(document_id, extractor_version)` constraint and document row lock make repeated extraction idempotent. The uploaded Company row is not modified.

## Day 6 domain ML

```text
CompanyProfile + verified business ExtractedField rows
            ↓
Versioned inference text + SHA-256
            ↓
Active TF-IDF classifier → sub-domain probabilities
            ↓
Versioned taxonomy supplies domain, industry, sector
            ↓
DomainClassification + evidence links + model/dataset lineage
```

The model is trained from an immutable JSONL snapshot, not mutable production rows. `ml_datasets`, `ml_runs`, `ml_metrics`, and `ml_models` record the dataset digest, candidate runs, measured metrics, active model, and artifact digest. Artifacts live outside PostgreSQL under `storage/models/domain`. `domain_classifications` stores the active model reference, profile and document lineage, four-level path, level confidence, status, taxonomy/dataset/builder versions, and input hash. `domain_classification_evidence` links only the verified business fields actually included in the model input. A partial unique index permits one active model per task. Source PDFs, pages, and extracted fields are unchanged by inference.

## Day 7 financial extraction

```text
DocumentPage text → heading/table detector → period, scope, currency and unit parsing
                  → versioned taxonomy → candidate reconciliation
                  → extraction run → statements → evidence-linked line items
```

The financial service is independent of domain classification. It locks the document during an extraction transaction, hashes ordered page text and parser provenance, and uses a unique run key for idempotency. `financial_extraction_runs`, `financial_statements`, and `financial_line_items` persist this lineage. A statement row represents one reporting column; line-item rows retain raw source values and 1-based page provenance. Separate scope values prevent standalone and consolidated numbers from being merged. Conflicting candidates remain visible. API summaries omit full page text.

## Day 8 financial analysis

```text
FinancialLineItem → selected NormalizedFinancialValue → validation issues
                                                   ↘ safe derived values
                                                    → FinancialRatio → ratio inputs → page evidence
```

`financial_analysis_runs` fingerprints the full Day 7 analytical input and versions the validator, ratio calculator, and ratio taxonomy. `normalized_financial_values` retains the source line-item foreign key or a derived formula and input IDs. `financial_validation_issues` stores pass, warning, failure, and skipped results with related values and tolerance. `financial_ratios` stores one definition per scope and fiscal year, including unavailable results, while `financial_ratio_inputs` links each calculated ratio to every normalized input. One transaction writes the complete graph and its audit events.

## Day 9 trend and anomaly analysis

```text
NormalizedFinancialValue + FinancialRatio
                    ↓
       Chronological Trend Engine
                    ↓
       Versioned Anomaly Engine
                    ↓
          Financial Risk Signals
```

`financial_trend_runs` fingerprints the complete Day 8 input and calculator/rule versions. `financial_trends` stores scope and currency-isolated series, changes, CAGR, direction, strength, status, confidence, and missing periods. `financial_trend_inputs` links every period to its normalized value or ratio. `financial_anomalies` stores descriptive, deterministic rule results and `financial_anomaly_inputs` links each alert to its supporting trends or analytical inputs. The complete Day 9 graph and audit events commit in one transaction.

## Day 10 deterministic credit risk

The credit engine has separate feature-building and scoring layers. `credit_feature_builder_v1` reads only persisted profile, domain, Day 8, and Day 9 rows. `credit_policy_v1` owns component weights, coverage gates, thresholds, reason impacts, overlap suppression, and band boundaries. `credit_score_engine_v1` applies the policy without ML or external data.

`credit_assessments` stores one immutable result per scope and input fingerprint. `credit_subscores` stores all five component outcomes. `credit_rule_results` records every applied rule and score impact. `credit_assessment_inputs` is the typed lineage edge to exactly one upstream row. The assessment, inputs, subscores, reasons, and audit events commit atomically.

## Day 11 credit ML dataset preparation

`credit_ml_observations` defines historical cutoffs and horizons independently of current analysis runs. `credit_outcomes` stores verified positive, negative, censored, or conflicting evidence and its real, curated, or synthetic quality. The versioned label policy converts that evidence into a binary target only when horizon coverage is complete.

`credit_ml_feature_snapshots` stores immutable feature JSON, schema and builder versions, a digest, missingness, and whether original publication availability is known. `credit_ml_feature_sources` links each populated feature to exactly one Day 5, Day 8, Day 9, or optional Day 10 source row. `credit_ml_examples` records company-isolated chronological partitions; `ml_datasets` and `credit_ml_dataset_reports` store the artifact digest, configuration, quality, readiness, counts, and leakage report. Dataset building is separate from model training and inference.

## Day 12 credit ML baseline pipeline

```text
Credit ML Dataset → train-only preprocessing → LR / RF / XGBoost
  → train-only sigmoid calibration → validation evaluation
  → versioned selection policy → locked test evaluation
  → hashed full-pipeline artifacts → generic ML registry
  → integrity-checked development inference
```

Each candidate has its own `ml_runs` row. Valid scalar metrics retain their split in `ml_metrics`; complete evaluation structures, confusion matrices, unavailable reasons, calibration points, and feature diagnostics live in model metadata. `ml_models` links every candidate to its immutable dataset and artifact. Only the selected pipeline-validation baseline is active, and its readiness metadata forbids production use.

## Day 13 credit ML evaluation architecture

```text
Versioned Credit Dataset
  → chronological expanding or rolling window generator
  → independent preprocessor + model + calibration per window
  → future-window metrics and probability summaries
  → feature, prediction, and calibration drift
  → candidate-model disagreement
  → diagnostic Day 10 rule comparison
  → versioned fusion-readiness gates
```

Evaluation runs, windows, window model results, drift results, and rule/ML comparisons are stored separately from the active model registry. Window estimators are temporary evaluation objects and cannot become active models. Input hashing makes evaluation idempotent. Foreign keys and cascade deletion keep each derived evaluation graph internally consistent while leaving the dataset, Day 10 assessments, and Day 12 artifacts unchanged.

## Day 14 experimental fusion architecture

```text
Immutable Day 10 assessment + integrity-checked active Day 12 model prediction
  + Day 13 evaluation, drift and candidate disagreement
  + financial completeness
  → versioned readiness and safety gates
  → weighted blend or consensus-gated strategy
  → experimental result, rule-only reference, review, or no-output state
  → contributions + reasons + input lineage + audit events
```

`CreditFusionReadinessService` evaluates rule status and confidence, effective coverage, snapshot lineage, artifact integrity, pipeline readiness, evaluation availability, drift, model disagreement, real outcomes, and walk-forward support. It separately reports experimental and production readiness. Synthetic pipeline validation can permit an internal experiment, while production remains blocked.

`CreditFusionService` obtains probability from `CreditMLInferenceService`; the client cannot submit a score or probability. Strategy math is isolated from readiness and confidence logic and uses `Decimal`. `credit_fusion_experiments` holds the derived output and version identities. Contributions preserve raw and normalized component values, reasons preserve gate and penalty explanations, and inputs link the assessment, model prediction, snapshot, and evaluation. The input digest makes identical runs idempotent.

Experiment evaluation reports the available Day 13 ML metrics and rule/ML ranking correlation, plus the current rule, ML, and hybrid values. A single experiment has no labelled historical hybrid series, so hybrid outcome metrics and Brier score remain unavailable and no strategy winner is selected. The UI and APIs always identify the hybrid value as an experimental risk index rather than a calibrated probability or final credit score.

## Day 15 5 Cs evidence architecture

```text
Financial analytics ───────────────→ Capacity
                   └───────────────→ Capital
Company profile ───────────────────→ Character
Explicit stored-page security text → Collateral
Business profile + verified domain → Conditions
                         All sections
                              ↓
              5 Cs evidence assessment
                              ↓
       completeness + confidence + review items
```

`FiveCsAssessmentService` selects the latest Day 10 assessment for each requested statement scope and loads its referenced Day 8 analysis and Day 9 trend runs. Capacity and Capital never recalculate source ratios. Character uses company identity and internal reporting evidence without personality or integrity inference. Collateral uses `collateral_evidence_extractor_v1` against existing page text and requires explicit security wording. Conditions distinguishes company-specific evidence from unavailable external research. Day 14 fusion is not a prerequisite.

`five_cs_assessments` stores immutable source-run identities, versions, input hash, overall availability, confidence, and qualitative status. `five_cs_sections` stores one normalized section row with deterministic summary and observation counts. `five_cs_evidence` stores the source type and reference, optional page, raw or normalized value, impact, status, and confidence. `five_cs_review_items` records unresolved missing or conflicting evidence. Exact document, scope, sources, page fingerprints, policy, and engine return the existing assessment; changed inputs create a new derived graph.

## Day 16 external research architecture

```text
Verified Company Profile
  → versioned Query Builder
  → fixture or configured Research Provider
  → URL/content safety + source normalization
  → entity resolution + quality + freshness
  → immutable source and evidence records
  → deduplicated, corroborated or conflicting findings
  → Character / Conditions candidates + future RAG
```

`research_runs` binds identity, requested scope, provider, policies, and versions with an input hash. Recent identical runs are reused; forced refresh creates a new immutable version. Queries, sources, evidence, findings, and finding-source edges form the complete lineage. Wrong entities and duplicate content remain visible as rejected or duplicate sources but cannot inflate evidence. Partial source failure does not fail successful evidence. Research has no write path into Day 15 tables.

## Day 17 recommendation preparation architecture

```text
Day 15 immutable 5 Cs + eligible Day 16 findings
  → versioned Character and Conditions refresh
  → copied Capacity, Capital, and Collateral evidence
  → immutable five_cs_engine_v2 assessment + refresh lineage

Day 10 deterministic assessment + refreshed 5 Cs + Day 16 research
  + optional Day 14 experimental context
  → factors + critical flags + missing evidence + review items
  → neutral readiness status + conservative confidence
```

`five_cs_refresh_runs` links base and refreshed assessments to a research run and input hash. `five_cs_research_evidence_links` connects each admitted observation to the exact research finding and evidence. `credit_recommendation_preparations` owns the derived readiness record, while factors and review items remain separate immutable children. The engine never updates Day 10, Day 14, Day 15, or Day 16 records.

## Day 18 human review architecture

```text
Recommendation Preparation → Credit Policy Gates → System Recommendation
  → Open Policy Exceptions → Human Review Package → Human decision remains unset

Verified Financial Values → Independent Limit Methods
  → Minimum eligible cap → Analytical Exposure Ceiling → Human Review
```

Decision records, gates, exceptions, checklist items, limit preparations, and limit methods are immutable derived rows. Experimental ML is context with zero weight. A human credit officer remains the final authority.


## Day 19 human governance

```text
Day 18 Decision Support
        ↓
Human Review Case
        ↓
Evidence Acknowledgement / Checklist / RFI
        ↓
Policy Exception Actions
        ↓
Explicit Human Decision
        ↓
Immutable Decision History

Review Case
        ↓
Versioned Committee Package
        ↓
Future Committee Decision Workflow
```

Review cases reference a fixed decision-support ID. Governance records are stored separately from analytical records. Backend authorization reads the versioned development authority policy, while audit records preserve the human actor for assignments, review activity, exception actions, decisions, overrides, and committee preparation.

## Day 20 report architecture

```text
Fixed Day 19 Review Basis
        ↓
Deterministic Input Hash
        ↓
Immutable Report Snapshot + Source Links
        ↓
Versioned Template + Report Renderer
        ↓
PDF or JSON Artifact + SHA-256
        ↓
Role-Governed Finalization / Explicit Supersession
```

`generated_reports` is the report identity and lifecycle record. `report_snapshots` freezes the exact serialized inputs used by the renderer. `report_source_links` identifies the analytical, research, governance, page, gate, exception, and committee records that support the report. `report_artifacts` stores the safe relative path, MIME type, format, size, and digest. `report_finalization_actions` records the human actor and rationale for issuance and supersession.

The reporting service reads prior stages and never updates them. Idempotency includes the snapshot content, report type, artifact format, template version, and renderer version. Finalization changes report governance state without regenerating bytes. Supersession links a finalized version to a newer generated or finalized version while retaining both artifacts.

## Day 21 RAG architecture

```text
Immutable internal records + untrusted document/research text
        ↓ sanitize, filter, version, chunk
Company-scoped immutable chunks → deterministic embedding abstraction
        ↓
PostgreSQL JSON vectors + keyword fields
        ↓ semantic + keyword + priority + confidence + current-state scoring
Ranked retrieval results → policy-controlled answer provider
        ↓
Grounded answer + claim citations + status + audit + feedback
```

Every chunk records its company, original source identity and version, section, page, period, scope, confidence, source priority, and current flag. A changed source creates a new chunk and marks the previous version historical. Exact manifests return the existing index run. Query, retrieval, answer, citation, chat, and feedback records preserve the full analyst lineage. Embedding and answer providers are interfaces; Day 21 uses deterministic offline implementations and requires no external model service.

## Day 22 stock foundation

```text
Uploaded Company → Verified Domain Classification → Indian Listed Universe
  → Explainable Peer Discovery → Peer Group → Primary/Secondary Listings
  → Provider Market Data Run → Versioned Daily OHLCV
```

`listed_companies` represents a legal entity while `stock_listings` preserves each NSE or BSE identity. ISIN resolves dual listings to one company. Peer groups freeze classification, policy, engine, and universe snapshot lineage. Market data providers remain interchangeable and one symbol failure is isolated in `market_data_errors`.

## Day 23 equity analytics architecture

```text
Listed Company → Provider Fundamentals → Availability Gate → Validation
  → As-of Market Price → Valuation → Peer/Industry/Sector Metrics
  → Historical Feature Store → Future Stock ML
```

Reported fundamentals, valuation outputs, relative observations, and features remain separate versioned records. Valuation and feature input tables retain the exact price, fundamental, and relative-metric identities used. Relative runs keep each comparison group separately identifiable.
