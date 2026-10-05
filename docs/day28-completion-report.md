# Day 28 completion report

## Day 28 Status

**COMPLETE**, verified 2026-10-05. Day 29 has not been implemented.
Implementation completion does not imply that every generated report has complete evidence.
All figures below describe an isolated development fixture, not a real company assessment.

## Consistency correction

The smoke fixture now constructs Grid Switchgear identity before research or credit
analysis. Current Five Cs and recommendation dependencies are rebuilt through the
existing services after verified classification. The original contradictory smoke
export is preserved under `output/day28-smoke-history/09b701f3-68ac-4110-98cd-0ff922320d8f/`;
its JSON and PDF hashes were verified unchanged.

Report selection now follows profile/classification/credit IDs and research-refresh
input hashes. Obsolete assessments are excluded from current sections and retained
as historical source references. A linked assessment that contradicts a verified
classification is explicitly flagged for rebuilding rather than edited. Future-dated
review items cannot invalidate an earlier report.

Identity is recomputed from normalized names. Recorded values remain in JSON;
genuine mismatches are CONFLICTING/NEEDS_REVIEW and never rename the Company.
PDF provider labels are readable; raw provider identifiers remain in JSON lineage.
Day 25 scoring, Day 26 validation, and Day 27 monitoring logic are unchanged.

## Report Architecture

Type `COMPANY_INTELLIGENCE_360`; template `company_intelligence_360_v1`;
schema `company_intelligence_360_schema_v1`; policy
`company_intelligence_report_policy_v1`; renderer `company_intelligence_renderer_v1`.
Day 20 report, snapshot, artifact, evidence-link, finalization, and audit tables are reused.
Migration `0027_company_intelligence_360_report` was required to support partial reports.
The service only synthesizes persisted analytics and never trains or scores models.

## Snapshot

Fixture: **Grid Switchgear India Limited**, as of **2026-10-05**.
The manifest resolves 498 source identifiers; evidence coverage accounts for
497 included persisted record claims. Six sections are AVAILABLE,
one NEEDS_REVIEW (monitoring), zero PARTIAL, and zero UNAVAILABLE at
section level. Missing subsection records remain listed explicitly.
Completeness is **85.71%**; traceability coverage is **100%**, which is not analytical confidence.

## Executive Summary

The fixture describes electrical equipment manufacturing in Industrials / Electrical
Equipment / Power Distribution Equipment / Transformers & Switchgear.
Strengths and risks are extracted from persisted observations. Financial status is
AVAILABLE; company and profile identity consistently name Grid Switchgear and are
MATCHED. Current classification is VERIFIED and current Five Cs uses that classification.
Missing human review evidence and monitoring warnings remain explicit. Separate conflict
tests retain genuine mismatches; the normal fixture no longer manufactures a name conflict.

## Credit Intelligence

Persisted score **75.00**, band **MODERATE_LOW_RISK**.
The report includes credit assessment, ML context, 5 Cs, research, policy gates and
exceptions, decision support, limits, and review evidence when present. Human decision,
committee package, fusion, and CAM are explicitly missing in this fixture. Missing human
decisions are not inferred from analytical recommendations.

## Stock Intelligence

Persisted score **72.2189**, band **ABOVE_AVERAGE_ANALYTICAL_STRENGTH**;
confidence **0.897955**, coverage **100%**, all **11 components**.
Listing, prices, fundamentals, valuations, features, component inputs, ranking,
watchlist, and research provenance are retained. Missing peer/relative valuation
collections remain explicit. This is research output, not an investment recommendation.

## Validation

Platform research diagnostics cover **2024-01-02 to
2026-06-01**, with **70 eligible rows**
over **7 dates**. Recorded mean Spearman:
**-0.16152918732070282**; median Spearman:
**-0.3404271044608361**; mean top/bottom spread:
**-0.018355270428571428**.
Ablation and sensitivity collections are supported but absent in this fixture and
marked missing. The report performs no policy optimization or new validation.

## Monitoring

Platform health: **REVIEW_REQUIRED**.
Readiness: **RESEARCH_REVIEW_RECOMMENDED**.
Feature/prediction/score drift, ranking stability, provider diagnostics, findings,
and governance are included when present. Automatic action is NONE.

## Governance Separation

Creditworthiness, equity research strength, system recommendations, and recorded
human decisions remain distinct. There is no combined master score, autonomous
credit decision, or automated market action. Validation and monitoring are labeled
as platform diagnostics rather than company-specific assessments.

## Evidence

Original evidence outranks extracted fields, derived analytics, and report prose.
Source types, identifiers, metadata, document/page/snippet references, and conflicts
remain inspectable. Synthesized reports are not indexed as original RAG evidence.
Evidence coverage counts traceable included records, not missing-data completeness.

## Database

Migration 0027 extends existing report type/status checks, permits nullable credit
references, adds policy/schema/readiness/as-of/scope/coverage metadata, validates
coverage ranges, and adds company/type/date indexes. Downgrade refuses incompatible
Day 28 rows through database constraints instead of deleting reports.

## APIs

All nine routes are implemented and exercised: create, list, get, snapshot, evidence,
PDF, JSON, finalize, and supersede under `/api/v1/company-intelligence-reports`.
See [the route table](day28-company-intelligence.md#api-and-workspace).

## Frontend

`/company-intelligence` provides scope controls, report history, nine section tabs,
evidence inspection, JSON/PDF downloads, finalization, supersession, and warnings.
All nine sections render the backend fixture with required disclaimers. HTTP lifecycle
tests cover the actions; the rendering contract is not a browser interaction test.

## Artifacts

The authoritative sample JSON is
[company-intelligence-360.json](../output/day28-smoke/company-intelligence-360.json).
The sample PDF is at `output/day28-smoke/company-intelligence-360.pdf` (25 pages).
Both use isolated test sources; their database records are rolled back after tests.

| Digest | SHA-256 |
| --- | --- |
| JSON artifact | `584a06528015f2b9ff57b2cbe553d0e09315d41339cc80d0867f1f32451c5171` |
| PDF artifact | `70ea4ca9417938ef1a84dd15d4e41a855ee25ad11024ec824e7cbaa65a6e2124` |
| Canonical snapshot | `6255aacd1c8baa839f82e12d5342145f2bfa6616025fccf35883a81642642395` |

Canonical snapshot and formatted JSON hashes intentionally differ. Artifact hashes
are stored separately to avoid self-referential export content.

## Tests

Previous baseline: **421 passed**. Day 28: **19 additional test cases**.
Final full run: **440 passed, 1 skipped**, in **351.93 seconds**.
The skipped OCR test requires Tesseract, which remains unavailable. One existing
Starlette/httpx deprecation warning remains. Results are in
[the regression log](../output/day28-backend-validation.log).
The consistency correction passed 40 focused Day 28/profile tests, plus the strengthened
historical-review-item test. Full regression includes all 19 Day 28 cases. The final
PDF text was checked for both stale domain codes and the old fixture name; none occur.
Raw provider identifiers remain in JSON, while PDF provider labels are readable.
An initial full-run export failure was caused by Windows temporary-path length; the
passing run used the shorter `--basetemp=.t28e` path. Frontend source was unchanged,
so TypeScript/lint/build were not rerun for this correction; the nine-tab rendering
contract passed against the corrected fixture.

## Migration Verification

Upgrade, downgrade to base, reapply, and clean database to head passed on the disposable
test database. Development and test databases report
`0027_company_intelligence_360_report (head)`. Both schema drift checks report
**No new upgrade operations detected**. Development data was not downgraded.

## Historical Safety

Source creation/update timestamps, financial periods, fundamental availability,
price trade dates, score dates, validation windows, monitoring windows, and human
decisions are gated by the report date. Future freshness and dataset-window metadata
are excluded. Historical tests cover future financial/document inputs, stock inputs,
scores, monitoring, and human decisions. Existing snapshots never refresh from live sources.

## Reliability

Identical inputs reuse a report; changed sources produce a new version. Company-level
locking serializes sequence allocation. Finalization preserves snapshot content;
supersession preserves history. Export failures roll back report metadata and remove
newly written files. Downloads check path containment and SHA-256. Partial and
non-listed cases remain explicit. Upstream analytics are not modified.
Collections are bounded at 2,000 records, component evidence separately per component,
and snapshots at 20 MiB; over-limit requests fail instead of truncating evidence.

## Quality

- Ruff lint: passed.
- Ruff formatting: 281 Python files passed.
- MyPy: 221 application source files passed.
- Frontend TypeScript and ESLint: passed.
- Next.js production build: passed, including `/company-intelligence`.
- React report rendering: all nine sections passed.
- PDF: final export rendered; representative opening, component, evidence, and closing pages visually checked.

## Known Limitations

Development market/fundamental providers, limited corporate-action adjustments,
fixture-sized stock ML research, survivorship bias, and a development benchmark remain.
Day 24 lifecycle remains `PIPELINE_VALIDATION_ONLY`. Historical validation and
monitoring use development data. PSI thresholds are governance heuristics. Tesseract
remains unavailable. Actor-ID access is a development convention, not production
authentication. There is no autonomous credit approval, production stock prediction,
live model serving, BUY/SELL/HOLD, target price, return forecast, or automated trading.
The 360 report synthesizes existing analytics; it is not a new scoring model.

## Day 29 Readiness

The versioned snapshot, provenance, export, and governance architecture is ready for
a separately scoped production-hardening/integration stage. Production authentication,
real-provider controls, broader validation, and deployment operations still require
that future work. **Day 29 has not been started.**
