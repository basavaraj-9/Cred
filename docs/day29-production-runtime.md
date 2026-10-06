# Day 29 production runtime

Status: **COMPLETE — local implementation and validation; deployment gates remain**. Day 30 has not started.

## Runtime boundaries

The runtime layer adds authentication, company access grants, request limits, durable jobs,
dependency probes and deployment configuration. It delegates all analytical work to existing
services. Credit authority, maker-checker rules, committee decisions, immutable report versions,
and stock/credit separation remain enforced by their existing services.

The stock ML lifecycle remains `PIPELINE_VALIDATION_ONLY`. There is no production stock
prediction, live model serving, BUY/SELL/HOLD signal, target price, return forecast, automated
trading, or autonomous credit approval. Runtime readiness does not certify regulatory or
compliance readiness.

## Accounts and access

Provision an account with `python -m app.runtime.admin EMAIL --role ROLE` from the backend
directory. The command reads the password without echo, stores an Argon2 hash, and increments
the token version when replacing credentials. It never accepts passwords on the command line.
Use the administrator company-access API to grant/revoke access to existing companies.
Existing users have no password after migration and must be explicitly provisioned.

`POST /api/v1/auth/token` accepts email and password. Tokens are HS256, issuer/audience bound,
short lived (15 minutes by default), and checked against current account state, role, token
version and company grants on each request. Disabled/locked/pending users cannot log in or
reuse an existing token. No development bypass exists in application settings. Legacy tests
override the dependency in `tests/conftest.py`; `strict_auth` tests exercise the real boundary.

Seven roles are declared in `app/runtime/authorization_policy_v1.json`. Service-specific
report and human-credit authority checks remain additional restrictions. An operational
permission cannot grant a credit decision authority that the original service denies.
Caller-supplied acting-user IDs must match the authenticated subject.

The frontend holds short-lived tokens in memory, clears them on sign-out/expiry/reload, and
uses authenticated fetches for artifacts. It does not store credentials in browser storage.

## Jobs

`POST /api/v1/jobs` accepts a discriminated, extra-fields-forbidden payload for REPORT_360,
RESEARCH, STOCK_DATASET, STOCK_TRAIN, MONITORING or PARSE. Actor identity is server supplied.
The idempotency key, canonical payload, company and actor form the durable input hash.
The unique database constraint makes concurrent duplicate submissions converge.

Read jobs with `GET /api/v1/jobs` or `GET /api/v1/jobs/{id}`. Owners and administrators can
cancel; retries require the original permission and an eligible transient failure/timeout.
Attempts remain preserved. A lease prevents a late attempt from replacing a cancellation or
newer attempt. Claims use `FOR UPDATE SKIP LOCKED`, bounded retries and exponential backoff.

Development worker: `python -m app.runtime.worker` (`--once` for a bounded smoke run).
Production uses `python -m app.runtime.dispatch` plus `python -m app.runtime.rq_worker`.
Redis transports JSON-only delivery messages; SQL is the authoritative ledger and durable
outbox. Redis unavailability leaves work queued for later dispatch. No arbitrary callable,
shell command, pickle payload or uploaded model path is accepted by the job API.

The supervisor runs each job in a separate process and terminates it on deadline or
cancellation. Job-specific timeout caps are bounded by JOB_TIMEOUT_SECONDS. Stale RUNNING
jobs are marked TIMED_OUT after their deadline plus recovery grace. A worker rechecks the
submitter's current account, permission and company grants before analytical work.

Service transactions remain owned by existing services. Browser requests are decoupled from
long analytical transactions; this release does not rewrite existing report-render or
research transaction boundaries. Cancellation can race with an already committed analytical
artifact: historical artifacts are preserved and the cancelled job cannot publish a late
result. Review this boundary before providing stronger business-level cancellation guarantees.

## Configuration and diagnostics

APP_ENV is development, test, staging or production. Staging and production require a
database, signing key of at least 32 characters, explicit HTTPS origins, explicit trusted
hosts, HTTPS deployment acknowledgement, absolute artifact root, shared Redis rate limits
and Redis queue. Debug must be off. Configuration errors hide supplied values.

Public `/health/live` checks process responsiveness without dependency access.
Public `/health/ready` returns only READY/NOT_READY. `/health/dependencies`, `/metrics`,
`/api/v1/admin/runtime` and `/api/v1/admin/runtime/jobs` require administrative access.
Run `python -m app.runtime.readiness` for safe READY/WARN/NOT_READY output and failure exit
status. Missing optional Tesseract produces WARN, not false readiness for OCR workloads.

Structured logs carry request IDs and redacted operational context. HTTP and worker metrics
must use bounded labels; user/company/request IDs belong in logs, never metric labels.
The metrics sink is process-local instrumentation, not a deployed multi-process metrics
collector. Durable job counts are available from the SQL-backed admin endpoint.

Production fixture providers fail explicitly. Market/fundamental and external research
providers remain development fixtures where unchanged. No silent fixture fallback is allowed.
Existing analytical records remain labeled non-production even if runtime dependencies are ready.

## Deployment sequence

1. Supply secrets with a deployment secret manager. Never commit populated environment files.
   No secret may use a NEXT_PUBLIC_ variable. Pin container digests in the deployment release.
2. Terminate TLS at a trusted reverse proxy. Bind application ports to loopback as shown in
   `compose.production.yml`; restrict direct backend access and trust forwarding headers only
   from that proxy. Configure trusted hosts to match the public API host.
3. Back up PostgreSQL and the complete artifact volume before migration.
4. Run the one-shot migration service and require successful completion before starting API,
   dispatcher and workers. Run migrations once per deployment, never independently per worker.
5. Provision an administrator. Grant company access explicitly. Start one worker initially;
   bound replica count and DB pools to available database capacity.
6. Run readiness and authenticated smoke checks. Review dependency warnings and queue age.

Backend and frontend images run as non-root users. Artifact storage is persistent and must
be writable by UID 10001; restrict filesystem access to the service account. Images exclude
environment files, virtual environments, caches and local test artifacts.

## Backup, restore and retention

Use PostgreSQL `pg_dump` in custom format with credentials supplied through a protected
password file or secret manager. Back up the artifact volume at the same recovery point;
the database contains artifact paths and hashes, not substitutes for artifact content.
Record migration head, application release, policy versions and artifact hash manifests.

Restore to an isolated database and artifact root, run migrations for the chosen release,
verify hashes and source links, and execute readiness/report-download smoke checks before
switching traffic. Never overwrite immutable report artifacts during restore verification.

Cleanup targets only expired `.runtime-temporary/*.temporary` files. Reports, source PDFs,
models, audit logs, snapshots and job attempts are excluded. No automatic history retention
deletion is enabled. Downgrading Day 29 requires explicit reconciliation of new VIEWER and
RESEARCH_ANALYST accounts; migration rollback never silently grants them a stronger role.

## Validation record

Final backend regression: 473 passed, one optional OCR skip. All 35 focused checks, backend
quality checks, frontend TypeScript/lint/build, migration round trips, schema drift and the
real-worker smoke passed. See the [completion report](day29-completion-report.md) for evidence
and remaining Docker/Redis deployment and dependency-audit limitations.

The backend image uses Python 3.13 to match local validation and satisfy the pinned NumPy/SciPy
Python requirement. It includes libgomp1 for Linux numerical/ML dependencies. Container execution
is still a target-environment verification gate.
