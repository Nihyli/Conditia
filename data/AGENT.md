# AI Agent Guide

## Project Purpose

Conditia is a system of record for the condition of physical fleet assets. Today, a driver or yard worker uses the mobile web capture flow to record a truck from several angles. The backend stores the media, analyzes it for damage, compares findings with earlier inspections, and produces structured inspection data for a fleet dashboard. The design is intended to remain independent of capture hardware so that mobile phones, drones, and fixed cameras can feed the same downstream workflow.

The current damage detector is unavailable unless Google Cloud Vision is configured, and that integration is experimental triage that always requires human review. PDF export, drone capture, user-level authentication/roles, and a production worker are not implemented; do not represent those features as complete. Private Supabase media storage and fleet-scoped service API-key authentication are implemented, but they do not replace end-user identity and authorization.

## Architecture Overview

This is a small monorepo with two applications:

- `frontend/`: React 18, TypeScript, React Router, and Vite. It contains the fleet dashboard and guided mobile capture flow.
- `backend/`: Python, FastAPI, Pydantic, async SQLAlchemy, and SQLite by default. PostgreSQL/Supabase is the intended production database.

The intended backend flow is:

1. A FastAPI router validates and translates an HTTP request.
2. A capture adapter accepts source-specific media and metadata.
3. A storage adapter persists the raw media and returns an application-owned storage key.
4. The application records `InspectionMedia` rows.
5. An analysis workflow extracts frames, invokes damage detection, performs change detection, stores findings, generates a report, and changes inspection status.
6. Query services assemble API response models for the frontend.
7. The frontend API client maps snake-case API DTOs to UI domain types before components render them.

Important patterns already present and worth preserving:

- `CaptureAdapter` establishes a hardware boundary for capture sources.
- Pydantic schemas are separate from SQLAlchemy persistence models.
- The database session is request-scoped and async.
- Configuration is centralized in `backend/config.py` and defaults are anchored to `backend/paths.py`.
- Damage analysis does not branch on mobile versus drone input.
- Frontend API DTO mapping is isolated in `mapInspection.ts`.
- UI design tokens and severity semantics are centralized in `styles.css`.
- Change-over-time information is a first-class product concept, not a view-only calculation.

The current implementation only partially enforces the intended layers. `routers/inspections.py` still performs ingestion/finalization orchestration, services instantiate concrete global dependencies, and no repository layer exists. Inspection response assembly has moved into a query service. Future changes should improve these boundaries incrementally rather than rewriting the application at once.

## Important Design Rules

- Do not put business rules, workflow state transitions, filesystem recovery, or response aggregation in API routers. Routers should parse validated input, call an application service, and translate known errors to HTTP responses.
- Keep every capture source behind `CaptureAdapter` or its successor interface. A new source must not require source-specific branches in analysis, reporting, or dashboard code.
- Do not make core workflows depend on mobile, DJI, a local filesystem, Google Vision, SQLite, or Supabase directly. Pass an interface or dependency into the service when an implementation may change.
- Keep services focused on business workflows. Split media ingestion, inspection finalization, analysis, query assembly, and report generation when their state transitions can change independently.
- Keep SQL and persistence operations in repositories or narrowly scoped data-access functions. Do not return SQLAlchemy models across a boundary where a stable application DTO is appropriate.
- Treat inspection analysis as an idempotent, explicit lifecycle. Uploading one angle must not accidentally finalize a multi-angle inspection. Repeated jobs must not duplicate findings or reports.
- Validate all incoming identifiers and domain values before use. This includes UUIDs, VINs, years, statuses, severity, finding type, capture source, capture angle, GPS coordinates, list limits, filenames, MIME types, file signatures, and upload sizes.
- Treat filenames and storage keys as untrusted. Generate server-owned names, normalize paths, and prove that resolved paths stay below the configured storage root.
- Do not perform blocking filesystem, OpenCV, cloud SDK, or large CPU operations directly on the async event loop. Stream uploads and move blocking analysis to a thread or job worker.
- Do not swallow operational exceptions. Convert expected failures to typed application errors; log unexpected failures with context; record a safe failure state; never turn detector failure into a successful “no damage” result.
- Use explicit transactions for multi-step state changes. Roll back on database errors and define retry/idempotency behavior before adding automatic retries.
- Keep configuration environment-driven. Never commit credentials, local absolute paths, production URLs, ports repeated across files, or customer media/database snapshots.
- Preserve strict TypeScript. Validate server data at the boundary instead of using unchecked casts to make unknown values fit UI unions.
- Prefer small readable functions and cohesive modules. Extract code because it owns a concept or repeated policy, not merely to reduce line count.
- Add or update unit, API, adapter, and integration tests whenever behavior changes. A passing frontend build is not a substitute for tests.
- Treat Alembic as the schema source of truth. Every constraint, index, membership table, and PostgreSQL RLS policy must be delivered by a migration. `backend/db/schema.sql` is currently a deployment reference and must not evolve independently.
- Preserve API compatibility unless the task explicitly changes the contract. If behavior changes, update frontend DTOs, documentation, and contract tests together.

## Folder Responsibilities

| Folder/File | Should contain | Must not contain |
|---|---|---|
| `backend/routers/` | HTTP routing, dependency declarations, validated request/response DTOs, HTTP error translation | Business rules, raw filesystem access, source-specific workflow logic, large query assemblers |
| `backend/services/` | Use-case orchestration and domain policies such as ingestion, finalization, analysis, change detection, reporting, and read-model assembly | FastAPI request objects unless the service is explicitly an HTTP adapter; hidden global infrastructure dependencies |
| `backend/adapters/` | Implementations and interfaces for capture devices and external systems | Core inspection rules or branches that change generic analysis behavior |
| `backend/repositories/` (add when extracting data access) | Narrow SQLAlchemy queries and persistence operations behind application-facing interfaces | HTTP details, UI formatting, filesystem storage logic |
| `backend/models/db_models.py` | SQLAlchemy persistence models and database constraints | Request validation or workflow methods |
| `backend/models/schemas.py` | Pydantic API contracts and domain validation shared by the transport boundary | Database queries or side effects |
| `backend/migrations/` | Versioned schema, PostgreSQL policies, and compatibility migrations | Runtime business logic or hand-applied unversioned changes |
| `backend/db/` | Reference PostgreSQL/Supabase DDL while it remains in the repository | A second independently evolving schema authority |
| `backend/config.py`, `backend/paths.py` | Typed environment configuration and portable defaults | Developer-specific paths, credentials, or feature behavior |
| `frontend/src/pages/` | Page-level orchestration, routing concerns, and composition of smaller components/hooks | A full API client, repeated domain normalization, or several unrelated workflows in one component |
| `frontend/src/components/` | Reusable presentational and interaction components | Backend DTO assumptions or duplicated request logic |
| `frontend/src/components/capture/` | Camera/media-recorder UI and capture-specific presentation | Backend inspection lifecycle policy |
| `frontend/src/api.ts` | Transport calls, shared response/error decoding, and API DTOs | UI state and display formatting |
| `frontend/src/mapInspection.ts` | Runtime-checked conversion from API DTOs to UI types | Network calls or React state |
| `frontend/src/types.ts` | UI-facing domain types | Duplicate API wire contracts when generation or shared schemas become available |
| `frontend/src/styles.css` | Design tokens and component styles; split by feature when edits become conflict-prone | Behavior, data constants, or unexplained one-off values repeated across features |
| `data/` | Agent guidance and other non-runtime project documentation | Uploaded media, secrets, databases, or application source code |

## Current Code Quality Findings

| Area/File | Issue | Why it matters | Recommended fix | Priority |
|---|---|---|---|---|
| `backend/security.py`, frontend API client | Authentication is one shared fleet API key with no user identity, roles, or actor attribution; the browser needs an identity-aware gateway. | A leaked key grants fleet-wide mutation and cannot support least privilege or audit history. | Add OIDC/Supabase JWT verification, membership/role checks, server-derived actor IDs, and a frontend session flow. | High |
| Alembic vs `backend/db/schema.sql` | Memberships and PostgreSQL RLS exist only in reference SQL, not migrations. | `alembic upgrade head` can produce a database without documented tenant defense. | Deliver and test memberships/RLS through PostgreSQL Alembic migrations; make Alembic the only authority. | High |
| `backend/services/analysis_jobs.py` | API processes execute jobs and reclaim every running job at startup without leases. | Rolling multi-instance deployments can reclaim work that is still active and run duplicate analysis. | Use a dedicated worker with leases, heartbeat, timeout, backoff, maximum attempts, and dead-letter/manual retry. | High |
| `backend/services/vision.py` | Generic label detection and confidence-based provisional severity are experimental and always require review. | Results are not validated for safety, maintenance, insurance, or compliance decisions. | Define a reviewed taxonomy/severity model, localization, provenance, evaluation set, and human-review acceptance gates. | High |
| Tracked runtime artifacts | Ignore rules are fixed, but `backend/conditia.db` and eight media files remain tracked. | Data can remain in Git history and mutable binaries add privacy/review risk. | Remove after explicit ownership/privacy approval and replace needed data with documented synthetic fixtures. | High |
| Upload/request controls | Per-file and declared-body limits exist, but missing/chunked lengths, rate limits, tenant quotas, and total storage limits remain. | Authenticated abuse can consume parser space, bandwidth, storage, and worker capacity. | Enforce edge body/rate limits and application tenant/storage/concurrency quotas. | Medium |
| `backend/services/analysis.py` | A database transaction remains open during media, video, and cloud processing. | Long transactions hold connections/locks and increase contention and rollback cost. | Detect outside the transaction; use a short lease-check-and-persist transaction. | Medium |
| Inspection coverage | The backend finalizes after one media row while the six-angle UI allows every angle to be skipped. | Incomplete inspections can look structurally valid. | Define configurable server-side coverage templates and authorized override reasons. | Medium |
| Backend global dependencies | Analysis/jobs import `SessionLocal`, storage, detector, and report implementations directly. | Failure tests and alternate infrastructure require monkeypatching and broad changes. | Inject repository, unit-of-work, storage, detector, and job ports at a composition root. | Medium |
| Frontend `CapturePage.tsx`, API boundary, and tests | Capture remains a 433-line component; most responses use compile-time casts; only mapper tests exist. | UI workflows and contract failures can regress without component/E2E evidence. | Extract a reducer/hook and phase components; generate/validate API contracts; add component and E2E tests. | Medium |

## Refactoring Recommendations

Apply these in order and keep each change independently reviewable:

1. Add user identity, membership roles, actor attribution, and PostgreSQL RLS migrations.
2. Move analysis from API background tasks to a leased durable worker.
3. Define and enforce inspection coverage, model validation, severity, and human-review policy.
4. Shorten analysis transactions and formalize object-storage staging/reconciliation.
5. Enforce edge request/rate limits plus tenant storage and concurrency quotas.
6. Move upload/finalization from `routers/inspections.py` into injected command services.
7. Add PostgreSQL/RLS/Supabase and real concurrency integration tests.
8. Decompose `CapturePage` around a tested capture-session reducer/hook and generated/runtime-validated API client.
9. Add production metrics, audit events, backup/restore, retention, and deployment security controls.
10. Remove tracked runtime data after explicit privacy/ownership approval.

Do not combine all ten items into a single rewrite. Security and lifecycle correctness should land with characterization tests first; structural cleanup can then follow stable boundaries.

## Testing Recommendations

Automated backend API/service/storage tests, frontend mapper tests, and CI now exist. Extend them with the following layers:

- **Adapter tests:** verify each capture adapter returns normalized, server-owned storage keys; rejects traversal, invalid metadata, unsupported types, empty/oversized files; and preserves source-specific metadata. Run a shared contract suite against local storage and every future storage implementation.
- **API route tests:** cover success, validation failures, not-found behavior, duplicate VIN, authorization/fleet isolation, bounded pagination, source availability, finalize conflicts, and stable safe error bodies. Use a temporary database and storage directory.
- **Service/business rule tests:** exercise every valid/invalid inspection state transition, finalize-once behavior, retry idempotency, duplicate job delivery, report uniqueness, severity normalization, and first-occurrence calculations across ordered truck histories.
- **Upload/media handling tests:** test multiple files/angles, sanitized names, MIME-extension mismatches, signature validation, interrupted uploads, disk-full/write failures, cleanup, storage containment, static-media authorization, and concurrent uploads/finalization.
- **Error handling tests:** force detector, OpenCV, storage, and database failures; assert `failed` state, rollback, logged context, retry policy, and that no failure produces a successful clear report.
- **Repository/integration tests:** verify query counts or bounded query behavior for inspection lists, SQLite foreign keys, schema constraints, migrations on PostgreSQL, and transaction concurrency around reports/findings.
- **Frontend unit/component tests:** cover DTO parsing, severity/zone fallbacks, time formatting, dashboard polling cleanup, capture reducer transitions, camera denial, upload retry/skip behavior, and active media selection.
- **End-to-end tests:** run create truck -> create inspection -> upload several angles -> finalize -> analyze -> dashboard/report, using a deterministic fake detector and storage adapter.
- **Contract tests:** generate or compare frontend DTOs with FastAPI OpenAPI and test every capture adapter against one interface contract.

Minimum continuous verification should run Python lint/type checks, backend tests, frontend unit tests, `tsc`, and the Vite production build. Add security-focused regression cases before changing the upload endpoint.

## Security Notes

- Uploaded filenames, extensions, MIME types, capture angles, source names, and metadata are attacker-controlled. Never concatenate them into filesystem paths or trust them to describe content.
- Resolve every storage destination against a configured root and verify containment. Prefer opaque generated object keys and retain the original display name only as sanitized metadata if it is needed.
- Stream uploads with hard per-file, per-request, and per-inspection limits. Restrict file count, verify signatures/codecs, reject active content, and handle partial writes atomically.
- Do not expose the storage directory through an unrestricted static mount in production. Authorize access by fleet and inspection, or issue short-lived signed URLs with safe content headers.
- GPS coordinates, drone flight IDs, VINs, actor IDs, and inspection timestamps affect audit evidence. Validate them and distinguish client-asserted metadata from server/device-attested data.
- The application has fleet-scoped service API-key authentication, not user identity or roles. Keep it behind a trusted gateway until user authorization and migration-installed RLS are implemented.
- Database URLs, Supabase keys, service-account files, and deployed API origins belong in secrets/configuration. Do not log full database URLs because they may contain credentials.
- Exclude local databases and uploaded media from version control. Use synthetic, documented fixtures with no personal, customer, vehicle, or location data.
- Enable database constraints and foreign keys as defense in depth; API validation alone does not protect maintenance scripts or concurrent writers.
- Return safe client errors while logging correlation IDs and technical context server-side. Do not expose filesystem locations, SQL details, credentials, or cloud SDK messages.

## AI Agent Instructions

1. Before editing, identify whether the change belongs to transport, application workflow, domain policy, persistence, external adapter, or UI. State the boundary in the change summary.
2. Read the relevant Pydantic schema, SQLAlchemy model, production DDL, API DTO, and tests before changing a cross-stack field.
3. Do not bypass `CaptureAdapter` or storage/detector abstractions. Improve an inadequate interface explicitly instead of importing a concrete device into core logic.
4. Do not introduce source-specific branches in generic analysis, change detection, reporting, or dashboard workflows.
5. Do not add dependencies without explaining the concrete need, operational cost, and why existing platform features are insufficient.
6. Do not rename or reshape public interfaces unless all callers, OpenAPI/DTO types, tests, and documentation are updated in the same change.
7. Do not change API behavior, status transitions, severity semantics, or database constraints without adding/updating tests and documentation.
8. Keep changes small and easy to review. Separate behavior changes, migrations, cleanup, and formatting when practical.
9. Preserve async correctness. Identify every potentially blocking call and put it behind an appropriate async implementation, thread/process boundary, or worker.
10. When adding a capture source, implement and contract-test the capture adapter, register it at the composition root, and leave core analysis unchanged.
11. When changing persistence, provide a migration and verify both SQLite development and PostgreSQL production expectations. Do not edit only `schema.sql` or only ORM models.
12. When handling uploads, assume hostile names, bytes, metadata, sizes, ordering, disconnects, retries, and concurrent requests.
13. Prefer typed domain values and result objects over unstructured dictionaries and strings.
14. Preserve user changes already present in the worktree. Do not delete local databases/media or run destructive migration commands without explicit authorization.
15. Run the narrowest relevant tests while iterating, then the full backend test suite and frontend build before handoff. Report commands and failures accurately.
16. If no test exists for modified behavior, add one before or with the implementation. Do not use manual testing as the only evidence for lifecycle/security changes.

## Do Not Do

- Do not put drone-, phone-, or fixed-camera-specific logic inside generic inspection, analysis, change-detection, or reporting services.
- Do not mix HTTP parsing, validation, storage writes, database transactions, and business state transitions in one function.
- Do not trigger full analysis once per uploaded angle or mark a multi-angle inspection complete before explicit finalization.
- Do not make a background job non-idempotent or assume it will run exactly once.
- Do not trust uploaded filenames, extensions, MIME types, paths, capture source names, angles, GPS values, VINs, statuses, or client actor IDs.
- Do not use raw client strings as filesystem/object-storage keys.
- Do not hardcode local paths, hostnames, ports, credentials, or environment-specific URLs.
- Do not perform large synchronous file/cloud/CPU operations on the FastAPI event loop.
- Do not catch `Exception` and silently convert infrastructure failure into a valid empty result.
- Do not repair storage or mutate the database as a side effect of a normal GET request.
- Do not duplicate workflow or media-recovery logic across mobile, drone, fixed-camera, scripts, and routes.
- Do not create giant `utils`, `helpers`, service, page, or stylesheet files that collect unrelated responsibilities.
- Do not cast unvalidated API strings into TypeScript unions merely to satisfy the compiler.
- Do not let local and production database schemas evolve independently.
- Do not commit `.env` files, credentials, SQLite runtime databases, or captured fleet media.
- Do not present placeholder controls or integrations as working production features.
- Do not perform a broad architecture rewrite without characterization tests and a staged migration plan.
