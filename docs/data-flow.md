# Data flow

Day 3 upload and persistence lineage:

```text
PDF upload → extension/MIME/signature/size validation → streaming SHA-256
  ↓
Company lookup or creation → duplicate check within company
  ↓
Analysis Job (PENDING) → Local file → Document Metadata (UPLOADED) → Audit Log
```

Repositories flush records into the upload transaction. The transaction commits only after the file and audit record are ready; a failure rolls back database writes and triggers file cleanup. A document row contains metadata and a logical storage URI, never PDF bytes. Duplicate attempts create no new job, document, or file. The status view distinguishes API unavailability from degraded database or storage readiness.

Later lineage may add feature snapshots, credit and stock predictions, and reports to the analysis job. Financial statements and evidence rows now exist.

## Day 4 page extraction lineage

```text
Company → AnalysisJob → Document → DocumentPage
                                  ↓
                 Text + method + quality + parser version
                                  ↓
                         Future page evidence
```

The parse call reads the unchanged stored PDF. Native extraction runs first on every page. Pages with poor native text and meaningful visual content use OCR if the provider is available. Legitimate blank pages remain explicit `BLANK` rows. A failed OCR page keeps empty text and an error code. All page rows and the summary commit together after parsing, with a document-level audit event. Repeated calls return the existing summary without duplicating rows or events. Later extracted facts can reference `document_id` and 1-based `page_number`.


## Day 5 evidence lineage

```text
DocumentPage → candidate evidence → ExtractedField → confidence and status → CompanyProfile
```

An extracted field points to its source `document_id`, `document_page_id`, and 1-based `page_number`. Verified profile columns are populated only from verified candidates. Missing values remain null; strong legal-name conflicts preserve both candidates and leave the canonical name unset. Uploaded-name mismatch triggers review and an audit event. Field evidence is displayed on demand rather than embedding full pages in a summary.

## Day 6 model lineage

```text
ExtractedField business evidence → normalized inference text → input hash
  → active model + dataset snapshot + taxonomy → classification + confidence
  → field/page evidence links
```

Training snapshots are validated against the taxonomy and split by company. Exact normalized input hashes, example IDs, and company keys cannot cross train, validation, or test boundaries. Inference filters fields to one CompanyProfile and the business field names only. A stored classification refers to a specific model and input hash; if profile evidence changes, retrieval reports it as stale. The full-path label comes from one taxonomy row, preventing inconsistent parent-child combinations.

## Day 7 financial evidence lineage

```text
Document → DocumentPage → FinancialExtractionRun(input_hash, versions)
                        → FinancialStatement(type, scope, period, unit)
                        → FinancialLineItem(raw label/value, Decimal, status, snippet, page ID)
```

The extraction run records the exact ordered page input digest. Repeating an identical request returns stored rows. A changed page yields a new run; document statement listing selects the latest run. Each comparative year is a separate statement row, preserving its raw column header on each line item. Page text and source PDFs are never updated during extraction.

## Day 8 analytical lineage

```text
FinancialLineItem ID + raw Decimal + unit + currency + status + scope + year
  → analysis input SHA-256
  → selected normalized base-currency value or explicit unusable status
  → validations and derived values
  → ratio formula + calculation basis + normalized input links
  → original line item → DocumentPage evidence
```

Calculations never cross scope or fiscal year. Average-balance ratios may additionally link the prior-year value from the same scope and currency. Same-currency units are normalized before comparison; different currencies are not combined. Repeating the same versions and fingerprint returns the existing graph.

## Day 9 trend and anomaly lineage

```text
Persisted normalized value or ratio series
  → parsed chronological ordering and period validation
  → absolute, YoY, percentage-point, state, and CAGR calculations
  → FinancialTrend + per-period source links
  → cross-metric versioned anomaly rule
  → FinancialAnomaly + supporting trend links
  → normalized value / ratio inputs → FinancialLineItem → DocumentPage
```

The Day 9 input digest includes IDs, values, statuses, confidence, currency, calculation basis, and Day 8 versions. Scope and currency partitions are never combined. Missing periods remain explicit and do not become invented values. Repeating the same digest and versions returns the same run; a changed Day 8 output creates a new immutable derived graph.

## Day 10 credit lineage

`CompanyProfile` + optional verified `DomainClassification` + `FinancialAnalysisRun` + `FinancialTrendRun` → scoped credit features → five component scores → coverage gate and renormalized overall score → risk band.

Every consumed source row receives a `credit_assessment_inputs` edge. Each policy reason may link to the input that triggered it. Evidence retrieval follows ratio inputs, trend inputs, and anomaly inputs until it reaches normalized values and financial line-item pages; profile and domain inputs follow extracted-field evidence. No Day 10 path reads the source PDF or modifies upstream rows.

## Day 11 credit ML dataset lineage

```text
Observation date + feature cutoff + prediction horizon
  → persisted Day 8/9 features available by the cutoff
  → optional persisted Day 10 rule score features
  → immutable feature snapshot + typed source edges
Verified outcome evidence through the horizon → label or censoring decision
  → company-grouped chronological split → leakage gate
  → versioned JSONL + metadata + SHA-256 + dataset report
```

The feature cutoff is enforced against system creation timestamps and fiscal periods. Unknown original filing publication dates remain an explicit availability warning. Censored and conflicting observations never enter a training partition. Critical leakage prevents files and dataset records from being published.

## Day 12 model training lineage

```text
Dataset snapshot + registered SHA-256 + leakage report
  → load fixed TRAIN / VALIDATION / TEST rows
  → fit imputer, encoder, scaler, class weighting, and calibration on TRAIN only
  → evaluate every candidate on VALIDATION
  → select without test results
  → evaluate selected baseline once on locked TEST
  → persist runs + split metrics + metadata + full pipeline artifact + artifact SHA-256
  → verify artifact before development inference
```

The inference foundation consumes an eligible feature snapshot through the saved preprocessing pipeline and returns probability, threshold class, model and dataset lineage, and `production_use_permitted: false`. It does not update Day 10 assessments or produce a lending decision.

## Day 13 walk-forward evaluation lineage

```text
Historical dataset ordered by observation date
  → earlier training window
  → fresh train-only preprocessing, model, and calibration
  → later evaluation window
  → per-model metrics and probabilities
  → aggregate stability + feature/prediction/calibration drift
  → model disagreement + optional Day 10 rule comparison
  → fusion-readiness status and blocking reasons
```

Expanding windows retain all eligible earlier periods; rolling windows retain the configured trailing periods. Strict window-level company isolation removes evaluation companies from that window's training set. Skipped windows preserve counts, dates, and reasons. The evaluation hash binds the dataset digest and every relevant policy version. Derived evaluation rows do not update the source dataset, active model registry, or Day 10 assessment.

## Day 14 fusion experiment lineage

```text
CreditAssessment ID + score + confidence + coverage + input hash
  → rule risk transformation (ranking index, not PD)
Active MLModel ID + artifact SHA-256 + CreditMLFeatureSnapshot ID/hash
  → verified CreditMLInferenceService probability
Latest CreditMLEvaluationRun ID/hash
  → drift + model disagreement + walk-forward and real-outcome gates
Complete fusion policy + requested strategy
  → deterministic experiment input SHA-256
  → contribution math + reasons + confidence penalties
  → experimental result / review / rule-only reference / no reliable output
```

The experiment stores separate input edges for the Day 10 assessment, Day 12 model prediction and snapshot, and Day 13 evaluation. Exact inputs, policy, readiness state, and strategy return the same row. A changed source, prediction, artifact, evaluation, policy, or strategy creates a new experiment. No edge updates its source. Diagnostic comparison is pipeline-only and never treats the rule index or hybrid index as calibrated PD.

## Day 15 5 Cs evidence lineage

```text
Source evidence
  → section-specific evidence builder
  → structured observation and impact
  → conservative confidence
  → availability-based completeness
  → qualitative section status
  → deterministic summary
  → open review item where evidence is missing or conflicting
```

Capacity and Capital evidence references persisted credit subscores, normalized values, ratios, trends, and anomalies. Existing ratio, trend, and anomaly input edges continue the path to normalized values, financial line items, and `DocumentPage`. Character references the company profile and explicit reporting pages. Collateral references only pages with explicit security wording. Conditions references the company profile, verified domain classification, and company-specific trends or anomalies. External placeholders carry no fabricated source reference.

The assessment input hash includes profile identity and version, Day 8 and Day 9 run identities, the Day 10 assessment and input hash, optional domain model lineage, stored-page fingerprints, and the complete Day 15 policy. No source record is updated. A newer Day 10 or financial input produces a different assessment while the earlier graph remains available.

## Day 16 research lineage

```text
Entity → Query → Provider Result → Safe Source Fetch / Fixture Snapshot
  → Normalize URL and content → Entity Match → Evidence
  → Deduplicate → Corroborate / Contradiction Check → Finding
  → Character or Conditions Candidate
```

Publication date describes the source, event date describes the reported event, and retrieval time describes this system's observation. These values are never merged. Every evidence row has one source foreign key, and every finding-source edge names both its evidence and source. A wrong-company result stops before evidence creation. Copied articles share a content hash cluster and do not count as independent confirmations.

## Day 17 refresh and recommendation lineage

```text
Refreshed Character / Conditions → FiveCsResearchEvidenceLink
  → ResearchFinding → ResearchEvidence → ResearchSource → URL, publisher, event date

Refreshed Capacity / Capital / Collateral → copied FiveCsEvidence
  → Day 15 source reference → Day 8–10 input graph → DocumentPage

CreditRecommendationPreparation
  → CreditAssessment + refreshed FiveCsAssessment + ResearchRun
  → optional CreditFusionExperiment (experimental context only)
  → factors and review items
```

The refresh hash covers the base assessment, accepted finding identities and states, research input, policy, and engine. The recommendation hash covers Day 10, refreshed 5 Cs, research, optional fusion identity, policy, and engine. Exact repeats return the persisted graph; changed inputs create a new graph.

## Day 18 decision and limit flow

```text
Recommendation → Gate Evaluation → Policy Exceptions
  → Decision-Support Status → Review Checklist

Normalized Financial Values → Cash Flow / Revenue / Leverage / Working Capital
  + verified collateral when available → Limit Preparation → Human Review
```

The decision hash includes the Day 17 preparation, Day 10 and refreshed 5 Cs hashes, research, financial values, scope, and both Day 18 policies. Limit method inputs retain source value IDs. Missing existing exposure stays missing and projected interest coverage stays unavailable without a supported rate assumption.

## Day 19 review flow

```text
System Recommendation
      ↓
Assigned Reviewer
      ↓
Comments / Evidence / Checklist
      ↓
Information Requests / Exception Actions
      ↓
Human Decision or Committee Referral
      ↓
Decision History and Timeline
```

Committee inputs are hashed from the fixed review basis and current governance records. Meaningful changes create another package version. A ready package is retained unchanged.

## Day 20 reporting flow

```text
Credit Review Case + Human Decision History + Committee Package
  + Day 10 Assessment + Financial Ratios / Trends / Anomalies
  + Day 15/17 Five Cs + Day 16 Research
  + Day 18 Gates / Exceptions / Analytical Limit
        ↓
Canonical Snapshot + Input Hash
        ↓
CAM / Committee Memo / Evidence Pack / JSON Export
        ↓
Artifact SHA-256 + Source Links + Audit Event
        ↓
Authorized Preview / Download / Finalization / Supersession
```

The snapshot preserves missing values as unavailable and includes the selected upstream record IDs. Document pages, financial outputs, research sources and findings, policy gates, exceptions, review activity, and decision history receive direct report-source edges. Existing upstream lineage continues from those records to extracted evidence and original pages. Newer analysis raises a warning in the snapshot; it never replaces the report basis automatically.

## Day 21 RAG and analyst flow

```text
Company records → source-specific chunk builder → immutable chunks → embeddings
Question + company/scope/period filters → hybrid ranker → selected context
Selected context → deterministic grounded answer → numbered citations
Question + ranks + scores + answer + citations → persistent audit lineage
```

The index includes document pages, company profiles, financial values, ratios, trends, anomalies, assessments, 5 Cs evidence, research, recommendation preparation, decision support, gates, exceptions, analytical limits, review activity, RFIs, human decisions, committee packages, and report snapshot navigation. Retrieval never crosses a company boundary. Scope and period constraints narrow or down-rank evidence while historical chunks remain available and visibly versioned.

## Day 22 peer and price flow

```text
Company Classification → Active Equity Candidate Filter → Similarity Components
  → Ranked Peer Group → Primary Listing Selection → Daily Market Data
```

Sector, industry, domain, sub-domain, business text, and product overlap remain separate persisted scores. The listing-to-run-to-price chain preserves exchange, symbol, provider, provider version, retrieval time, currency, and trading date.

## Day 23 fundamentals and feature flow

```text
Provider Fundamentals → Normalize → Availability-Date Gate
  → Market Price As-Of → Valuation → Relative Metrics → Feature Builder
```

For an as-of date, each company contributes only fundamentals published by that date and prices traded by that date. Every peer, industry, and sector member is subject to the same cutoff. Growth uses compatible prior periods. Momentum, volatility, liquidity, moving averages, and rolling drawdowns use historical prices only. Relative feature lineage points to the exact eligible relative-metric record.

## Day 24 stock ML research flow

```text
As-Of Feature Run → 63 Subsequent Trading Observations → Relative Return Label
  → Dataset Row and Feature Snapshot → Chronological Walk-Forward Assignment
  → Purge Overlap + Embargo → Train / Validate / Test → Persisted Diagnostics
```

Unavailable features remain null. Censored labels are retained for audit but excluded from training. The imputer and scaler fit only the training assignment, and label fields are blocked from the ordered feature catalog.

## Day 25 stock intelligence flow

```text
Eligible as-of features and research prediction
  → Component calculation → Bounded normalization → Weighted contributions
  → Confidence and coverage → Analytical score
  → Same-date ranking → Research priority
```

Missing components retain zero effective weight without redistributing their configured weight. Scores require minimum coverage. Ranking members all reference a score from the same as-of date, and the ranking hash covers the fixed universe and score-run inputs.

## Day 26 historical validation flow

```text
Historical Day 24 Row → Exact As-Of Day 25 Score and Ranking
  → Labeled/Censored Gate → Per-Date Spearman and Quantile Buckets
  → Component, Segment, Ablation, and Sensitivity Diagnostics
```

Only `LABELED` rows with an eligible score enter forward-performance diagnostics. `CENSORED` rows remain counted for transparency. Every cross-section uses one historical date; the underlying score retains its original availability-date and price-date gates. Quintiles require ten eligible companies and otherwise fall back to terciles only when that smaller grouping remains valid.
