# Day 29 completion and validation report

## Day 29 Status

**COMPLETE — local Day 29 implementation and validation.** All 473 backend tests passed
with one optional OCR skip; deployment limitations below remain explicit release gates. This record distinguishes local validation from deployment certification.
Day 30 has not started. No commit, push or publication was performed.

## Environment / Configuration

Typed development/test/staging/production settings validate secrets, explicit HTTPS origins,
trusted hosts, absolute storage, database and shared Redis adapters in controlled environments.
Environment examples contain placeholders. Signing keys and connection secrets are excluded
from normal settings serialization; production debug and unsafe policy overrides are rejected.

## Authentication

Argon2 password verification; short-lived HS256 tokens bound to issuer, audience, account,
role and token version. Each protected request rechecks current account state and grants.
An interactive administration command provisions credentials without command-line passwords.
Existing accounts need explicit provisioning. No refresh-token or external identity-provider
integration is claimed.

## Authorization

Versioned seven-role runtime policy, company access grants, resource-reference checks and
request-session company/owner filtering. Caller-supplied actor IDs must match the token subject.
Stock services use independent actor checks: research analysts can build, viewers can read,
and neither acquires credit RAG authority. Legacy direct service actors remain compatible;
HTTP stock mutations require the runtime build permission. Existing report-download and human
credit review authority remain additional service-level restrictions.

## Security

Safe correlated error responses, production detail suppression, secret-redacted structured
logs, trusted hosts, explicit CORS, security headers and production HSTS. Request JSON,
uploads, query values, pagination, reference traversal and JSON responses are bounded.
Artifact downloads enforce access, root containment and SHA-256 integrity. Public dependency
status omits connection details. No production test-auth override exists.

## Async Jobs

Typed report/research/parse/dataset/train/monitoring submissions persist in a SQL ledger.
Canonical idempotency hashes and unique constraints deduplicate submissions. Atomic claims,
leases and fenced completion prevent duplicate active ownership and late result replacement.
Attempts retain retry/cancellation/timeout history. The bounded child-process supervisor calls
existing services, rechecks authorization and terminates the owned process tree on timeout.
Database delivery works locally; Redis RQ delivery and SQL outbox are provided for deployment.

## Health

Minimal public liveness/readiness; administrator dependency detail includes DB connectivity,
migration head, storage, authentication, queue/rate adapters and optional OCR. Missing Redis
in production was verified to keep liveness available while readiness and protected requests
fail closed. The readiness CLI returns READY/WARN/NOT_READY with safe detail.

## Observability

Request IDs propagate into logs, security events and job records. Structured logs redact
secrets. Bounded process-local counters/timings provide a metrics foundation; persistent SQL
job counts supplement it. No deployed metrics collector or fleet-wide telemetry is claimed.

## Rate Limiting

Development/test use a bounded in-memory adapter. Controlled environments require the shared
Redis implementation, including login and per-user request limits, with no memory fallback.

## Storage

Persistent artifact root; relative contained paths only. Traversal, drive-relative names,
unsafe symlinks and integrity mismatches fail safely. Cleanup targets only expired runtime
temporary files. Reports, models, documents, source lineage and audit history are retained.

## Database

Bounded pools, pre-ping, recycle and connection timeout settings. Migration
`0028_production_runtime_and_jobs` adds company grants, background jobs, job attempts and
account authentication/state fields with indexes and constraints. New role rollback requires
explicit reconciliation; it never silently grants elevated roles.

Long-transaction review: asynchronous requests remove browser waiting from expensive work.
Existing services still own their transactions, including rendering/research boundaries;
these were not rewritten because doing so could alter analytical persistence semantics.
Cancellation can race with an already committed artifact; the artifact remains historical,
while fenced job completion cannot overwrite a cancellation.

## Deployment

Non-root backend/frontend images, pinned application dependencies, production Compose with
API, migration service, dispatcher, worker, PostgreSQL, Redis and persistent artifact storage.
TLS terminates at a separately configured proxy; published ports are loopback-bound.
Docker is unavailable locally, so images/Compose were inspected and configuration parsed,
but container startup and Redis RQ end-to-end execution remain unverified. Follow the
[runtime runbook](day29-production-runtime.md) for secrets, migrations, accounts, backup,
restore, retention and dependency checks. Backup/restore drills remain deployment work.

## Production Provider Safety

Market, fundamentals and external research fixture providers remain development providers.
Their execution is rejected in controlled environments; no silent fixture fallback is allowed.
Production stock ML and external research flags default off in deployment configuration.
Approved real providers and target-environment validation are prerequisites for live use.

## APIs

Token/me, typed job submission/list/detail/cancel/retry, public live/ready and protected
administrator runtime/security/dependency/metrics/account/grant endpoints. Existing APIs now
require authentication and policy authorization. Expensive production synchronous entry points
require asynchronous submission. Report evidence supports bounded pagination. Development/test
OpenAPI builds; production documentation endpoints are disabled by configuration.

## Frontend

Memory-only authentication, actor binding to verified identity, destination-restricted API
requests, clear unauthorized/expired responses and sign-out clearing private workspaces.
Operations UI shows jobs, cancellation/retry, queued report generation and administrator
runtime status. Downloads use authenticated requests. A non-production analytical banner
remains visible. Report evidence is paginated.

## Tests

Previous baseline: **440 passed, 1 skipped**. Final full regression: **473 passed, 1 skipped**
in 287.56 seconds. The 33 added Day 29 cases passed. Latest focused checks: **35 passed**,
covering all current Day 29 tests plus two Day 28 report API integration tests. This full run
includes the stock actor and report-pagination compatibility fixes.
The optional OCR test is skipped because Tesseract is unavailable.

## Migration Verification

An isolated disposable database was created for verification. Clean database to head,
Day 29 downgrade/reapply, full base-to-head round trip and `alembic check` passed with no
schema drift. Both database environment selectors were pinned to that isolated database.
See [machine-readable smoke evidence](../output/day29-smoke/verification.json).
The existing development database was not downgraded or reset.

## Security Verification

Tests cover unauthenticated and role-denied requests, cross-company references, current
account revocation, actor spoofing, secret redaction, rate-limit behavior, traversal, artifact
integrity and policy/config rejection. New stock-role tests also prove credit RAG remains
unavailable to viewer/research roles. Production missing-Redis behavior was exercised.

Dependency audit: Python environment **no known vulnerabilities**; frontend production-only
installation **zero advisories**. Next was patched to 16.3.6, source-map-js to 1.2.2, pytest to
9.0.3 and installer pip to 26.2.1. Five high development-only frontend audit entries remain in
the braces/micromatch/fast-glob/Next ESLint chain. The audit's suggested incompatible downgrade
was not applied. Review and patch that tooling chain when a compatible fix is available.

## Reliability

Tests cover deduplication, ownership, retry bounds, permanent failure behavior, cancellation,
stale-job recovery, supervisor timeout and dependency degradation. A real worker child
completed a queued report; its authenticated PDF download passed integrity verification.
Single local smoke observations: liveness 21.84 ms, enqueue 184.56 ms. These are not load,
concurrency or capacity guarantees. Redis and multi-replica deployment need separate testing.

## Analytics Immutability

No Day 24 prediction logic, Day 25 scoring, Day 26 validation, Day 27 monitoring formula,
credit policy or Day 28 snapshot construction was changed. Stock service edits are actor
checks and explicit fixture-provider guards. Artifact read protection preserves immutable
content. Regression-generated canonical Day 28 smoke exports were restored after testing;
new Day 29 exports live in a separate output directory.

## Quality

Ruff lint passed; formatting passed for 311 Python files. MyPy passed for 245 application
files. Frontend TypeScript, ESLint and production build passed (18 static routes). Runtime
request-client checks and all nine Day 28 report section render checks passed. OpenAPI is
covered by runtime tests. Final full regression passed as recorded above.

## Known Limitations

- Development market/fundamental and external research providers remain unsuitable for live use.
- Tesseract is unavailable; one optional OCR test is skipped.
- Docker runtime and Redis RQ deployment are unverified locally; deployment foundation only.
- Five development-tool dependency advisories remain; production frontend and Python audits are clean.
- Existing analytical transaction boundaries and process-local telemetry limitations remain.
- Stock ML remains `PIPELINE_VALIDATION_ONLY`: no production stock prediction, live model serving,
  BUY/SELL/HOLD, target price, return forecast or automated trading.
- No autonomous credit approval. Day 29 does not certify regulatory/compliance deployment.

## Day 30 Readiness

Local Day 29 validation is complete and the system is ready for a separately authorized
final integration/release-readiness stage. Target-environment
container/Redis, TLS, secret provisioning, backup/restore and operational capacity checks
remain explicit release gates. Day 30 has not been implemented.

The backend image uses Python 3.13 to match local validation and satisfy the pinned NumPy/SciPy
Python requirement. It includes libgomp1 for Linux numerical/ML dependencies. Container execution
is still a target-environment verification gate.
