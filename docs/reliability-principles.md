# Reliability principles

- Keep process liveness independent of infrastructure and report degraded database state explicitly.
- Validate configuration at startup and keep secret values out of logs.
- Return stable, typed API responses and generic error messages for unexpected failures.
- Log structured events with UTC timestamps.
- Keep future component states honest: planned means unavailable today.
- Add evidence, model version, lineage, and analyst override records alongside later domain features.
- Use migrations for every schema change; never modify persistent structure only by ORM changes.
- Keep binary documents out of PostgreSQL and retain historical analysis records.
- Require a dedicated test database for destructive migration and constraint tests.
- Keep multi-record writes within a caller-owned transaction and roll back on failure.
- Keep physical files and document metadata consistent using compensating cleanup on failures.
- Treat SHA-256 as exact-content identity within a company; enforce the scope in PostgreSQL.
- Never use client filenames to choose storage paths, and never trust client-side validation.
- Validate PDF extension, MIME type, signature, nonzero content, and configured size limit.
- Never log raw file contents, credentials, or full local storage paths.
- Add malware scanning and crash-reconciliation tooling in later hardening work.

## Day 4 parsing guarantees

- OCR is a fallback for eligible pages, never the default for the whole PDF.
- Failed or unavailable OCR never fabricates page text.
- Parsing never modifies or deletes the original uploaded PDF, including after parser failure.
- Page numbering is stable and starts at 1; parser version and extraction method are persisted with each page.
- Partial extraction is explicit. Blank pages remain represented and are not treated as OCR failures.
- Repeated parse calls are idempotent. A unique document and page number constraint protects against duplicates.
- Page text retains document and page provenance. Logs and audit metadata exclude extracted text and OCR images.
- An abrupt process crash can leave `PARSING` until operator recovery; background scheduling and recovery are later work.

## Day 5 profile guarantees

- No trusted profile fact exists without a source page and human-readable evidence snippet.
- The upload label is compared with document evidence and is never silently accepted or overwritten.
- Subsidiary, auditor, customer, bank, and supplier contexts are excluded from primary-name rules.
- Strong identity conflicts remain explicit; low-confidence fields are not promoted to verified.
- Missing facts remain unavailable. Country defaults from Company are not presented as document evidence.
- Extraction changes neither the PDF nor stored `DocumentPage` text.
- Repeated extraction is idempotent by document and extractor version.
- Source page numbers remain 1-based, and extractor versions are persisted.
- Profile and evidence rows commit together; persistence errors roll them back together.

## Day 6 ML guarantees

- Domain labels are inferred from uploaded-document business evidence, never a manually selected domain.
- Taxonomy, dataset, model, and input-builder versions are recorded for every classification.
- Grouped splitting keeps a company in one partition and rejects exact-input leakage across partitions.
- All snapshot examples are marked `SYNTHETIC`; their measured metrics are development-only.
- Logistic Regression uses its probability output; the Linear SVM candidate is probability-calibrated before comparison. These small-data probabilities are not a production calibration guarantee.
- Low confidence, close alternatives, and profiles needing review cannot become verified classifications.
- Model outputs must map to one valid taxonomy path. Missing artifacts and version mismatches fail explicitly.
- A failed candidate training run does not deactivate the previous active model.
- Classification input is reproducible from verified profile fields and has a stored SHA-256 digest.
- Prediction evidence links point only to fields included in the model input; original PDFs, pages, and profile evidence remain unchanged.

## Day 7 financial guarantees

- A financial value has source page, raw label, raw value, reporting column, evidence snippet, confidence, status, extractor version, and taxonomy version.
- Explicit standalone and consolidated scope remain separate. Conflicting like-scope, like-period values are preserved and flagged.
- A dash or NIL remains unavailable; a numeric zero is zero. EPS is not multiplied by the statement currency unit.
- OCR values receive a deterministic confidence penalty. Failed OCR and partial parsing prevent an overall verified claim.
- One transaction writes the run, statements, line items, and audit events. A document lock and unique input fingerprint prevent repeat inserts.
- The service reads existing page text only, independent of the domain model; it never reparses or alters source content.

## Day 8 analysis guarantees

- Monetary arithmetic uses Python `Decimal` and PostgreSQL `NUMERIC`; display rounding is separate from stored precision.
- Unit conversion preserves the stated currency. There is no implicit FX conversion.
- Ratio inputs share company, scope, fiscal year, and compatible currency. Conflicting inputs block only dependent ratios.
- Derived debt and revenue aliases store formulas and input IDs. Ratio inputs have foreign keys to normalized values.
- Zero denominators produce unavailable results and issues. Negative equity or EBITDA produces a not-meaningful leverage ratio.
- Ratio confidence is the minimum input confidence; safe derived values receive a confidence penalty.
- The analysis run, normalized values, issues, ratios, ratio inputs, and audit events commit or roll back together.
- Input fingerprints and version keys make identical analysis idempotent and changed line items stale by construction.
- Completeness indicates data coverage only. No ratio is interpreted as favorable or unfavorable.

## Day 9 trend and anomaly guarantees

- Trend analysis uses persisted normalized values and ratios and never recalculates from PDF text.
- Company, reporting scope, metric, and currency compatibility remain isolated.
- Fiscal periods are parsed chronologically; lexical ordering is not used as a time model.
- Zero-base growth never returns infinity, and negative profit bases use explicit state transitions.
- Margins and return ratios use percentage-point movement for their primary change.
- Missing intermediate periods remain missing and reduce confidence; values are never interpolated.
- Trend and anomaly confidence cannot exceed the weakest critical input.
- Anomaly thresholds and rule interpretation are stored under `financial_anomaly_rules_v1`.
- Alerts describe observed relationships without claiming causation or issuing a credit decision.

## Day 10 credit risk guarantees

- Policy, feature builder, and score engine versions are persisted with every assessment.
- Statement scopes remain separate and every input is a persisted Day 5, Day 8, or Day 9 row.
- Minimum component and overall coverage gates prevent false precision; insufficient inputs produce no score or band.
- Verified industry evidence contributes only availability and confidence. No sector label carries a risk assumption.
- Overlapping persistent and single-period alerts are suppressed deterministically.
- Score inputs and reasons are immutable, auditable, and traceable to page evidence.
- The result is analytical support and never an approval, rejection, amount, pricing, collateral, or lending decision.
- A unique input fingerprint makes repeated analysis idempotent and changed Day 8 data stale by construction.
- Day 8 values, ratios, financial line items, document pages, and source PDFs remain immutable.
- The run, trends, inputs, anomalies, lineage links, and audit events commit or roll back together.

## Day 11 credit ML dataset guarantees

- Risk bands and Day 10 rule outputs are never ground-truth labels.
- A negative label requires verified follow-up through the complete prediction horizon; incomplete follow-up is censored.
- Feature snapshots use only persisted rows available by the observation cutoff and never carry company IDs, target values, outcome dates, or split labels in the feature map.
- Missing and unverified inputs remain missing. Conflicts are not silently selected.
- Companies cannot cross train, validation, and test partitions; partitions are chronological by company group.
- Company overlap, duplicate observations, exact cross-partition feature matches, target fields, outcome dates, and future source timestamps are publication-blocking checks.
- Dataset versions, policy versions, split policy, feature schema, feature builder, artifact hash, label quality, exclusions, missingness, and source lineage are persisted.
- Unknown original publication dates produce `NEEDS_REVIEW`; synthetic-only fixtures can validate the pipeline but cannot establish training or production readiness.
- Raw snapshots preserve nulls, numeric values, and categories without scaling, encoding, imputation, balancing, or resampling; Day 12 preprocessing must be fitted on training data only.
- Label quality keeps verified real, curated real, proxy, synthetic, and unknown evidence distinct in stored examples and reports.
- Day 11 performs no credit model training, probability calibration, inference, approval, or lending decision.

## Day 12 credit ML training guarantees

- Dataset SHA-256 and critical leakage status are verified before training.
- Imputers, encoders, scalers, class weights, and calibration are fitted from training rows only.
- Validation metrics drive model selection; final test labels never influence selection or calibration.
- Undefined metrics remain unavailable with a reason. Tiny or single-class splits never receive fabricated AUC values.
- Artifacts contain the complete inference pipeline and must pass SHA-256 verification before loading.
- Failed candidates cannot replace the selected model; successful candidate runs remain independently recorded.
- Pipeline-validation models cannot become production ready through the Day 12 training service.
- Coefficients and feature importance are synthetic-data pipeline diagnostics, not causal or underwriting evidence.
- Day 10 deterministic scoring remains independent and unchanged.
- Development inference always discloses readiness and forbids production use; it does not issue a lending decision.

## Day 13 credit ML evaluation guarantees

- Every evaluation window trains only on observations earlier than its evaluation period.
- Preprocessing, class handling, model fitting, and calibration are recreated independently per window.
- Calibration never receives future evaluation labels, and window estimators never enter the active registry.
- Insufficient and single-class windows remain explicit; unsupported metrics are never fabricated.
- Aggregate metrics exclude undefined values and retain their valid-window support.
- PSI, categorical shift, prediction drift, and calibration drift are development diagnostics rather than lending decisions or universal regulatory thresholds.
- Model disagreement remains visible and is not automatically averaged or resolved.
- The Day 10 rule score may be converted to a ranking index but is never represented as calibrated probability of default.
- Tiny samples cannot produce stability claims; fewer than three valid windows yields `INSUFFICIENT_DATA`.
- Evaluation input hashing makes identical runs idempotent and changed policies produce different identities.
- Synthetic-only data, non-production model readiness, missing comparison support, and critical drift block fusion.
- Evaluation cannot promote models, change Day 10 assessments, modify datasets, or create a hybrid score.

## Day 14 fusion experiment guarantees

- Fusion is a separate derived layer; it never rewrites a Day 10 score, Day 12 probability or artifact, or Day 13 evaluation.
- The API accepts source IDs and a strategy. It does not accept client-supplied scores or probabilities.
- Artifact SHA-256 and bundle metadata must verify before ML inference. A copied or unregistered probability is never used as a substitute.
- Rule confidence, effective coverage, feature lineage, model readiness, drift, candidate disagreement, and rule/ML gap are explicit gates.
- Data completeness affects availability and confidence and is not converted directly into borrower risk.
- High rule/ML disagreement blocks numeric output for every current strategy; consensus mode also withholds output at moderate disagreement.
- Rule-only fallback references the immutable Day 10 result. Invalid rule evidence or insufficient coverage produces no reliable output and never a neutral default.
- The current synthetic-only pipeline caps fusion confidence at 0.50 and always sets `production_use_permitted` to false.
- Weights, component values, contributions, penalties, reasons, fallback state, policy versions, and lineage remain visible.
- Rule and ML signals may overlap; weighted components are not statistically independent evidence.
- Hybrid indices are not calibrated probabilities. Hybrid Brier score and strategy-winner claims require a labelled historical fusion series and remain unavailable today.
- Input hashing and a database uniqueness constraint make exact experiment requests idempotent.
- Readiness, start, completion, block, fallback, disagreement review, and sanitized failure events are auditable without raw document content.
- Fusion never approves or rejects credit, sets pricing or limits, requests collateral, or makes a lending decision.

## Day 15 5 Cs evidence guarantees

- No 5 C receives evidence, confidence, or completeness credit for a fact that is absent.
- Missing Character promoter, legal, bureau, and repayment-history evidence remains explicitly unavailable.
- Character describes evidence availability and consistency without inferring honesty, trustworthiness, intent, competence, integrity, or reputation.
- Capacity and Capital consume persisted Day 8–10 analytics and do not recalculate ratios from raw tables or document text.
- Completeness measures evidence availability and remains separate from financial strength or credit quality.
- Generic assets, PPE, property, plant, machinery, and book value are never treated as collateral without explicit security wording.
- A security mention does not establish collateral value, coverage, LTV, enforceability, or independent valuation.
- Conditions separates company-specific trends from external industry, regulatory, sector, and macroeconomic research.
- External evidence placeholders have no fabricated source reference.
- Every available observation retains its source object and optional page lineage.
- Summaries use fixed templates and structured facts without an external LLM.
- Scope-specific Capacity and Capital evidence never mixes standalone and consolidated records.
- Input hashing makes exact analysis idempotent and preserves stale historical assessments when sources change.
- Day 15 does not depend on experimental fusion and never changes Day 5–14 records.
- No total 5 Cs credit score, loan approval, rejection, sanction, amount, rate, collateral requirement, or final lending decision is produced.

## Day 16 external research guarantees

- Every external finding requires stored source evidence; a source failure creates no finding.
- Absence of search results is not evidence of absence or low risk.
- Allegations and reported investigations remain allegations and investigations; they are never promoted to convictions or fraud findings.
- Publisher class, quality tier, entity-match confidence, freshness, and source status are explicit.
- Same-name companies are not merged automatically, and ambiguous matches require review.
- Publication, event, and retrieval dates remain separate.
- Canonical URLs, content hashes, and copied-text clusters prevent syndicated copies from inflating corroboration.
- Stale and historical sources remain immutable and labeled.
- Character and Conditions candidates never overwrite Day 15 sections automatically.
- External content is never executed. HTTP(S), DNS/IP, redirect, content-type, size, timeout, retry, and backoff controls constrain retrieval.
- Tests use deterministic fixtures and never require the live web.
- No research output is a lending decision, stock recommendation, or generic sentiment score.

## Day 17 evidence and readiness controls

- Base 5 Cs assessments and every upstream financial or research record remain immutable.
- Only policy-eligible findings can alter refreshed Character or Conditions evidence.
- Capacity and Capital retain the financial pipeline as their authority; research cannot rewrite their values.
- Collateral remains evidence based and is never valued from external reporting.
- Missing research is represented as missing coverage and never interpreted as low risk.
- Unresolved conflicts take precedence over ordinary readiness and cap confidence.
- Experimental fusion remains visibly separate and has no numerical effect on readiness or confidence.
- Every recommendation factor names its source type and source record.
- Prepared status means readiness for later human or policy review; it never means a lending outcome.

## Day 18 human review safeguards

- System recommendation is not a final lending decision; a qualified human reviewer remains the authority.
- Protected personal attributes and intentional protected-trait proxies are excluded.
- Synthetic ML and experimental fusion cannot influence the policy state, confidence, or limit.
- Policy thresholds, exception rules, and limit formulas are versioned.
- Blocking gates trigger explicit review rather than silent rejection.
- Missing evidence never becomes zero, and missing research never becomes low risk.
- An analytical ceiling is not a sanctioned amount, and collateral is used only when independently verified.
- Historical decision-support graphs remain immutable with gate and limit-method source lineage.

## Human credit governance

- Human decisions are explicit and are never inferred from system recommendations, scores, ML, or workflow state.
- System recommendations and human decisions remain separate historical facts.
- Every decision, exception action, assignment, and committee action identifies its human actor.
- Human decisions and material overrides require rationale.
- An approved exception is not a credit approval.
- The analytical ceiling is not the human-approved limit.
- Role permissions, ownership, authority limits, and configured maker-checker controls are enforced in backend services.
- Review comments and action histories are append-only.
- Superseding decisions create new versions and preserve the earlier decision.
- Committee packages are immutable after `READY`; meaningful input changes create a new version.
- Blocking RFIs and unresolved review items prevent readiness where policy requires it.
- A newer analysis raises an updated-analysis warning and never silently replaces the review basis.
- Day 10 through Day 18 analytical records remain unchanged by governance actions.
- Protected personal attributes are excluded from the workflow and development authority policy.
- Day 19 performs no borrower notification, pricing, facility booking, sanction generation, or disbursement.

## Day 20 report governance guarantees

- A report renders persisted data from one fixed review basis and introduces no new credit score, recommendation, approval, rejection, limit, pricing, collateral value, or sanction term.
- Missing values remain visibly unavailable; the renderer never substitutes zero or invents supporting evidence.
- Template version, renderer version, input hash, snapshot hash, artifact SHA-256, byte size, format, and MIME type are persisted.
- Exact repeated inputs are idempotent. Material input changes create a later report version.
- Generated files use a bounded safe path beneath the configured storage root. Downloads verify path containment and SHA-256 before returning bytes.
- Report preview and download require an active authorized actor. Finalization and supersession use report-type-specific backend roles.
- Finalization does not regenerate an artifact. Supersession preserves the prior bytes, status history, actor, rationale, and explicit successor link.
- Report snapshots exclude user credentials and do not serialize user records.
- Experimental ML remains labeled pipeline-only with zero decision weight.
- The reporting layer never changes Day 10 through Day 19 analytical or governance records.
- Local filesystem storage and the development authority policy are not production substitutes for enterprise identity, durable object storage, retention, signing, or jurisdiction-specific reporting controls.

## Day 21 RAG reliability guarantees

- RAG is a derived read layer and does not update source financial, research, credit, review, decision, committee, or report records.
- Chunk and embedding versions, manifest hashes, source identities, and current or historical state are persisted. Exact rebuilds are idempotent.
- Every retrieval is company scoped. Optional financial scope and period filters are recorded with the query.
- The default embedding and answer providers are deterministic and operate offline. PostgreSQL JSON vectors provide a portable fallback before a governed vector extension is introduced.
- Answers cite persisted chunks. Missing, conflicting, and human-review-required states remain explicit, and unsupported claim counts are stored.
- The assistant reports system recommendations and recorded human decisions as different facts. It cannot choose a sanctioned limit or create an approval, decline, price, facility, or disbursement.
- Document and external research text is untrusted. Control characters, scripts, known prompt-injection phrases, and configured secret terms are removed or excluded before indexing.
- Analyst roles are checked by backend services; raw retrieval diagnostics require an administrative role.
- Evaluation reports observed retrieval recall, reciprocal rank, hit rate, citation precision and recall, citation coverage, and unsupported claim rate. Metrics are never hard-coded as passing.
- Day 21 does not provide production identity, a production LLM, jurisdiction-specific legal conclusions, semantic reranking, or a native vector database.

## Day 22 stock-data guarantees

- Listed companies and exchange listings are separate entities; dual listings are retained under one ISIN-backed company.
- Similar names alone never merge identities or create peers. Inactive and non-equity securities are excluded.
- Peer ranking persists every weighted component and rationale. Low-confidence classifications cannot produce high-confidence peers.
- Prices use Decimal/NUMERIC, preserve provider versions, and never fabricate weekend or holiday candles.
- One symbol failure produces a symbol error and a partial run without discarding successful symbols.
- Missing prices do not remove an otherwise valid peer.
- Peer similarity is business comparability only. Day 22 creates no valuation, stock ML, target price, forecast, Stock Intelligence Score, or BUY/SELL/HOLD signal.

## Day 23 equity analytics guarantees

- Listed-company fundamentals remain separate from borrower financial statements.
- Availability date controls historical eligibility; period end alone never makes data eligible.
- Future fundamentals, prices, and member analytics are excluded from as-of calculations.
- Valuation inputs and feature inputs retain exact record lineage.
- Negative earnings, non-positive equity, and non-positive EBITDA are explicit not-meaningful states; unavailable values are never represented as zero.
- Relative comparisons require the configured minimum group size and remain descriptive statistics.
- Feature runs are input-hash idempotent and reproducible for an as-of date.
- Day 23 generates no stock recommendation, target price, forecast, stock ML model, or Stock Intelligence Score.
