# Development roadmap

- Day 1 — **Complete:** repository, FastAPI, frontend connectivity, configuration, logging, errors, baseline tests, and docs.
- Day 2 — **Complete:** PostgreSQL connectivity, five core models, repositories, transactions, Alembic migration, database health, integration tests, and updated status view.
- Day 3 — **Complete:** validated PDF upload, local storage, SHA-256, company-scoped duplicate rejection, document/audit persistence, failure cleanup, and upload UI.
- Day 4 — **Complete:** PyMuPDF parsing, page text and quality, OCR fallback abstraction, parser metadata, page persistence, audit events, APIs, and minimal parse UI.
- Day 5 — **Complete:** deterministic company identity and business profile extraction, page evidence, confidence, conflict handling, persistence, APIs, audit, and frontend review.
- Day 6 — **Complete:** versioned domain taxonomy and synthetic dataset, grouped training split, TF-IDF baselines, measured metrics, active model registry, evidence-linked four-level classification, APIs, and review UI.
- Day 7 — **Complete:** versioned financial taxonomy, deterministic statement and row extraction, multi-year/scope/unit metadata, evidence, conflicts, PostgreSQL lineage, APIs, and review UI.
- Day 8 — **Complete:** base-unit normalization, deterministic source selection and derivations, accounting validation, completeness, 13 explainable ratios, input lineage, APIs, and review UI.
- Day 9 — **Complete:** chronological financial series, YoY and CAGR, state transitions, percentage-point changes, confidence, versioned deterministic anomaly rules, full lineage, APIs, and review UI.
- Day 10 — **Complete:** versioned deterministic five-component credit risk scoring, coverage gates, risk bands, overlap suppression, typed input lineage, APIs, audit events, and evidence UI.
- Day 11 — **Complete:** historical observations and outcomes, horizon-safe labels, immutable feature snapshots, source lineage, company-isolated chronological splits, leakage gates, versioned JSONL metadata, audit events, CLI, and read-only dataset metadata API.
- Day 12 — **Complete:** train-only preprocessing, Logistic Regression, Random Forest, XGBoost, sigmoid calibration, safe binary metrics, validation-only selection, locked test evaluation, hashed artifacts, model registry, read-only APIs, and development inference foundation.
- Day 13 — **Complete:** expanding and rolling walk-forward evaluation, independent per-window fitting and calibration, aggregate stability, feature/prediction/calibration drift, model disagreement, rule/ML diagnostics, fusion-readiness gates, persistence, CLI, APIs, and an internal validation summary.
- Day 14 — **Complete:** versioned explainable rule and ML fusion experiments, weighted and consensus-gated strategies, integrity/readiness/data/drift/disagreement gates, deterministic confidence, safe fallback and no-output states, immutable lineage, persistence, APIs, audits, and an internal experiment view.
- Day 15 — **Complete:** versioned 5 Cs evidence synthesis, conservative Character and Conditions frameworks, persisted Capacity and Capital evidence, explicit-security Collateral extraction, confidence, completeness, deterministic summaries, review items, lineage, APIs, audits, and an internal five-section view.
- Day 16 — **Complete:** provider-based external company, promoter, legal, rating, industry, and sector research; source quality and freshness; entity matching; deduplication; immutable evidence and findings; 5 Cs candidates; safe retrieval controls; APIs; and an internal research view.
- Day 17 — **Complete:** research-enriched 5 Cs refresh, immutable refresh lineage, deterministic recommendation preparation, neutral readiness states, critical review flags, confidence caps, APIs, audits, and internal review pages.
- Day 18 — **Complete:** deterministic human-review recommendations, policy gates, explicit exceptions, review checklists, analytical exposure-ceiling methods, immutable lineage, APIs, audits, and internal review UI.
- Day 19 — **Complete:** role-governed human review cases, assignment history, evidence acknowledgement, checklist actions, information requests, policy-exception actions, explicit versioned human decisions, overrides, timelines, and immutable committee packages.
- Day 20 — **Complete:** fixed report snapshots, versioned CAM and committee memorandum generation, decision evidence packs, structured JSON export, PDF artifacts, SHA-256 integrity, source lineage, controlled finalization and supersession, APIs, audits, and an internal report workspace.
- Day 21 — **Complete:** immutable company RAG indexes, vendor-neutral deterministic embeddings, hybrid retrieval, company/scope/period isolation, grounded analyst Q&A, citations, chat and feedback lineage, prompt-injection defenses, evaluation metrics, APIs, audits, and an internal analyst workspace.
- Day 22 — **Complete:** normalized NSE/BSE listed entities and listings, deterministic fixture universe, dual-listing resolution, explainable peer discovery, provider-neutral OHLCV ingestion, freshness and partial-failure handling, APIs, audits, and internal UI.
- Day 23 — **Complete:** provider-neutral listed fundamentals, availability-date gating, deterministic valuation, peer, industry, and sector statistics, historical price/fundamental/relative features, drawdowns, lineage, APIs, audits, and UI.
- Day 24 — **Complete:** versioned stock ML datasets, trading-day labels, fixture benchmarks, purged and embargoed expanding splits, train-only preprocessing, deterministic baseline models, persisted predictions, metrics, artifacts, registry, APIs, and research UI.
- Day 25+ — **Planned:** Stock Intelligence Score, governed model/rule fusion, explainable cross-sectional ranking, and watchlist intelligence.

Each later increment should define its data contracts, failure behavior, and review requirements before implementation.

