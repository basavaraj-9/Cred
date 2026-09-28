# Company Intelligence Platform

## Day 23: fundamentals, valuation, and historical features

Day 23 adds provider-neutral listed-company fundamentals with explicit publication dates, deterministic valuation formulas, peer, industry, and sector context, and an as-of historical feature store. Every valuation selects the latest price and published fundamental available on or before its calculation date. Negative earnings, non-positive equity, and non-positive EBITDA produce explicit not-meaningful states. Relative metrics and features are descriptive analytical data and never produce BUY, SELL, HOLD, target-price, or return-forecast conclusions.

The development provider supplies deterministic annual periods without contacting a finance API. `stock_fundamental_normalizer_v1` preserves raw values, units, provider references, statement scope, currency, provenance, and normalized values. Publication availability, rather than period end, controls historical eligibility; an unknown publication date remains review restricted.

`stock_valuation_engine_v1` calculates market capitalization as price times shares, simplified enterprise value as market capitalization plus debt less cash, and supported price, enterprise, earnings, book, sales, cash-flow, and dividend ratios. `sector_metrics_policy_v1` produces deterministic ranks, inclusive percentiles, and population z-scores for eligible peer, industry, and sector members only when at least three valid observations exist.

`stock_features_v1` persists fundamental, growth, momentum, volatility, liquidity, moving-average, drawdown, peer-relative, and sector-relative features with exact source records. Fixture fundamentals, provider availability dates, limited corporate-action adjustments, and the absence of full free-float and historical share-count modeling limit the current analytics.

## Day 22: Indian listed peers and market data

Day 22 adds a normalized Indian listed-company universe with separate NSE/BSE listings, deterministic entity resolution, explainable domain-to-peer discovery, and provider-neutral daily OHLCV ingestion. The included development providers are deterministic fixtures, so tests and local demonstrations do not contact exchange websites. Prices preserve provider/version lineage and use PostgreSQL NUMERIC values. Peer similarity describes business comparability only and produces no valuation, target price, forecast, Stock Intelligence Score, or BUY/SELL/HOLD signal. The internal view is available at `/stock-intelligence`.

Day 21 foundation for a company intelligence and governed credit analysis platform. The current build carries source evidence through financial analysis, credit assessment, external research, human review, controlled reporting, and an evidence-grounded analyst assistant. Authentication remains planned.

## Requirements

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ or Docker Compose

## Run locally

Create a PostgreSQL database and copy `apps/backend/.env.example` to `apps/backend/.env`. Set `DATABASE_URL` to that database with your own credentials. The example password is a placeholder. For Compose, copy the root `.env.example` to `.env`, set `POSTGRES_PASSWORD`, and set `DATABASE_URL` to the same database using host `postgres` for the backend container. A host-running backend uses `localhost`. Start only PostgreSQL with `docker compose up -d postgres` if needed.

From `apps/backend`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --reload
```

From another terminal in `apps/frontend`:

```powershell
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open http://localhost:3000/upload to upload a PDF and http://localhost:3000/health to view status. The API health endpoint is at http://localhost:8000/api/v1/health; API docs are at http://localhost:8000/docs.

The internal model-validation summary is available at http://localhost:3000/model-validation. It reports development diagnostics and keeps production fusion explicitly blocked for synthetic-only datasets.

The analyst assistant is available at http://localhost:3000/analyst-assistant. Build a company index with an authorized internal user ID, then ask questions across document, financial, research, credit, workflow, decision, committee, and report evidence. Answers include persisted citations and never make or change a lending decision.

## Day 21: RAG and credit analyst assistant

Day 21 adds an immutable derived index over existing records. `credit_rag_index_v1` and `credit_rag_chunk_builder_v1` preserve source versions, company boundaries, periods, scope, status, confidence, and current or historical state. The default offline embedding provider is deterministic and stores vectors as portable JSON in PostgreSQL. The retrieval layer combines embedding similarity, keyword overlap, source priority, evidence confidence, and recency under `credit_rag_retrieval_policy_v1`.

`credit_analyst_query_classifier_v1` routes questions to relevant source families. `credit_analyst_prompt_v1` and `credit_analyst_answer_policy_v1` require cited answers, explicit insufficient or conflicting evidence states, and clear separation between system recommendations and human decisions. External text is treated as untrusted data, known instruction patterns and secrets are excluded from indexed context, and debug retrieval requires an administrative role. The deterministic answer provider supports offline testing; the provider interface allows a later governed LLM integration without changing retrieval or citation records.

The root `.env.example` lists all current environment variables. The backend reads `apps/backend/.env`; the frontend reads `apps/frontend/.env.local`. Change `FRONTEND_URL` when the frontend runs on another origin. The status page fetches from `API_INTERNAL_BASE_URL` on the server; use `http://backend:8000` inside Compose and `http://localhost:8000` when running locally. Rebuild the frontend after changing `NEXT_PUBLIC_API_BASE_URL` for future browser requests.

The health endpoint returns HTTP 200 with `healthy` when PostgreSQL answers `SELECT 1` and local storage is ready. It returns HTTP 200 with `degraded` when either dependency is unavailable. Database URLs and local paths are never included in responses. Connectivity alone does not prove migrations were applied; run them during setup.

`python -m alembic downgrade base` rolls back the Day 2 schema. It removes all five tables and their data; use it only on a disposable database. Reapply with `python -m alembic upgrade head`.

## PDF uploads

The backend accepts only `.pdf` files with MIME type `application/pdf`, a `%PDF-` signature, and nonzero content. The default limit is 50 MB, configured with `MAX_UPLOAD_SIZE_MB`. `LOCAL_STORAGE_PATH` defaults to the project `storage` directory; files are saved under `storage/uploads` using generated UUID names. PostgreSQL stores the original safe basename, SHA-256, logical `local://uploads/…` URI, status, and analysis association. Parsing stores page text separately; it never modifies the source PDF.

Exact duplicate content is rejected **within the same company**, including across analysis runs. The endpoint returns HTTP 409 with the existing document ID, and does not create another job, document, or file. The same bytes may be uploaded for a different company. A unique database constraint protects this policy during concurrent requests.

Example upload from PowerShell:

```powershell
curl.exe -F "company_legal_name=ABC Electrical Ltd" -F "file=@annual_report.pdf;type=application/pdf" http://localhost:8000/api/v1/documents/upload
```

`GET /api/v1/documents/{document_id}` returns metadata; `GET /api/v1/analysis/{analysis_id}/documents` lists metadata for one analysis. Neither endpoint returns file contents or storage paths.

## PDF parsing and OCR

PyMuPDF is installed with the backend requirements. After uploading a PDF, use **Parse document** on the upload page or call `POST /api/v1/documents/{document_id}/parse`. The call runs synchronously and returns a small summary; long or OCR-heavy reports may take time. Repeating the request returns the persisted result without adding pages or audit events. There is no forced reparse in Day 4.

The parser handles pages sequentially. It keeps usable native text, skips truly blank pages, and sends image or drawing pages with unusable text to OCR. A PDF with both native and OCR pages reports `HYBRID`. Text quality is a deterministic 0–1 score: 35% alphanumeric ratio, 30% printable ratio, 20% word count, and 15% text length, with penalties for replacement characters and repeated runs. Native text must also pass a minimum alphanumeric ratio and either the configured character minimum or a short-text rule on pages without significant image coverage. The defaults are in `apps/backend/.env.example`. Page text retains whitespace, numbers, and page provenance.

OCR uses the Tesseract command-line executable. Install Tesseract separately and ensure `tesseract` is on `PATH`, then set `OCR_ENABLED=true`. The parser checks availability at runtime. If it is unavailable, native pages still parse and pages requiring OCR are marked failed for review; no text is invented. `OCR_LANGUAGE`, `OCR_DPI`, and `OCR_TIMEOUT_SECONDS` tune fallback behavior. The status endpoint reports OCR availability separately from overall database and storage health.

`GET /api/v1/documents/{document_id}` includes `parser_status`, page count, method, version, and safe error details. `GET /api/v1/documents/{document_id}/pages` lists page metadata without the full text. `GET /api/v1/documents/{document_id}/pages/{page_number}` returns one page with its text. Page numbers start at 1.

Parser statuses: `NOT_STARTED` means no parse was requested; `PARSING` means work is in progress; `PARSED` means every page was extracted or blank; `PARTIAL` means some pages failed while others succeeded; `REVIEW_REQUIRED` means no page yielded usable text, such as an image-only document without OCR; `FAILED` means the document itself could not be opened or its source is missing. Upload status remains `UPLOADED` after parser failure. Encrypted PDFs report `PDF_ENCRYPTED`; malformed PDFs report `PDF_PARSE_ERROR`.

If a parse stays `PARSING` after an abrupt process crash, operator recovery is required in this synchronous Day 4 design. Install Tesseract to resolve OCR-unavailable pages in a new document; Day 4 does not provide destructive forced reprocessing. Parsing alone does not infer financial or company facts.

## Company profile and evidence

After parsing, select **Extract company profile** on the upload page or call `POST /api/v1/documents/{document_id}/company-profile/extract`. Extraction reads stored `DocumentPage` text only. It never opens the PDF, reruns OCR, changes page text, or renames the uploaded Company row. Documents with `NOT_STARTED` or `FAILED` parser status return `DOCUMENT_NOT_PARSED`. A partially parsed document may produce a profile, but its status requires review. Repeated calls for the same extractor version return the existing profile without adding fields or audit events.

The deterministic `company_profile_extractor_v1` records candidates for legal name, reporting period, source-faithful business description, products, services, operating segments, headquarters, registered office, country, and website when the document explicitly states them. Missing values remain unavailable. `GET /api/v1/documents/{document_id}/company-profile` returns the persisted profile and field summaries. `GET /api/v1/company-profiles/{profile_id}/evidence` returns candidate snippets and 1-based source page links for review. The frontend displays values, status, confidence, page numbers, and snippets.

Every stored field references a `DocumentPage`, its document and page number, an evidence snippet, a confidence score, status, and extractor version. Confidence is deterministic: at least 0.85 is `VERIFIED`, 0.65–0.84 is `NEEDS_REVIEW`, and lower scores are `UNAVAILABLE`. Strong conflicting legal-name candidates become `CONFLICTING` and leave the profile's canonical legal name empty. The extractor compares the evidenced legal name to the upload label, treating `Ltd` and `Limited` as equivalent. A mismatch is flagged for review and audited; the Company row is never overwritten. Optional missing location or website does not prevent a verified profile when legal name, reporting period, and business description are verified. If critical evidence is missing, the profile is `PARTIAL` or `NEEDS_REVIEW`.

Rules favor report covers and company overview sections and exclude subsidiary, auditor, bank, customer, and supplier contexts. These are conservative baseline rules; they can miss unusual layouts or wording. No website is visited and no outside facts are added. Profile extraction itself does not classify the business or extract financial values. The original Day 4 OCR availability rules still apply.

## Domain classification ML

The controlled four-level taxonomy is in `apps/backend/app/ml/domain/taxonomy/domain_taxonomy_v1.json`. Its 30 paths span 16 sectors, 28 industries, 30 domains, and 30 sub-domains. Labels and parent-child relationships are validated when loaded. The first dataset snapshot is `data/ml/domain/versions/domain_dataset_v1.jsonl`: 32 examples from 32 distinct **synthetic** companies in four trained sub-domains. Taxonomy coverage is wider than trained model coverage; untrained classes should not be treated as supported predictions.

After installing backend requirements and applying migrations, train and activate a model from `apps/backend`:

```powershell
python -m app.ml.domain.train --dataset-version domain_dataset_v1 --taxonomy domain_taxonomy_v1 --model-version domain_classifier_v2
```

The command requires the configured PostgreSQL `DATABASE_URL` and saves the selected artifact under `storage/models/domain/<model-version>/`. For a disposable test database, set `APP_ENV=test` and `TEST_DATABASE_URL`; its name must contain `test`. Training validates the dataset and taxonomy, splits by company into train/validation/test sets, checks exact-input leakage, trains TF-IDF with Logistic Regression and calibrated Linear SVM candidates, selects by validation sub-domain macro F1 with a 0.03 margin favoring Logistic Regression, and reports measured per-level metrics, confusion matrices, full-path accuracy, and top-2 accuracy. It stores dataset hash, run parameters, metrics, artifact hash, model version, taxonomy version, and input-builder version in PostgreSQL. One model is active per task. A failed training run leaves the previous active model in place.

After extracting a company profile, select **Classify sector and domain** in the upload flow or call `POST /api/v1/company-profiles/{profile_id}/domain-classification`. `GET` on the same path returns the stored prediction; `GET /api/v1/domain-classifications/{classification_id}/evidence` shows the exact source fields and pages used. Classification requires verified business-description, product, service, or operating-segment evidence; legal name, website, location, and reporting period are excluded from the input. A missing active model or artifact returns a controlled error. Repeating classification with the same profile, active model, builder version, and input hash returns the existing row. If evidence later changes, retrieval marks the stored result stale and a new classification can be created.

The flat sub-domain model derives the three parent labels from the taxonomy, so every emitted hierarchy path is valid. Its per-level confidence sums model probabilities under each parent; overall confidence is the lowest of the four levels. By default, confidence at least 0.85 may be `VERIFIED`, 0.65–0.84 requires review, and lower confidence is `UNAVAILABLE`; close alternatives also require review. A profile that itself needs review cannot yield a verified classification. These cutoffs are configurable. Probabilities from this small synthetic baseline are **not validated production calibration**. The measured test metrics reflect this snapshot and must not be interpreted as broad accuracy across Indian companies.

## Financial statement extraction

After parsing, select **Extract financial statements** in the upload flow or call `POST /api/v1/documents/{document_id}/financial-statements/extract`. This reads stored `DocumentPage` text only; it requires no trained domain model. `GET /api/v1/documents/{document_id}/financial-statements` lists summaries, `GET /api/v1/financial-statements/{statement_id}/line-items` lists rows, and `GET /api/v1/financial-line-items/{line_item_id}` returns one row and its concise source evidence. The frontend shows status, scope, period, unit, and expandable evidence. Source PDFs and page text remain unchanged.

The `financial_line_items_v1` JSON taxonomy covers 42 canonical fields across income, balance sheet, and cash flow statements, with synonyms and measurement types. The deterministic `financial_extractor_v1` detects headings, standalone and consolidated scope, adjacent continuation pages, reporting columns, currency and unit headers, numeric values, accounting negatives, and dash/NIL as unavailable. Each row stores raw and parsed values, raw column label, period, page link, snippet, confidence, status, and versions. EPS retains its per-share unit rather than inheriting statement scaling. Unrecognized short table labels remain `UNMAPPED` for review. A SHA-256 of ordered stored pages makes repeat extraction idempotent; changed page text creates a new run, and listing returns the latest run.

Confidence is deterministic: heading 0.35, mapped label 0.25, period 0.14, numeric parse 0.12, known scope 0.04, text quality up to 0.10, with an OCR penalty of 0.16. A mapped numeric row needs at least 0.85 to be verified. Candidate values for the same statement type, scope, fiscal year, and canonical field conflict if their number, currency, or unit differs. Matching secondary evidence is retained; the primary statement takes precedence. A partially parsed document or failed required OCR yields review status. All run, statement, row, and audit writes commit atomically.

This is a conservative text-table baseline. Complex layouts, note-number columns, quarterly periods, ambiguous page continuations, unfamiliar labels, and mixed units may require review. Day 7 extraction preserves source units; Day 8 creates separate normalized values. Tesseract must be installed separately for OCR-dependent PDFs.

## Financial normalization, validation, and ratios

After financial extraction, select **Normalize, validate, and calculate ratios** or call `POST /api/v1/documents/{document_id}/financial-analysis`. Day 8 reads persisted Day 7 line items and never calculates from raw PDF text. Monetary values are converted with `Decimal` into base units of their stated currency; crore, lakh, million, thousand, billion, and absolute units are supported. EPS and other non-monetary measurements are not scaled. No FX rate is invented: inputs in INR, USD, EUR, or GBP remain in that currency, and mixed-currency formulas return an explicit mismatch.

The analysis selects the highest-priority reliable source inside one scope and fiscal year. Standalone and consolidated records remain separate. Equal duplicates support the selected value; conflicts block affected calculations. Safe derivations are limited to `revenue` as an alias for revenue from operations and `total_debt` as short-term plus long-term borrowings. Derived rows record their formula and normalized input IDs.

Validation checks the accounting equation, component totals, debt, opening cash plus movement versus closing cash, and PBT less tax versus PAT when inputs exist. Reconciliation tolerance defaults to 1% and is configured separately with `ACCOUNTING_RECONCILIATION_TOLERANCE_PERCENT`, `DEBT_RECONCILIATION_TOLERANCE_PERCENT`, and `CASH_RECONCILIATION_TOLERANCE_PERCENT`. Completeness measures the availability of revenue, PAT, assets, equity, debt, and operating cash flow; it is data coverage, not financial quality or credit risk.

The versioned `financial_ratios_v1` taxonomy defines 13 ratios: current and quick ratios; debt/equity and debt/assets; interest coverage and debt/EBITDA; EBITDA, EBIT, and net profit margins; ROA and ROE; operating cash flow/debt; and asset turnover. ROA, ROE, and asset turnover use average balances when the prior year is available in the same scope and currency, otherwise ending balances. Percentage values are stored as decimals and formatted as percentages only in the UI. Zero denominators are unavailable; negative equity or EBITDA makes the affected leverage ratio not meaningful. Ratio confidence cannot exceed its weakest input and derived inputs receive a penalty.

`GET /api/v1/documents/{document_id}/financial-validation` returns normalized values and concise validation results. `GET /api/v1/documents/{document_id}/financial-ratios` supports `scope` and `fiscal_year` filters. `GET /api/v1/financial-ratios/{ratio_id}` returns the formula, calculation basis, normalized inputs, and page evidence. The analysis input fingerprint includes line-item IDs, values, units, currencies, statuses, scope, and period; identical requests are idempotent and changed inputs create a new analysis run.

DSCR remains unavailable until reliable debt-service inputs exist. Complex accounting definitions and extracted values needing review can make ratios unavailable or require analyst review. Tesseract remains required for real OCR.

## Financial trends and anomalies

After Day 8 analysis, select **Analyze trends and anomalies** or call `POST /api/v1/documents/{document_id}/financial-trends/analyze`. Day 9 reads the latest persisted normalized values and ratios; it does not re-read the PDF or calculate from raw values. Series are isolated by company, statement scope, metric, and compatible currency, and periods such as `FY2026` and ISO dates are ordered by their parsed year.

The `financial_trend_calculator_v1` calculates absolute change, consecutive-period YoY change, and CAGR using the actual endpoint year distance. A zero prior value yields `ZERO_BASE` rather than infinity. Negative-base profit movement becomes `LOSS_TO_PROFIT`, `PROFIT_TO_LOSS`, `LOSS_NARROWED`, or `LOSS_WIDENED` instead of ordinary percentage growth. Margins, ROA, and ROE use percentage-point change. Missing intermediate periods are retained as gaps and suppress false consecutive YoY claims. Confidence starts from the weakest input and is reduced for gaps, derived values, and ending-balance ratio fallbacks.

The versioned `financial_anomaly_rules_v1` file centralizes thresholds for revenue and profit decline, persistent losses, margin compression, rising leverage, debt growth versus revenue, declining or low interest coverage, liquidity deterioration, negative operating cash flow, profit/cash-flow divergence, receivables or inventory outpacing revenue, asset growth with weak revenue, declining ROA/ROE, debt/EBITDA deterioration, current-ratio alerts, and rapid debt increases. Severity is rule-driven and conservative. Alerts describe observed patterns and do not assert causes or make credit decisions.

`GET /api/v1/documents/{document_id}/financial-trends` supports scope, metric, and period filters. `GET /api/v1/documents/{document_id}/financial-anomalies` supports scope, severity, category, and status filters. Single-trend and single-anomaly endpoints expose input lineage back through ratios or normalized values to original page evidence. Identical inputs and versions return the same run; changed Day 8 outputs create a new run.

Missing periods and uncommon accounting metrics reduce trend coverage. The anomaly layer describes observed patterns without asserting their causes.

## Deterministic credit risk analysis

After Day 9 analysis, select **Calculate credit risk** or call `POST /api/v1/documents/{document_id}/credit-risk/analyze`. Day 10 reads the latest persisted company profile, optional domain classification, Day 8 financial analysis, and Day 9 trends and anomalies. It never reads the PDF or recomputes ratios and trends. Standalone and consolidated scopes receive separate assessments.

The versioned `credit_policy_v1` scores financial strength (30%), repayment capacity (30%), business stability (20%), data quality (10%), and verified industry context (10%). Each component begins at 50 and applies explicit positive or negative rule impacts before being clamped to 0–100. Industry context is unavailable unless the domain result is verified; the engine does not infer risk from a sector label. Eligible weights are renormalized only when overall coverage is at least 80%, financial-strength coverage is at least 60%, repayment-capacity coverage is at least 60%, and each other included component satisfies its configured minimum. Otherwise the assessment is `INSUFFICIENT_DATA` and omits the score and band.

Bands are `LOW_RISK` at 80+, `MODERATE_LOW_RISK` at 65+, `MODERATE_RISK` at 50+, `ELEVATED_RISK` at 35+, and `HIGH_RISK` below 35. Persistent negative cash flow suppresses the overlapping one-period cash-flow reason, persistent revenue decline suppresses the single decline reason, and a low-coverage alert suppresses an overlapping declining-coverage reason. These rules prevent duplicate penalties while preserving the input graph.

`GET /api/v1/documents/{document_id}/credit-risk` returns the latest assessment per scope. `GET /api/v1/credit-assessments/{assessment_id}` returns the score, five subscores, coverage, confidence, status, and leading factors. The `/reasons` and `/evidence` endpoints expose every rule impact and traverse its typed inputs back through normalized values, ratios, trends, anomalies, company profile or domain classification to page evidence. Input IDs and all three engine versions make repeated analysis idempotent and changed upstream runs create new immutable assessments.

This score is a development-stage analytical output. It does not approve or reject credit, set an amount, price a facility, assess collateral, replace underwriting judgment, or use external research, stock data, RAG, the 5 Cs, or ML credit prediction.

## Credit ML dataset preparation

Day 11 prepares versioned historical examples for the target `default_within_365_days`; it does not train a model or produce predictions. An observation fixes the company, observation date, fiscal year, prediction horizon, and feature cutoff. Positive labels require a verified default event within the horizon. Negative labels require verified no-default evidence through the entire horizon. Incomplete follow-up is censored and conflicting evidence is excluded.

The default `ANOMALY_ENRICHED_V1` feature group reads only persisted Day 8 and Day 9 rows created by the cutoff and fiscal periods available by the observation year. `RULE_SCORE_ENRICHED_V1` can additionally include the Day 10 score and subscores. Missing or unverified values remain null. Every used feature has typed source lineage, and the feature snapshot stores its builder version, schema version, input digest, and availability limitation.

Build a snapshot from `apps/backend` after recording historical observations and outcomes:

```powershell
python -m app.ml.credit.dataset --dataset-version credit_dataset_v1 --feature-group ANOMALY_ENRICHED_V1
```

The builder assigns companies to chronological train, validation, and test partitions, then blocks publication on company overlap, duplicate observations, exact feature overlap across partitions, target leakage, outcome-date leakage, or future source timestamps. JSONL and metadata are written under `data/ml/credit/versions`, and PostgreSQL stores the dataset, examples, report, policy versions, counts, missingness, label quality, leakage checks, and SHA-256. A version is immutable; changed configuration requires a new version. `GET /api/v1/ml/credit/datasets/{dataset_id}` exposes read-only metadata.

Synthetic outcomes validate the pipeline only. The included fixture produces ten eligible examples, three positive and seven negative, plus one censored observation. It reports `PIPELINE_VALIDATED` and `NEEDS_REVIEW` because original filing publication timestamps and real curated outcomes are unavailable. It is not training ready or production ready.

## Credit ML baseline pipeline validation

Day 12 trains Logistic Regression, Random Forest, and XGBoost only from a published Day 11 JSONL snapshot. It verifies the registered dataset hash and leakage report before training. Numeric median imputation, missing indicators, scaling for Logistic Regression, categorical missing values, and one-hot encoding are fitted inside the training split. Validation and test categories unseen during training are ignored safely. Logistic Regression and Random Forest use balanced class weights; XGBoost receives `scale_pos_weight` calculated from training labels only.

Sigmoid calibration uses cross-validation within the training split. Validation metrics select the baseline under `credit_model_selection_policy_v1`; test data is evaluated once after selection. Reports include PR-AUC, ROC-AUC, accuracy, precision, recall, F1, balanced accuracy, Brier score, log loss, specificity, negative predictive value, expected calibration error, calibration points, and confusion matrices when mathematically valid. Single-class splits report affected metrics as unavailable.

Run the pipeline from `apps/backend`:

```powershell
python -m app.ml.credit.training --dataset-version credit_dataset_v1 --feature-group ANOMALY_ENRICHED_V1 --training-mode PIPELINE_VALIDATION --models logistic_regression,random_forest,xgboost
```

Candidate artifacts contain the complete fitted preprocessing, calibrator, and classifier under `storage/models/credit/<model-version>/`. SHA-256 is verified before loading. PostgreSQL reuses `ml_runs`, `ml_metrics`, and `ml_models` for parameters, library versions, split-specific metrics, dataset lineage, readiness, lifecycle, calibration, threshold, artifact reference, and active baseline state. Read-only metadata is available from `GET /api/v1/ml/credit/models` and `GET /api/v1/ml/credit/models/{model_id}`.

The current credit ML models are trained on ten synthetic examples and are intended only to validate the ML pipeline. Their metrics and feature diagnostics are not evidence of real-world default prediction performance. They cannot be marked production ready, do not alter the Day 10 score, and are not used for approval, rejection, pricing, limits, collateral, or any lending decision.

## Credit ML evaluation and fusion preparation

Day 13 evaluates fresh Logistic Regression, Random Forest, and XGBoost pipelines inside chronological walk-forward windows. `EXPANDING_WINDOW` uses every eligible prior period, while `ROLLING_WINDOW` uses the configured trailing period. Every window independently fits its feature layout, imputer, encoder, scaler, class handling, estimator, and train-internal sigmoid calibration. Future evaluation observations never participate in fitting. Windows with insufficient support, one training class, or invalid ordering remain persisted as `SKIPPED` with a reason.

Run an evaluation from `apps/backend`:

```powershell
python -m app.ml.credit.evaluate --dataset-version credit_dataset_v1 --feature-group ANOMALY_ENRICHED_V1 --mode PIPELINE_VALIDATION --walk-forward-policy credit_walk_forward_policy_v1 --window-mode EXPANDING_WINDOW --models logistic_regression,random_forest,xgboost
```

The versioned policies are `credit_walk_forward_policy_v1`, `credit_drift_policy_v1`, `credit_ml_diagnostic_bands_v1`, and `credit_fusion_readiness_policy_v1`. The input hash covers the dataset digest, feature group, modes, candidates, training configuration, and policy versions. Repeating an identical request returns the existing run.

Per-window results include safe ranking, threshold, calibration, confusion-matrix, default-rate, predicted-positive-rate, and average-probability metrics. Aggregates report mean, median, population standard deviation, minimum, maximum, and evaluation-size-weighted average while excluding unavailable values. Fewer than three valid windows yields `INSUFFICIENT_DATA` for performance stability.

Numeric feature drift uses train-derived PSI bins plus mean and median shift. Categorical drift records frequency shift and unseen-category rate. Prediction drift compares probability summaries across adjacent valid windows; calibration drift compares Brier scores. Thresholds are development alerts, not universal regulatory standards or lending rules.

Candidate probabilities are compared per observation for probability gap, standard deviation, predicted-class disagreement, and unanimity. Day 10 scores may be transformed to `rule_risk_index = 1 - score / 100` for ranking comparison. This index is explicitly **not** a calibrated probability of default. Rule and ML diagnostic bands can be compared without changing the stored Day 10 score or resolving disagreements automatically.

Fusion readiness produces structured inputs and blocking reasons only. Synthetic-only data, insufficient walk-forward support, non-production model readiness, high drift, or missing rule comparison prevents fusion. Day 13 creates no hybrid score and cannot activate or promote a registry model.

Read-only endpoints:

- `GET /api/v1/ml/credit/evaluations`
- `GET /api/v1/ml/credit/evaluations/{evaluation_id}`
- `GET /api/v1/ml/credit/evaluations/{evaluation_id}/windows`
- `GET /api/v1/ml/credit/evaluations/{evaluation_id}/drift`
- `GET /api/v1/ml/credit/evaluations/{evaluation_id}/rule-comparison`

The current ten-row dataset produces one valid expanding window and no valid rolling windows under the published policy. Its metrics, drift output, disagreement output, and calibration results validate architecture only and cannot establish real-world stability or model quality.

## Explainable rule and ML fusion experiments

Day 14 adds a derived experiment layer without changing the immutable Day 10 assessment, Day 12 model registry or artifacts, or Day 13 evaluation history. `credit_fusion_policy_v1` keeps the current mode, 60% rule and 40% ML development weights, confidence and coverage gates, drift and disagreement thresholds, production requirements, and fallback policy in one versioned file. `credit_fusion_risk_bands_v1` owns separate experimental labels.

The rule input is transformed with `rule_risk_index = 1 - overall_score / 100`; this ranking index is not a probability of default. The ML input comes only from the active registered model through integrity-checked inference. The weighted strategy calculates an experimental hybrid risk index only after every gate passes. The consensus strategy withholds the number for moderate disagreement and blocks high disagreement. High disagreement also blocks the weighted strategy. Data quality changes availability and confidence rather than directly increasing borrower risk.

Readiness checks the assessment, confidence, effective data coverage, company and feature lineage, artifact SHA-256 and bundle metadata, model lifecycle, latest Day 13 evaluation, drift, candidate-model disagreement, real-outcome support, and walk-forward support. Artifact or model unavailability may return an explicit Day 10 rule-only reference. Invalid rule evidence or low coverage returns no reliable output. The current synthetic-only model is `PIPELINE_VALIDATION_ONLY`; fusion confidence is capped at 0.50 and `production_use_permitted` is always false.

Each experiment persists source values, visible weights and weighted contributions, safety reasons, readiness, deterministic confidence penalties, model/evaluation/snapshot lineage, policy versions, and an input hash. Repeating the exact experiment is idempotent. The diagnostic comparison exposes rule-only, ML-only, weighted, and consensus contexts as `PIPELINE_DIAGNOSTIC_ONLY`; it does not calculate hybrid Brier score, claim calibration, or select a winning strategy without a labelled historical fusion series.

Internal APIs:

- `POST /api/v1/credit-fusion/experiments`
- `GET /api/v1/credit-fusion/experiments/{experiment_id}`
- `GET /api/v1/documents/{document_id}/credit-fusion/experiments`
- `GET /api/v1/credit-fusion/experiments/{experiment_id}/contributions`
- `GET /api/v1/credit-fusion/experiments/{experiment_id}/reasons`
- `GET /api/v1/documents/{document_id}/credit-fusion/readiness`

The internal page at http://localhost:3000/credit-fusion accepts assessment and feature-snapshot IDs plus a strategy. It labels every result as experimental and keeps production use blocked. These outputs cannot approve or reject credit, set terms, or support a real lending decision. Rule and ML features overlap, so the 60/40 calculation must not be interpreted as combining statistically independent evidence.

## 5 Cs of Credit evidence engine

Day 15 creates a new derived evidence layer for Character, Capacity, Capital, Collateral, and Conditions. It does not change company profiles, financial evidence, Day 10 credit assessments, registered ML models, evaluation records, or fusion experiments. `five_cs_policy_v1` defines section requirements, availability-based completeness, confidence thresholds, critical inputs, deterministic rules, and the prohibition on a total 5 Cs credit score.

Character uses internal identity and reporting consistency only. It records promoter background, repayment history, bureau evidence, and legal/background research as unavailable. It never infers honesty, intent, competence, reputation, or integrity from annual-report language. Capacity consumes persisted Day 10 repayment-capacity context and Day 8–9 interest coverage, Debt/EBITDA, operating cash flow/debt, cash flow, trends, and anomalies. Capital consumes the financial-strength component, total equity, leverage ratios, net-worth availability, and equity trends without treating equity, net worth, and share capital as interchangeable.

Collateral scans existing `DocumentPage` text for explicit phrases such as secured by, first or second charge, mortgage, hypothecation, pledged assets, security created, or collateral security. Generic assets, PPE, property, plant, or machinery are not collateral evidence unless they occur inside explicit security wording. A security mention remains incomplete without description, asset type, value, coverage, LTV, and independent valuation. No collateral value is estimated. Conditions uses verified internal business/domain context and company-specific revenue or margin evidence. It never presents those observations as an external industry outlook; sector, regulatory, and macroeconomic research remain unavailable.

Each scope receives a separate assessment. Sections store structured positive, negative, neutral, and review observations with source IDs, optional page evidence, confidence, completeness, status, and a deterministic `five_cs_summary_v1` narrative. Completeness measures evidence availability rather than credit strength. Review items identify missing external Character evidence, Capacity or Capital concerns, incomplete collateral, unverified domain context, and missing external Conditions research.

APIs:

- `POST /api/v1/documents/{document_id}/five-cs/analyze?scope=CONSOLIDATED`
- `GET /api/v1/documents/{document_id}/five-cs?scope=CONSOLIDATED`
- `GET /api/v1/five-cs/{assessment_id}`
- `GET /api/v1/five-cs/{assessment_id}/evidence?section=CAPACITY`
- `GET /api/v1/five-cs/{assessment_id}/review-items`

The internal page at http://localhost:3000/five-cs displays five section cards, evidence availability, summaries, review indicators, and source links. The output contains no approval, rejection, loan amount, pricing, sanction terms, collateral requirement, collateral valuation, or lending decision.

## External research evidence

Day 16 adds an immutable external evidence layer for company events, verified promoter identities, legal and regulatory events, credit ratings, industry outlook, and sector outlook. `external_research_engine_v1` uses the versioned `research_query_builder_v1`, `research_source_quality_v1`, `research_freshness_policy_v1`, `research_evidence_extractor_v1`, and `research_finding_v1` contracts. The default deterministic fixture provider makes local operation and tests reproducible without internet access. A bounded HTTP fetch primitive is available for a future configured search provider; no live search provider or credentials are bundled.

Only a verified and matched company profile can start research. Promoter queries require verified named identities, and industry or sector queries require a verified domain classification. Results retain separate publication, event, and retrieval dates. URLs are canonicalized, tracking parameters removed, content hashed, copied content collapsed, and publisher independence counted conservatively. Exact or alias entity matches can create evidence; wrong-company matches are rejected and ambiguous names require review. Source classes carry explicit tiers and quality scores, while time-sensitive evidence is labeled current or stale and old legal history is preserved as historical.

Legal events distinguish allegations, reported investigations, orders, penalties, convictions, and dismissals. An investigation report cannot become a fraud finding. Rating actions preserve agency, upgrade or downgrade, old and new rating, withdrawal or affirmation, and outlook when available. Company financial trends never become sector conclusions; industry and sector findings require external sources. Every finding links to stored evidence and its source. Source failures are recorded without fabricating findings, and absence of results is represented as coverage rather than low risk.

The research dashboard is available at http://localhost:3000/research. It displays source quality, dates, freshness, entity status, findings, and Character or Conditions candidates. Candidates are review inputs only: Day 16 never changes the Day 15 assessment and generates no lending decision or stock recommendation.

APIs:

- `POST /api/v1/companies/{company_id}/research`
- `POST /api/v1/documents/{document_id}/research`
- `GET /api/v1/research-runs/{run_id}`
- `GET /api/v1/research-runs/{run_id}/sources`
- `GET /api/v1/research-runs/{run_id}/evidence`
- `GET /api/v1/research-runs/{run_id}/findings`
- `GET /api/v1/research-findings/{finding_id}`
- `GET /api/v1/research-runs/{run_id}/five-cs-candidates`

HTTP source validation allows only HTTP(S), blocks loopback, private, link-local, metadata, and internal destinations, disallows redirects, limits content to HTML, plain text, or PDF, and caps a response at 2 MiB. Requests use finite timeouts, one retry, and backoff. Downloaded content is never executed. Entity resolution remains conservative, legal findings may need human review, freshness varies by source, and live coverage depends on provider configuration.

## Research-enriched 5 Cs and credit recommendation preparation

Day 17 creates an immutable `five_cs_engine_v2` assessment from one Day 15 base assessment and one Day 16 research run. `five_cs_research_refresh_v1` admits only mapped findings that satisfy quality, confidence, and freshness rules. Legal and regulatory findings enrich Character, while ratings and external sector findings enrich Conditions. Dismissed cases do not become active adverse findings, stale or conflicting research does not silently change a section, and reported investigations retain their reported status. Capacity, Capital, and Collateral are copied from validated Day 15 evidence; external reporting cannot recalculate financial facts or value collateral.

`credit_recommendation_engine_v1` prepares strengths, risks, critical review flags, missing evidence, human review items, and optional experimental context. Day 10 remains the primary quantitative baseline. Day 14 fusion is stored only as `EXPERIMENTAL_CONTEXT` and cannot change readiness or production confidence. `credit_recommendation_policy_v1` permits only `READY_FOR_DECISION_REVIEW`, `CONDITIONAL_REVIEW_REQUIRED`, `INSUFFICIENT_EVIDENCE`, `CRITICAL_RISK_REVIEW`, `DATA_CONFLICT_REVIEW`, and `NOT_READY`.

Day 17 produces no approval, rejection, sanction amount, credit limit, facility pricing, or final lending decision. Confidence is capped for missing external coverage, partial research, and unresolved conflicts.

APIs:

- `POST /api/v1/five-cs/{assessment_id}/refresh-with-research`
- `GET /api/v1/documents/{document_id}/five-cs?latest=true`
- `POST /api/v1/documents/{document_id}/credit-recommendation/prepare`
- `GET /api/v1/credit-recommendations/{preparation_id}`
- `GET /api/v1/documents/{document_id}/credit-recommendations`
- `GET /api/v1/credit-recommendations/{preparation_id}/factors`
- `GET /api/v1/credit-recommendations/{preparation_id}/review-items`
- `GET /api/v1/credit-recommendations/{preparation_id}/evidence`

The 5 Cs page displays base-versus-refreshed evidence. The internal `/credit-recommendation` page groups official factors, missing evidence, review items, and experimental context while showing Day 10, 5 Cs, and research lineage.

## Deterministic credit decision support and proposed limit preparation

Day 18 consumes the immutable Day 17 recommendation and evaluates `credit_decision_policy_v1` through financial, repayment capacity, capital, collateral, Character, Conditions, legal/regulatory, data-quality, and research-coverage gates. Outputs are limited to `FAVORABLE_REVIEW`, `CONDITIONAL_REVIEW`, `MANUAL_REVIEW_REQUIRED`, `ADVERSE_REVIEW`, `INSUFFICIENT_EVIDENCE`, and `POLICY_EXCEPTION_REVIEW`. Every output requires a qualified human reviewer; `human_decision` remains unset.

Policy threshold breaches create explicit open exceptions with required reviewer authority. Blocking means that review or an exception is required and never means automatic rejection. The engine excludes protected and sensitive personal attributes, does not add protected-trait proxies, and limits promoter evidence to sourced professional relevance.

`credit_limit_policy_v1` calculates available cash-flow, revenue, leverage, working-capital, and independently verified collateral methods separately. The minimum eligible cap produces a range and analytical ceiling. Missing debt exposure remains `EXISTING_EXPOSURE_INCOMPLETE`, missing values never become zero, PPE book value is not collateral, and no future interest rate is invented. The result is an analytical exposure ceiling rather than a sanctioned facility limit. ML and fusion have zero decision and limit weight.

APIs are rooted at `POST /api/v1/documents/{document_id}/credit-decision/prepare` and `GET /api/v1/credit-decisions/{decision_support_id}`, with read-only gates, exceptions, review-items, limit-preparation, evidence, and document-list endpoints. The internal `/credit-decision` page shows the human review package and mandatory warning.

## Checks

For PostgreSQL integration tests, set `APP_ENV=test` and `TEST_DATABASE_URL` to a **dedicated disposable PostgreSQL database whose name contains `test`**. The migration test downgrades and reapplies its schema. Upload tests use temporary storage and do not write to the development upload directory. Tests refuse a URL without `test` in the database name. For example:

```powershell
$env:APP_ENV = 'test'
$env:TEST_DATABASE_URL = 'postgresql+psycopg://test_user:password@localhost:5432/company_intelligence_test'
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy app
```

Without `TEST_DATABASE_URL`, PostgreSQL integration tests skip; they must pass against PostgreSQL before database changes are considered verified.

From `apps/frontend`: `npm run typecheck`, `npm run lint`, and `npm run build`.

## Containers

`docker compose up --build` runs PostgreSQL, backend, and frontend after the root environment is configured. Apply migrations with `docker compose exec backend alembic upgrade head`. The named `postgres_data` volume persists local database data. This Compose file is for development.

See [architecture](docs/architecture.md), [data flow](docs/data-flow.md), [reliability principles](docs/reliability-principles.md), and [roadmap](docs/development-roadmap.md).

## Day 19: human credit review and committee preparation

Day 19 adds a governance layer over the immutable Day 18 decision-support record. A review case remains bound to one Day 18 version and records assignments, append-only comments, evidence acknowledgements, checklist actions, information requests, policy-exception actions, and a chronological audit trail. Newer Day 18 analysis produces an `UPDATED_ANALYSIS_AVAILABLE` warning and never silently changes the case basis.

## Day 20: controlled credit reports and exports

Day 20 turns one fixed Day 19 review basis into versioned report artifacts. It generates a credit appraisal memorandum, credit committee memo, decision evidence pack, or structured JSON export from persisted records only. The renderer does not recalculate financial values, create a new credit judgment, fill missing evidence, or allow experimental ML to influence the report.

- **CAM:** company and reporting basis, financial statements and normalized values, ratios, trends, anomalies, rule-based credit assessment, Five Cs, research, recommendation factors, policy gates and exceptions, analytical and approved limits, review activity, decisions, overrides, committee context, experimental ML disclosure, and limitations.
- **Committee memo:** a shorter committee-labelled view of the fixed package, material assessment and Five Cs facts, research, gates, exceptions, analytical limit, review activity, human decision history, and committee summary.
- **Evidence pack:** the detailed snapshot and source-link graph for financial records, source pages, research URLs and findings, recommendation evidence, gate and exception history, review actions, decisions, overrides, and limit methods.
- **Exports:** conservative A4 PDFs through ReportLab and stable structured JSON. Missing values render as unavailable or not recorded.

Every report stores its type, report version, template and renderer versions, deterministic input hash, confidentiality label, human actor, immutable JSON snapshot, source links, artifact metadata, byte size, and SHA-256. Repeating an identical request returns the existing report. Changed persisted inputs create a new version. Authorized users can finalize a generated report; a later version can explicitly supersede a finalized report without changing or deleting the earlier artifact.

Internal APIs:

- `POST /api/v1/credit-review-cases/{review_case_id}/reports`
- `GET /api/v1/credit-review-cases/{review_case_id}/reports`
- `GET /api/v1/reports/{report_id}`
- `GET /api/v1/reports/{report_id}/snapshot`
- `GET /api/v1/reports/{report_id}/evidence`
- `GET /api/v1/reports/{report_id}/download`
- `POST /api/v1/reports/{report_id}/finalize`
- `POST /api/v1/reports/{report_id}/supersede`
- `GET /api/v1/reports/{report_id}/versions`

The internal `/credit-reports` page generates and lists report versions, previews the frozen snapshot and its hash, displays artifact integrity metadata, finalizes generated reports, warns when a version is superseded, and provides authorized downloads. Local filesystem storage and the development authority policy are current deployment constraints. Production use still needs enterprise identity, durable object storage, retention controls, electronic signing, and jurisdiction-specific report templates.

The development authority policy `credit_review_authority_policy_v1` defines reviewer roles, decision and exception permissions, limit bands, committee thresholds, and maker-checker controls. These permissions are enforced by backend services. Human decisions are explicit, attributable actions with required rationale and immutable versions. `APPROVED`, `DECLINED`, `RETURNED_FOR_INFORMATION`, and `REFERRED_TO_COMMITTEE` remain separate from the system recommendation.

The Day 18 analytical ceiling and a human-entered approved limit remain separate. A higher human limit requires authority and recorded override rationale. An approved policy exception does not approve credit. Committee packages are deterministic structured data, versioned by input hash, and immutable after they are marked `READY`.

No borrower notification, pricing, sanction document, facility booking, repayment schedule, disbursement, CAM PDF, or automatic human decision is produced. ML and fusion remain experimental pipeline-validation context with zero decision weight. No protected personal attributes are included in the authority policy or workflow.
