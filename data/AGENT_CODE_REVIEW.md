# Conditia Production-Readiness Code Review

**Review date:** 2026-06-21

**Scope:** Entire repository after the security, lifecycle, persistence, frontend, and test hardening pass

**Stack found:** FastAPI, Pydantic, async SQLAlchemy, SQLite/PostgreSQL, Supabase Storage, React, TypeScript, and Vite. There is no Java or Spring Boot code.

## Executive summary

Conditia has moved from an unsafe prototype to a substantially safer development system. The current code prevents upload path traversal, verifies media, limits individual uploads, protects media delivery, supports fleet-scoped API-key access, validates domain inputs, finalizes inspections explicitly, persists idempotent analysis jobs, avoids false-clear reports when detection fails, applies database constraints, provides Alembic migrations, and runs automated CI checks. Current Python and npm production dependency audits are clean.

It is still **not ready for an internet-facing, multi-user production release**. The largest remaining blockers are:

- Authentication is a shared fleet API key, not user identity with roles and audit attribution.
- The PostgreSQL RLS/membership schema exists only in `db/schema.sql`; Alembic does not install it.
- The detector is explicitly experimental and cannot produce a validated automated safety result.
- Analysis runs inside API processes. Startup reclamation is unsafe during multi-instance rolling deployments and lacks leases, timeouts, backoff, and worker isolation.
- Request limits depend partly on `Content-Length`, and there is no rate limit, tenant quota, retention policy, or edge enforcement.
- Runtime database and captured media remain tracked in Git.
- PostgreSQL/RLS, real Supabase, frontend workflows, and true concurrency are not covered by integration tests.

**Recommendation:** keep deployment limited to trusted development or a single-fleet internal environment behind an identity-aware gateway. Do not represent automated findings as production-grade damage assessment.

## Verification performed

- Reviewed all repository source, SQL, migration, configuration, workflow, documentation, and test files; inspected tracked runtime artifacts separately.
- Searched for hardcoded credentials and unsafe SQL construction. No committed secret value or direct SQL-injection sink was found.
- `backend/.venv/bin/ruff check .` — passed.
- `backend/.venv/bin/python -m pytest -q` — **18 passed**.
- Fresh SQLite `alembic upgrade head` and `alembic check` — passed; no model drift detected for the ORM-managed schema.
- `backend/.venv/bin/pip check` — passed.
- `pip-audit -r backend/requirements.txt` — no known vulnerabilities.
- `npm test` — **3 passed**.
- `npm run build` — passed TypeScript checks and the Vite production build.
- `npm audit --omit=dev` — zero vulnerabilities.
- `git diff --check` — passed.

The failed attempt to run the initial migration over the existing unversioned development database was discarded; migration verification used a fresh temporary database. The tracked database and media were not deleted.

## Spring Boot / Java criteria

There is no Spring Boot or Java implementation to review. The requested concerns were evaluated against the FastAPI equivalents:

| Requested concern | FastAPI equivalent reviewed |
|---|---|
| Controller/service/repository separation | routers, workflow services, SQLAlchemy access |
| DTO vs entity usage | Pydantic schemas vs SQLAlchemy models |
| Validation annotations | Pydantic fields, enums, FastAPI query/form constraints |
| Exception handling | router translations and global exception handler |
| Transactions | `AsyncSession` boundaries and storage compensation |
| Dependency injection | FastAPI dependencies and remaining module-level globals |
| Configuration | `pydantic-settings` and production startup validation |

## Detailed findings

### AUTH-01 — Shared API key is not user authentication or role authorization

- **File/location:** `backend/security.py:1-38`; `backend/config.py:23-27,47-63`; `backend/models/db_models.py:86`; `backend/routers/findings.py:update_finding`; `frontend/src/api.ts:1-210`
- **Severity:** High
- **Category:** Security
- **Problem:** Production accepts one `X-API-Key` mapped to one fleet. `Principal` contains only `fleet_id`; it has no user ID or role. All holders can read and mutate the same resources, including resolving findings. `Inspection.created_by` is never populated. The browser client does not send the API key, so production UI access requires an external gateway that injects it.
- **Why it matters:** A leaked shared key grants fleet-wide access and cannot identify the actor, enforce least privilege, revoke one user, or produce defensible audit history. Putting the key in Vite configuration would expose it to every browser.
- **Recommended fix:** Verify short-lived OIDC/Supabase JWTs server-side; load fleet membership and role from the database; derive `created_by` from the principal; enforce an authorization matrix for viewer, inspector, and admin actions; retain API-key mode only for narrowly scoped service-to-service use. Use an HttpOnly session or bearer-token flow in the frontend—never a compiled shared secret.
- **Example improved code:**

```python
@dataclass(frozen=True)
class Principal:
    user_id: UUID
    fleet_id: UUID
    role: Role

def require_role(*roles: Role):
    async def authorize(principal: Principal = Depends(require_principal)):
        if principal.role not in roles:
            raise HTTPException(403, "Insufficient permission")
        return principal
    return authorize
```

### DB-01 — RLS and fleet memberships are outside the migration source of truth

- **File/location:** `backend/db/schema.sql:14-19,126-224`; `backend/migrations/versions/0001_initial.py:14-203`; `backend/models/db_models.py`
- **Severity:** High
- **Category:** Security
- **Problem:** `schema.sql` creates `fleet_memberships` and PostgreSQL RLS policies, but neither the ORM metadata nor Alembic migrations contain them. A fresh `alembic upgrade head` therefore passes its own drift check while producing a database without the documented membership/RLS defense.
- **Why it matters:** Deployment behavior depends on which schema path an operator chooses. A release using the documented migration workflow can silently omit tenant isolation.
- **Recommended fix:** Make Alembic the only schema authority. Add a PostgreSQL migration for memberships, indexes, RLS enablement, and policies; mark intentionally database-managed objects in Alembic comparison configuration; remove duplicate table DDL from setup instructions. Test the migration and policies against PostgreSQL with two users and two fleets.

### JOB-01 — In-process job reclamation is unsafe for multi-instance deployment

- **File/location:** `backend/main.py:38-45`; `backend/routers/inspections.py:finalize_inspection`; `backend/services/analysis_jobs.py:16-102`
- **Severity:** High
- **Category:** Business Rule
- **Problem:** The job row and atomic pending claim are useful, but work is launched with FastAPI `BackgroundTasks` and every API instance runs `resume_incomplete_analysis_jobs()` at startup. Startup changes every `running` job back to `pending` without a lease or heartbeat. During a rolling deployment, a new instance can reclaim work still running on an old instance.
- **Why it matters:** Two processes may analyze the same inspection concurrently, hold long database transactions, duplicate cloud cost, or race on findings/report replacement. CPU/video/cloud work also competes with request handling.
- **Recommended fix:** Move execution to a dedicated worker/queue. Add `lease_owner`, `lease_expires_at`, heartbeat, maximum attempts, exponential backoff, timeout, dead-letter/manual-retry state, and per-inspection idempotency. Reclaim only expired leases. Keep API finalization limited to the transaction that creates the job/outbox record.

### BR-01 — Damage detection is experimental, not a validated domain model

- **File/location:** `backend/services/vision.py:18-29,58-112`; `backend/services/report_generator.py:generate`; `backend/services/change_detection.py:find_first_occurrence`
- **Severity:** High
- **Category:** Business Rule
- **Problem:** Generic Google label detection is filtered by keywords. Confidence thresholds become provisional severity, there is no stable localization/bounding box, and every successful batch requires human review. The change rule uses only finding type and zone; unlocalized results are always treated as new.
- **Why it matters:** Model confidence does not measure repair urgency. Generic labels are not evidence of a defect, and the current output cannot support safety, maintenance, insurance, or compliance decisions.
- **Recommended fix:** Treat this integration as triage only. Define reviewed damage taxonomy and severity policy, required evidence, model/version provenance, calibrated thresholds, localization, human-review workflow, acceptance metrics, and a labeled evaluation set. Prevent production configuration from advertising automated clearance until those gates pass.

### SEC-02 — Request and resource-abuse controls are incomplete

- **File/location:** `backend/main.py:security_headers`; `backend/config.py:29-32`; `backend/routers/inspections.py:132-190`; `backend/services/storage.py:52-145`
- **Severity:** Medium
- **Category:** Security
- **Problem:** Individual files, file count, image dimensions, and declared request length are bounded. However, the request-wide limit trusts `Content-Length`; chunked/missing-length requests are not counted at the ASGI boundary. There is no request rate limit, per-inspection/tenant storage quota, total disk watermark, or upload concurrency limit.
- **Why it matters:** An authenticated or proxied attacker can consume parser temp space, network bandwidth, object-storage cost, worker capacity, or disk even when each stored file is valid.
- **Recommended fix:** Enforce body and multipart limits at the reverse proxy/API gateway and test chunked requests. Add tenant/user rate limits, inspection media/byte quotas, storage lifecycle/retention, disk/object-store monitoring, and upload concurrency/backpressure.

### SEC-03 — Runtime data and captured media remain in Git

- **File/location:** `backend/conditia.db`; `backend/storage/**`; `.gitignore`
- **Severity:** High
- **Category:** Security
- **Problem:** Ignore rules now prevent new database/media additions, but one SQLite database and eight captured images are already tracked (about 752 KB combined).
- **Why it matters:** VINs, timestamps, locations, findings, user identifiers, and customer imagery can remain recoverable in repository history. Mutable binaries also create noisy, risky diffs.
- **Recommended fix:** Confirm the files are synthetic and approved. Then remove them from tracking in a deliberate data-cleanup change, replace needed fixtures with documented synthetic assets, and assess history rewriting with repository owners/security. This review did not delete them because project guidance explicitly requires authorization.

### TX-01 — Analysis holds a database transaction across file and cloud processing

- **File/location:** `backend/services/analysis.py:analyze_inspection`; `backend/services/analysis.py:_analyze_frames`
- **Severity:** Medium
- **Category:** Spring Boot
- **Problem:** After deleting existing findings, the same session remains transactionally active while media is downloaded/materialized, video frames are extracted, Google calls run, and historical queries execute.
- **Why it matters:** Slow external I/O produces long transactions and locks, increases rollback work, and worsens contention. SQLite is especially sensitive, and PostgreSQL connections remain occupied during non-database work.
- **Recommended fix:** Read immutable input metadata first, perform detection outside a database transaction, then open a short transaction to verify the inspection/job lease and atomically replace findings/report/status. Persist intermediate artifacts or attempt records for safe retry.

### TX-02 — Upload storage/database compensation is best-effort

- **File/location:** `backend/routers/inspections.py:165-193`; `backend/adapters/mobile.py:receive_media`
- **Severity:** Medium
- **Category:** Spring Boot
- **Problem:** Files are stored before media rows commit. On database failure the route attempts deletion, but cleanup can itself fail and there is no orphan ledger or reconciliation job.
- **Why it matters:** Object storage and relational transactions cannot be atomic. Repeated partial failure can leak customer media and storage cost, while the raised cleanup error can obscure the original database failure.
- **Recommended fix:** Record upload intents/staging objects, promote after commit, and run idempotent orphan cleanup with retention. Preserve the primary exception and log cleanup failure separately with storage key and request ID.

### BR-02 — Required inspection coverage is undefined

- **File/location:** `backend/routers/inspections.py:finalize_inspection`; `frontend/src/pages/CapturePage.tsx:19-26,170-173,423-427`
- **Severity:** Medium
- **Category:** Business Rule
- **Problem:** The UI describes six angles but permits every angle to be skipped. The backend finalizes after any single media row and does not enforce required angles, media quality, recency, or source-specific coverage.
- **Why it matters:** Incomplete inspections look structurally valid and enter analysis/reporting. Coverage policy is business-critical and should not live only in UI text.
- **Recommended fix:** Define configurable inspection templates by asset/source, enforce required/optional angles and minimum quality server-side, return coverage state, and require an authorized override reason for incomplete submissions.

### SOLID-01 — Workflow services depend on global concrete infrastructure

- **File/location:** `backend/services/analysis.py:12-18`; `backend/services/analysis_jobs.py:8-11`; `backend/routers/inspections.py:32-34`; `backend/services/storage.py:create_storage_service`
- **Severity:** Medium
- **Category:** SOLID
- **Problem:** Analysis and job modules import `SessionLocal`, `storage_service`, detector functions, and report modules directly. Storage is created at import time. Routers also coordinate persistence and compensation.
- **Why it matters:** This violates dependency inversion, makes failure behavior depend on monkeypatching globals, complicates alternate workers/storage/detectors, and spreads transaction ownership.
- **Recommended fix:** Define application ports (`InspectionRepository`, `Storage`, `Detector`, `JobQueue`, `UnitOfWork`) and inject implementations at a composition root. Keep FastAPI routers responsible for HTTP translation only.

### CODE-01 — Several modules remain oversized and multi-purpose

- **File/location:** `frontend/src/pages/CapturePage.tsx` (433 lines); `frontend/src/styles.css` (about 1,179 lines); `backend/services/storage.py` (299 lines); `backend/routers/inspections.py` (243 lines)
- **Severity:** Medium
- **Category:** Code Smell
- **Problem:** Capture selection, truck registration, camera workflow, upload progress, finalization, and three phases share one component. Storage combines validation plus local and Supabase implementations. The inspection router still owns orchestration and compensation.
- **Why it matters:** Changes have broad regression scope, logic is harder to unit test, and parallel work creates conflicts.
- **Recommended fix:** Extract a tested capture reducer/hook and phase components; split storage validation from provider implementations; move ingestion/finalization into command services; split CSS by shell/dashboard/capture when those areas are next changed.

### FRONT-01 — Frontend transport contracts are only partially runtime-validated

- **File/location:** `frontend/src/api.ts:75-176`; `frontend/src/mapInspection.ts`; `frontend/src/api.ts:198-204`
- **Severity:** Medium
- **Category:** Code Smell
- **Problem:** Inspection mapping validates important enum fallbacks, but most API responses are still asserted with `as Promise<T>`. Upload errors expose raw response text instead of using the safe structured decoder. There is no authentication/session handling.
- **Why it matters:** Backend contract drift can become invalid UI state. Raw proxy/server bodies can produce poor or sensitive error messages, and the production authentication contract is incomplete.
- **Recommended fix:** Generate types/client code from OpenAPI or validate all responses with a runtime schema; centralize fetch/XHR headers, timeouts, request IDs, and safe error parsing; add an identity/session adapter before production UI deployment.

### OPS-01 — Production observability and data operations are not defined

- **File/location:** `backend/main.py:16-18,76-107`; `backend/services/analysis_jobs.py`; repository-wide deployment configuration
- **Severity:** Medium
- **Category:** Spring Boot
- **Problem:** Logs are safer and include request IDs, but there are no metrics, traces, audit events, alert thresholds, backup/restore procedure, retention policy, job dashboard, or deployment manifests. Rate limiting and HSTS are delegated but not specified as a tested deployment contract.
- **Why it matters:** Production failures, stuck jobs, authorization changes, storage growth, and detector degradation may be discovered late or be impossible to investigate.
- **Recommended fix:** Add structured JSON logging, metrics for request/job/storage/detector behavior, trace propagation, immutable audit events, alerts, backup/restore drills, retention/deletion policy, and an explicit reverse-proxy security baseline.

### TEST-01 — Important integration and UI behavior remains untested

- **File/location:** `backend/tests/`; `frontend/src/mapInspection.test.ts`; `.github/workflows/ci.yml`
- **Severity:** High
- **Category:** Testing
- **Problem:** The new suite covers critical validation, storage, fleet isolation, lifecycle, recovery, findings, query counts, and mapping. It does not run PostgreSQL, RLS policies, real Supabase, a real queue, multi-process concurrency, frontend components, camera APIs, or end-to-end workflows. CI has no coverage threshold, secret scan, SAST, or container/deployment test.
- **Why it matters:** The remaining production risks exist at infrastructure boundaries and concurrency points that SQLite/unit tests cannot prove.
- **Recommended fix:** Add PostgreSQL/Testcontainers migration and RLS tests; storage contract tests against a Supabase test project/emulator; concurrent worker tests; React Testing Library capture/dashboard tests; Playwright happy/failure paths; coverage reporting; secret/SAST/container scanning.

## Positive observations and remediated findings

- No hardcoded credential or string-built SQL query was found.
- Upload paths use server-generated names and enforce root containment.
- Images are signature-checked, decoded with Pillow, dimension-limited, streamed in chunks, fsynced, and atomically moved; partial writes are cleaned up.
- Media is served through a fleet-authorized endpoint or short-lived private Supabase URL, not a public static mount.
- Production refuses disabled auth, SQLite, local storage, startup seeding, enabled docs, and local CORS origins.
- Routes apply fleet predicates in API-key mode; cross-fleet tests cover trucks and inspections.
- The inspection state machine separates upload and finalize; one unique job is created transactionally and duplicate delivery is a no-op.
- Detector unavailability/failure yields `review_required` or `failed`, never a false successful clear report.
- UUIDs, VINs, domain enums, GPS, confidence, years, limits, and finding transitions are validated.
- ORM constraints, foreign-key behavior, report/job uniqueness, Alembic migrations, and SQLite FK enforcement are present.
- Inspection summary queries are batched and have a query-count regression test.
- Safe exception bodies, request IDs, redacted startup logging, security headers, restricted CORS, configurable docs, and readiness checks are implemented.
- Backend and frontend vulnerable dependencies were upgraded; current production audits are clean.
- CI now runs lint, tests, build, migrations, and dependency audits.

## Top 10 most important fixes

1. Replace the shared API key with short-lived user identity, fleet memberships, roles, and actor/audit attribution.
2. Put memberships and all PostgreSQL RLS policies into Alembic and test cross-tenant policies on PostgreSQL.
3. Move analysis to leased dedicated workers; add timeout, heartbeat, backoff, maximum attempts, and dead-letter/manual retry.
4. Validate the damage model and severity policy with labeled data and mandatory human-review workflow.
5. Enforce request size/rate/storage quotas at the edge and application levels, including chunked uploads.
6. Define and enforce required inspection coverage/templates server-side.
7. Shorten analysis transactions and formalize storage/database reconciliation.
8. Remove tracked runtime data after privacy/ownership approval and establish retention/deletion controls.
9. Add PostgreSQL/RLS/Supabase/concurrency and frontend E2E integration coverage.
10. Add production observability, immutable audit events, backup/restore drills, and deployment security controls.

## Quick wins under 30 minutes

- Stop returning `storage_path` in `MediaOut`; clients only need media ID/type/angle/time.
- Parse XHR error JSON through the same safe `detail` decoder used by fetch calls.
- Add `order_by` to findings lists for deterministic UI/test behavior.
- Add `Secure`, `SameSite`, and CSRF requirements to deployment documentation for any future cookie session.
- Add explicit reverse-proxy examples for body limits, HSTS, request rate limits, and timeouts.
- Add a CI secret-scanning step and Dependabot/Renovate configuration.
- Add a production startup warning/error when no identity-aware gateway contract is configured for API-key mode.
- Document who may resolve/false-positive findings before implementing role checks.
- Add job-age and failed-job queries to readiness/operations documentation.
- Add a synthetic-data marker/license for retained development fixtures.

## Larger refactors requiring planning

1. **Identity and tenancy:** OIDC/Supabase JWT verification, membership/role model, UI session, audit events, RLS migrations, and existing-data ownership migration.
2. **Worker architecture:** queue/outbox, leases, isolated video/model execution, backpressure, retry/dead-letter behavior, and deployment topology.
3. **Validated inspection domain:** templates/coverage, quality gates, reviewed damage taxonomy, severity policy, model registry, human review, and defect identity/change matching.
4. **Transactional ingestion:** staged objects, upload intents, promotion, reconciliation, retention, deletion, and storage lifecycle rules.
5. **Application boundaries:** command/query services, repositories, unit of work, infrastructure ports, and one composition root.
6. **Frontend capture decomposition:** reducer/state machine, registration and phase components, runtime-generated API client, authentication/session adapter, and component/E2E tests.
7. **Production platform:** PostgreSQL/Supabase integration environment, metrics/traces/alerts, backups, secrets management, gateway policy, and disaster recovery.

## Suggested cleaner package structure

```text
backend/
  app/
    api/
      routers/
      dependencies.py
      errors.py
    application/
      commands/
        create_inspection.py
        ingest_media.py
        finalize_inspection.py
      queries/
        inspection_queries.py
      ports/
        repositories.py
        storage.py
        detector.py
        jobs.py
      unit_of_work.py
    domain/
      inspection.py
      finding.py
      identity.py
      policies/
        coverage.py
        severity.py
        change_matching.py
    infrastructure/
      db/
        models.py
        repositories.py
        migrations/
      auth/
        oidc.py
      storage/
        local.py
        supabase.py
      detection/
        google_experimental.py
      jobs/
        worker.py
    config.py
    main.py
  tests/
    unit/
    api/
    integration/
    security/

frontend/src/
  app/
  features/
    capture/
      CapturePage.tsx
      useCaptureSession.ts
      captureReducer.ts
      components/
    dashboard/
    findings/
  shared/
    api/
      client.ts
      generated.ts
    auth/
    domain/
    components/
    styles/
```

Introduce this incrementally behind tests. Moving files without changing responsibilities is not a refactor.

## Suggested testing strategy

1. **Unit/domain:** inspection transition and coverage tables; severity policy; defect matching; storage validation/containment; auth role matrix; frontend capture reducer and DTO parsers.
2. **API/security:** unauthenticated, expired/revoked token, role denial, two-fleet BOLA tests for every resource, chunked/oversized/corrupt uploads, safe errors, and rate limits.
3. **Concurrency/workers:** simultaneous finalize, duplicate delivery, active-vs-expired leases, worker crash at each checkpoint, timeout/retry/dead letter, report/finding uniqueness.
4. **PostgreSQL/RLS:** migrate empty and prior schemas; test constraints, indexes, RLS with separate authenticated users, service-role boundaries, rollback, and backup/restore.
5. **Storage contracts:** run the same upload/download/delete/signed-delivery suite against local and Supabase test storage, including partial failures and orphan cleanup.
6. **Frontend components:** camera denied/unsupported, recording, progress, retry, skip/coverage errors, finalize, polling cleanup, manual-review/failed states, and authenticated media.
7. **End to end:** login -> register truck -> create inspection -> upload required coverage -> finalize -> deterministic fake worker -> human review -> resolve finding -> report/dashboard.
8. **CI/release gates:** Ruff, type checks, pytest with coverage, frontend tests/build, PostgreSQL migrations/RLS, dependency/secret/SAST scans, image scan, and smoke test in a production-like environment.

## Final production-readiness score

### **5 / 10**

| Area | Score | Assessment |
|---|---:|---|
| Security | 5/10 | Upload/media/config substantially hardened; user auth, roles, migration-installed RLS, abuse controls, and tracked-data cleanup remain |
| Business correctness | 5/10 | Lifecycle/failure semantics are sounder; detector, coverage, severity, and change identity are not production-validated |
| Architecture/maintainability | 6/10 | Useful DTO/adapter/query/job boundaries, but global infrastructure and large workflow modules remain |
| Testing | 6/10 | CI and meaningful regression tests exist; production infrastructure, concurrency, components, and E2E are missing |
| Operations/data | 4/10 | Migrations/readiness/private storage exist; worker topology, observability, backup/retention, and deployment controls are incomplete |

The application is appropriate for controlled development and possibly a single-fleet internal pilot behind a trusted gateway with mandatory manual review. It is not ready for public multi-tenant production or automated safety/maintenance decisions.
