# Day 28: 360° Company Intelligence Report

Status: COMPLETE — completion gates passed on 2026-10-05. Day 29 remains planned.

See [the completion report](day28-completion-report.md) for final test results,
sample snapshot details, artifact hashes, and readiness limitations.

The report is a synthesis of existing records. It never invokes score calculation,
model training, validation, monitoring, credit approval, or trading services.
Creditworthiness and equity-market analytical strength remain separate assessments.
There is no combined master score.

## Architecture

The report reuses Day 20's generated reports, snapshots, artifacts, source links,
finalization actions, and audit infrastructure. Its versions are:

- Type: `COMPANY_INTELLIGENCE_360`
- Template: `company_intelligence_360_v1`
- Policy: `company_intelligence_report_policy_v1`
- Schema: `company_intelligence_360_schema_v1`
- Renderer: `company_intelligence_renderer_v1`

The resolver loads persisted company, document, financial, credit, stock, validation,
and monitoring records. Sections preserve original scopes, currencies, statuses,
confidence, and provenance. The executive summary is deterministic. Missing records
remain explicit; a company with no resolved listing has stock sections marked
`NOT_APPLICABLE`. Missing stock scores never borrow credit scores.

JSON is authoritative. The PDF is a readable view with explicit limits on repeated
records; the JSON retains the underlying records and source references. Evidence
coverage measures included record claims with links, independently of analytical
confidence. The report records partial, unavailable, and review sections separately.

Source collections are limited to 2,000 records each and the authoritative snapshot
to 20 MiB. Exceeding either limit returns `REPORT_SCOPE_TOO_LARGE` rather than
silently dropping evidence. These limits are part of the versioned report policy.
Score-component evidence is bounded per component, preserving the thousands of
price observations that a valid multi-component score can reference in aggregate.

## Temporal safety and governance

### Current-record consistency correction

Identity is recomputed using the same deterministic company-name normalization as
profile extraction (Unicode normalization, case, punctuation, whitespace, and
Ltd/Limited or Pvt/Private equivalents). Empty names cannot match. Report profiles
retain the recorded identity/status alongside the derived current identity; a
mismatch is CONFLICTING/NEEDS_REVIEW and never renames the Company or edits the
source profile. The PDF displays current identity, while JSON retains recorded values.

The report selects classification by profile, Five Cs by credit assessment/profile/
classification, refreshed Five Cs by research-run and input-hash lineage, and
recommendation/decision support/review by their exact dependency IDs. A later
timestamp cannot promote an assessment linked to an obsolete classification.
Superseded or stale assessment IDs and hashes remain in the report's historical
exclusion metadata. Historical database rows and generated artifacts are untouched.

A verified classification paired with unavailable-domain evidence in the same
assessment is a visible consistency conflict. That entire assessment and its
dependent recommendation are excluded pending a service rebuild; evidence or
scores are not patched individually. Existing system-versus-human conflicts remain
visible. Reporting itself continues to synthesize only persisted analytics.

The normal smoke fixture creates Grid Switchgear identity before any research or
credit calculations. After domain classification it rebuilds Five Cs, research,
recommendation, and decision support through their existing services. Separate tests
retain deliberate identity and domain conflicts. Development provider identifiers
remain exact in JSON and use readable labels in the PDF.

Sources are filtered by the report's analytical date and their persistence timestamp.
Mutable records updated after that date are excluded because their prior state cannot
be reconstructed safely. Fundamental availability and price trade dates are also
gated. An explicitly selected future analysis job is rejected.

Future listing freshness metadata is omitted from historical reports. Provider-run
and dataset provenance includes identifiers and version metadata without exposing
future-window statistics. Validation and monitoring are explicitly identified as
platform research diagnostics, rather than attributed to the selected company.

Stored snapshots and artifacts never refresh from live analytics. The input hash
includes selected source content, identifiers, scope, and versioned policy. Identical
inputs reuse a report; changes produce a new sequence. Company-level locking
serializes report version allocation. Finalization changes governance metadata only;
supersession links the old and new reports without deleting history. Generation uses
a savepoint, and failed exports remove files written during the failed attempt.

Active users follow the existing development actor-ID convention. This is not a
replacement for production authentication. Generation and finalization enforce
reviewer roles. Exports verify storage containment and SHA-256 integrity.

## API and workspace

The `/api/v1/company-intelligence-reports` collection supports creation and filtering
by company, status, version, and analytical date. Each report supports retrieval,
snapshot, evidence, JSON/PDF downloads, finalization, and supersession. The
`/company-intelligence` workspace exposes scope controls, version history, section
navigation, evidence inspection, exports, and governance actions.

All routes below use `/api/v1/company-intelligence-reports` as their base:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/` | Generate or reuse a report from eligible persisted sources |
| GET | `/` | List versions with company, status, sequence, and date filters |
| GET | `/{id}` | Read report metadata and artifacts |
| GET | `/{id}/snapshot` | Read the immutable authoritative snapshot |
| GET | `/{id}/evidence` | Inspect source references and metadata |
| GET | `/{id}/artifacts/pdf` | Download the integrity-checked PDF |
| GET | `/{id}/artifacts/json` | Download the integrity-checked JSON |
| POST | `/{id}/finalize` | Record authorized human finalization |
| POST | `/{id}/supersede` | Link a successor without deleting the prior report |

The frontend provides summary, company profile, documents, financials, credit,
stock, validation, monitoring, and evidence tabs. Existing credit decision support,
human decisions, and stock research assessments retain their distinct labels and
source values. Missing decisions are never inferred from scores.

## Source coverage

| Section | Persisted inputs |
| --- | --- |
| Company and documents | Identity, business profile, domain classification, extracted fields, documents, pages, and evidence snippets |
| Financials | Statements, line items, normalized values, ratios, trends, anomalies, scope, currency, and periods |
| Credit | Assessment and reasons, ML context, 5 Cs and evidence, external research, policy gates and exceptions, decision support, analytical limits, human review and decisions, committee package, and CAM linkage |
| Stock | Listing, peer membership, prices, fundamentals, valuation and relative metrics, features, all 11 score components and inputs, rankings, watchlist, and ML research provenance |
| Validation | Historical run and periods, rank/bucket diagnostics, recorded ablations and sensitivity results, with platform scope |
| Monitoring | Freshness/provider diagnostics, feature and prediction drift, score drift, ranking stability, findings, and advisory governance |

Absent source collections are listed in subsection statuses and missing information;
the report does not manufacture replacement analytics. Executive strengths and risks
are deterministic extracts of these persisted observations with source references.

## Migration decision

Migration `0027_company_intelligence_360_report` is required: Day 20 constrained report
types and required a review case, decision-support record, analysis job, and document.
Those requirements prevent legitimate partial, stock-only, or non-listed reports.
The migration makes those references optional, adds readiness/as-of/coverage metadata,
extends status/type checks, and adds company/date indexes. Existing report tables are
retained. Downgrade requires Day 28 rows to be absent or compatible with Day 20; it
does not silently delete generated reports.

## Verification (2026-10-05)

The original backend baseline is 421 passing tests. Day 28 adds 19 test cases
covering integrated credit/stock/validation/monitoring snapshots, non-listed and
missing-data reports, scope exclusion, JSON schema, exact lineage, historical
eligibility, unchanged upstream scores, report versions, finalization, supersession,
permissions, HTTP lifecycle, artifact hashes, tampering, and export rollback.
The final full regression passed: **440 passed, 1 skipped**, in 351.93 seconds.
The skipped test requires the unavailable Tesseract executable. One existing
Starlette/httpx deprecation warning remains. The log is preserved at
`output/day28-backend-validation.log`.

Backend Ruff lint and formatting pass (281 Python files including migrations).
MyPy passes across 221 application files. Frontend TypeScript, ESLint, and the
Next.js production build pass, including `/company-intelligence`. The separate
React rendering contract checks all nine report tabs against the exported backend
fixture; it is not a browser interaction test.

The development database reports `0027_company_intelligence_360_report (head)`;
Alembic reports no new upgrade operations for both development and test databases.
The full regression passed downgrade to base followed by a clean upgrade to head
on the disposable test database. The final 25-page fixture PDF was rendered and
visually checked; all nine frontend report sections passed the rendering contract.

Final validation exposed a legitimate aggregate lineage collection exceeding the
2,000-record bound. Applying the bound per score component fixed the report while
retaining all input records; the test now compares exported input IDs with the
complete persisted set. An earlier unordered Day 23 fixture was also made
deterministic for its positive-earnings assertion; financial calculations were not
changed.

## Limitations

Development market/fundamental providers, limited corporate-action adjustment,
fixture-sized stock ML research, survivorship bias, and a development benchmark
remain. Day 24 lifecycle remains `PIPELINE_VALIDATION_ONLY`. Historical validation
and monitoring use development data; PSI thresholds are governance heuristics.
Tesseract is unavailable in the current environment. There is no autonomous credit
approval, production stock prediction, live model serving, BUY/SELL/HOLD, target
price, return forecast, or automated trading.

Original evidence has greater authority than extracted fields, derived analytics,
or report prose. Day 28 does not index synthesized reports as original RAG evidence,
which avoids circular report citations.
