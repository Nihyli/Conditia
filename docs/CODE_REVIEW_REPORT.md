# Conditia Clean-Code and Architecture Review

**Review date:** 2026-06-21

**Scope:** Current repository after the incremental refactor described below.

## Project structure summary

Conditia is a small fleet-asset condition system, not a Java/Spring project.

| Area | Technology | Responsibility |
|---|---|---|
| `backend/routers/` | FastAPI | HTTP parsing, authorization dependencies, response models, HTTP error translation |
| `backend/services/` | Python application services | Inspection ingestion/finalization, analysis, jobs, report generation, change detection, read models |
| `backend/adapters/` | Python abstractions/adapters | Source-specific media ingestion; mobile is the only registered source |
| `backend/models/` | Pydantic and SQLAlchemy | API contracts and persistence models |
| `backend/migrations/` | Alembic | Versioned relational schema changes and legacy SQLite compatibility |
| `backend/db/schema.sql` | PostgreSQL/Supabase reference DDL | Supabase memberships and RLS reference currently not represented fully in Alembic |
| `frontend/src/pages/` | React | Route-level composition for dashboard and capture flows |
| `frontend/src/features/` | React hooks/domain workflow | Feature-specific state and application workflow, currently capture sessions |
| `frontend/src/components/` | React | Reusable UI and camera/media presentation |
| `frontend/src/api.ts` | TypeScript | HTTP transport and API DTO contracts |
| `frontend/src/mapInspection.ts` | TypeScript | Runtime normalization from API DTOs to UI domain models |
| `.github/workflows/ci.yml` | GitHub Actions | Lint, coverage, migrations, build, and dependency audits |

The primary business flow is:

```text
register truck
  -> start inspection (uploading)
  -> upload validated media through a capture adapter
  -> finalize once (submitted + durable job row)
  -> claim/analyze (processing)
  -> complete | review_required | failed
  -> dashboard read model and report
```

## Main problems found

### 1. Inspection HTTP router owned application workflow — resolved

`routers/inspections.py` previously handled capture-adapter selection, storage calls, persistence, compensation, state transitions, and job creation. This violated SRP and made the workflow difficult to reuse outside HTTP.

The write lifecycle now lives in `services/inspection_ingestion.py`. The router validates transport input, loads an authorized resource, calls the service, and translates known errors. Storage cleanup is best-effort without masking the original database failure.

### 2. Capture and analysis depended on hidden infrastructure globals — improved

`MobileAdapter` previously imported the global storage singleton. Analysis directly referenced global storage, detector, and report modules.

- `MobileAdapter` now receives the narrow `MediaWriter` capability.
- `InspectionIngestionService` receives an adapter registry and cleanup capability.
- `AnalysisDependencies` provides materialized storage, detector, and report-builder capabilities.
- `dependencies.py` is the explicit application composition root.

`analysis_jobs.py` still constructs `SessionLocal` directly. That is documented as remaining work because changing it safely should accompany the dedicated-worker design.

### 3. An unregistered future adapter violated LSP/YAGNI — resolved

`DroneAdapter` implemented the adapter type but always raised `NotImplementedError`. It was not substitutable for a valid adapter and advertised a capability that did not exist. It was deleted. Historical `drone`/`fixed_camera` values remain valid persistence values, while `IngestibleCaptureSource` explicitly permits only mobile input.

### 4. Legacy storage-repair script bypassed current invariants — resolved

`sync_storage.py` directly wrote SQLite rows, inferred types from extensions, hardcoded the mobile source, copied files synchronously, and could reintroduce the legacy UUID format. Nothing in the runtime or documentation called it. It was removed rather than maintained as a second ingestion path.

### 5. Capture page mixed two independent workflows — improved

`CapturePage.tsx` previously owned truck loading/registration and the complete inspection capture state machine in one 433-line component.

The capture lifecycle now lives in `features/capture/useCaptureSession.ts`, with an injectable API contract. `CapturePage` is reduced to route/page composition and truck setup. Registration errors are no longer coupled to capture/finalization errors.

The page still contains a sizeable truck-selection/registration view. Extracting it is reasonable when that UI next changes, but doing so now would be file movement with little additional behavior isolation.

### 6. Frontend request/error handling was duplicated — resolved

GET and POST functions duplicated timeout, status, error-body, and JSON handling. XHR upload failures exposed arbitrary raw response text.

All JSON requests now use one `requestJson` function and one safe `detail` decoder. Upload errors use the same policy and fall back to a stable status message.

### 7. Magic lifecycle values were repeated — improved

Fleet statistics and change detection repeated raw inspection/finding status strings. They now use `InspectionStatus` and `FindingStatus` values from the domain module. Database check constraints still contain SQL literals, which is appropriate because migrations must remain immutable and database-readable.

### 8. Storage module has multiple responsibilities — remaining

`services/storage.py` contains media sniffing, image validation, local storage, Supabase storage, materialization, and provider construction.

It is cohesive enough for the current size and well tested, so this refactor does not split it solely to reduce line count. If another provider or validation policy is added, split it into:

```text
services/storage/
  contracts.py
  validation.py
  local.py
  supabase.py
```

### 9. Persistence/tenant schema has two sources of truth — remaining, high priority

Alembic manages application tables, but `db/schema.sql` separately contains Supabase memberships and RLS. A deployment using only Alembic does not receive those policies.

This is not safe to “refactor” without a PostgreSQL integration environment. Add PostgreSQL-only Alembic revisions and cross-tenant RLS tests, then demote or remove the duplicate DDL.

### 10. Authentication and roles are incomplete — remaining, high priority

Production authentication is one fleet-scoped service API key. It is not user identity, RBAC, or audit attribution. Replacing it requires an explicit identity-provider and session decision; inventing one during a clean-code refactor would violate YAGNI and risk changing public behavior.

### 11. Job execution remains coupled to API processes — remaining, high priority

The job record is durable and claims are idempotent, but FastAPI background tasks execute analysis in web processes. Startup reclamation has no lease/heartbeat and is unsafe for rolling multi-instance deployment.

Move execution to a worker only with a complete lease, retry, timeout, backoff, and dead-letter design. A queue abstraction without those semantics would add indirection without solving the failure model.

## SOLID assessment

| Principle | Finding | Refactor/status |
|---|---|---|
| Single Responsibility | Inspection router and capture page owned unrelated concerns | Write lifecycle moved to an application service; capture lifecycle moved to a feature hook |
| Open/Closed | Source resolution was a module-level concrete map | `CaptureAdapterRegistry` accepts configured implementations; adding a real adapter does not modify ingestion logic |
| Liskov Substitution | Drone stub implemented the contract but always failed | Stub removed; only operational implementations are registered |
| Interface Segregation | Components depended on a full concrete storage service | `MediaWriter`, `MediaCleanup`, and `MaterializedStorage` expose only capabilities each consumer needs |
| Dependency Inversion | Mobile and analysis imported concrete global infrastructure | Constructors/dependency objects now receive abstractions; `dependencies.py` wires defaults |

## Clean-code assessment

| Concern | Finding | Status |
|---|---|---|
| DRY | Repeated fetch/POST/error handling | Consolidated in `requestJson` and `detailMessage` |
| KISS | Fake future adapter and repair script added unsupported paths | Removed |
| YAGNI | Drone phase stub suggested unimplemented behavior | Removed while retaining compatible persisted values |
| Naming | Global adapter map hid composition | Replaced by `CaptureAdapterRegistry` and explicit composition root |
| Small functions | Capture workflow and router functions were long/mixed | State transitions and persistence moved to focused methods/hook functions |
| Error handling | Cleanup failure could mask the database exception; XHR returned raw bodies | Cleanup is logged without replacing the primary failure; client errors are safely decoded |
| Logging | Storage compensation lacked operational context | Structured logger records the storage key without response leakage |
| Configuration | Limits, origins, storage, auth, and deployment mode are typed settings | Preserved; no new environment-specific constant introduced |
| Testability | Important behavior required monkeypatching globals | Capture and analysis dependencies can be passed directly; coverage tests exercise those seams |

## Files changed and rationale

### Backend architecture

| File | Change | Why |
|---|---|---|
| `backend/adapters/base.py` | Added small storage capability protocols and clarified adapter contract | ISP and explicit structural contracts |
| `backend/adapters/mobile.py` | Injected storage writer | Removes hidden concrete dependency |
| `backend/adapters/registry.py` | Replaced global map/function with encapsulated registry | OCP, encapsulation, and testability |
| `backend/adapters/drone.py` | Deleted nonfunctional stub | LSP and YAGNI |
| `backend/dependencies.py` | Added composition root | Keeps concrete wiring outside business services |
| `backend/services/inspection_ingestion.py` | Added inspection write application service | SRP, transaction ownership, storage compensation |
| `backend/routers/inspections.py` | Delegated writes to application service | Thin transport layer and preserved API |
| `backend/services/analysis.py` | Added injectable analysis dependencies | DIP and worker/test reuse |
| `backend/routers/fleet.py` | Reused typed status values and retained explicit joins | Removes magic strings and ambiguous relationship inference |
| `backend/services/change_detection.py` | Reused typed status values | Removes duplicated domain literals |
| `backend/sync_storage.py` | Deleted unsafe/dead alternate ingestion path | One authoritative ingestion workflow |
| `backend/models/db_models.py`, `backend/db/schema.sql`, `backend/README.md` | Removed speculative phase wording | Documentation now describes current behavior only |

### Frontend architecture

| File | Change | Why |
|---|---|---|
| `frontend/src/features/capture/useCaptureSession.ts` | Added injectable capture-session workflow | Separates state/business flow from page rendering |
| `frontend/src/pages/CapturePage.tsx` | Delegated capture lifecycle and separated registration errors | SRP and lower coupling |
| `frontend/src/api.ts` | Centralized JSON requests and safe errors | DRY and consistent failure behavior |
| `frontend/src/features/capture/useCaptureSession.test.tsx` | Added direct hook tests | Protects the extracted boundary |
| Existing API/page/component tests | Continued to pass without API changes | Behavior-preservation evidence |

### Test and documentation support

The existing coverage-gated backend/frontend suites were updated where constructor seams changed. This report was added at `docs/CODE_REVIEW_REPORT.md`.

## Behavior-preservation evidence

- Public HTTP routes and response models are unchanged.
- Inspection states and transition semantics are unchanged.
- Upload validation, storage keys, media rows, job creation, analysis, and reporting behavior are unchanged.
- Frontend routes, labels, progress behavior, retry behavior, and API payloads are unchanged.
- Backend: **54 tests passed**, about **84% total coverage**.
- Frontend: **43 tests passed**, about **92% statements / 95% lines**.
- TypeScript production build passed.
- A clean Uvicorn process started successfully; `/health` and the database-backed
  `/inspections` endpoint both returned HTTP 200.

## Risks and assumptions

- `MobileAdapter` is an internal class and now requires a storage capability in its constructor. The public HTTP API is unaffected.
- `DroneAdapter` and `sync_storage.py` were removed because repository search found no runtime caller and both bypassed or violated current contracts.
- No database migration was required because persistence shape and business state values did not change.
- Capture-source values other than mobile remain readable for historical/imported data but cannot be uploaded through the current API.
- Analysis execution is still in-process; dependency injection makes a future worker easier but does not itself make execution distributed or safe under multiple replicas.
- The refactor does not claim the experimental detector is production-grade.

## Recommended next improvements

1. Move membership tables and RLS policies into PostgreSQL-tested Alembic migrations.
2. Add user identity, fleet membership roles, server-derived actor IDs, and audit events.
3. Implement leased worker execution with heartbeat, timeout, bounded retry, backoff, and dead-letter/manual retry.
4. Shorten analysis database transactions by detecting outside the write transaction and persisting results after lease revalidation.
5. Generate or runtime-validate all frontend DTOs from FastAPI OpenAPI; current TypeScript interfaces are compile-time assertions.
6. Split storage validation/providers only when a new provider or policy creates a second reason to change the module.
7. Extract the truck setup/registration panel when that feature next gains behavior or independent reuse.
8. Add PostgreSQL, Supabase storage, and multi-worker integration environments; unit coverage cannot prove those boundaries.
9. Add metrics, tracing, immutable audit history, backup/restore drills, and storage-retention operations.

Avoid a repository-wide “clean architecture” rewrite. The next changes should remain vertical, behavior-tested slices with measurable operational value.
