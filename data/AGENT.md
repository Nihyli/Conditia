# AI Agent Guide

## Project Purpose

Conditia is a system of record for the condition of physical fleet assets. Today, a driver or yard worker uses the mobile web capture flow to record a truck from several angles. The backend stores the media, analyzes it for damage, compares findings with earlier inspections, and produces structured inspection data for a fleet dashboard. The design is intended to remain independent of capture hardware so that mobile phones, drones, and fixed cameras can feed the same downstream workflow.

The current damage detector is a stub unless Google Cloud Vision is configured. PDF export, drone capture, authentication, and a production Supabase integration are not implemented yet; do not represent those features as complete.

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

The current implementation only partially enforces the intended layers. In particular, `routers/inspections.py` performs workflow orchestration and query assembly, services instantiate concrete global dependencies, and no repository layer exists. Future changes should improve these boundaries incrementally rather than rewriting the application at once.

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
- Keep the SQLAlchemy schema and `backend/db/schema.sql` equivalent. Every constraint, nullability rule, index, and uniqueness invariant must be represented and migrated deliberately in both environments until a single migration system replaces the dual definitions.
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
| `backend/db/` | Production DDL and, preferably, future migrations | Runtime business logic |
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
| `backend/adapters/mobile.py`, `backend/services/storage.py` | `capture_angle` and the client filename are concatenated into a path without sanitization or a containment check. | `..`, path separators, or absolute path behavior can write/read outside the storage root. | Generate server-owned filenames, allow-list angles/extensions, resolve the destination, and reject any path not contained by the storage root. | High |
| Upload endpoint and local storage | Uploads have no byte limit, file-count limit, MIME/signature validation, or streaming write; each file is read fully into memory. | Large or disguised uploads can exhaust memory/disk and public static media can serve unsafe content. | Enforce request/file limits, allow-list verified image/video formats, stream to a temporary file, atomically move after validation, and reject empty files. | High |
| `backend/routers/inspections.py`, `backend/services/analysis.py` | Every angle upload queues full inspection analysis and can set the inspection to `complete`. Jobs are not idempotent and findings are not replaced/deduplicated. | A six-angle capture can be marked complete early, analyzed repeatedly, race with later uploads, and create duplicate findings/reports. | Separate media upload from an explicit finalize action; enqueue one durable idempotent job; add lifecycle guards and unique/idempotency constraints. | High |
| Entire API and `/media` mount | There is no authentication, authorization, fleet scoping, or access control on media. `created_by` is trusted client text. | Any reachable client can read media and modify or enumerate fleet records; this blocks safe multi-tenant/production use. | Add authenticated principals, fleet ownership checks, server-derived actor IDs, and authorized/signed media delivery before deployment. | High |
| `backend/models/schemas.py`, router query/form parameters | Domain validation is minimal. Most IDs/statuses/sources/angles/VINs/years/GPS coordinates and `limit` are unrestricted strings/numbers. | Invalid states enter storage, negative/unbounded limits are accepted, and downstream code relies on unchecked values. | Introduce enums, UUID types, constrained strings/numbers, VIN normalization, bounded pagination, and cross-field validators. | High |
| Error handling in routers, vision, and analysis | Duplicate VIN/database errors are not translated or rolled back consistently. Vision/frame exceptions are broadly swallowed and detector failure becomes an empty detection set. | Clients receive inconsistent errors and a failed detector can generate a false “no findings” report. | Define typed application errors and one HTTP handler; log causes; distinguish `analysis_failed` from a valid clear inspection; preserve safe client messages. | High |
| Test suite | No backend or frontend test files, test scripts, fixtures, or CI configuration are present. | Core upload, lifecycle, change-detection, and security behavior can regress without detection. | Establish pytest/async database tests and Vitest/React Testing Library; add CI for tests, type checking, and builds. | High |
| Tracked runtime artifacts | `backend/conditia.db` and sample files under `backend/storage/` are committed, and `.gitignore` does not exclude them. | Real customer media or local data can be committed accidentally; binary changes add repository noise. | Add DB/storage patterns to `.gitignore`, retain explicit safe fixtures elsewhere, and remove tracked runtime artifacts in a deliberate cleanup change. | High |
| Async paths in storage, analysis, media sync, and vision | `Path.read_bytes/write_bytes`, OpenCV frame extraction, and the synchronous Google client run inside async functions. | Blocking I/O and CPU work can stall all FastAPI requests under load. | Stream with async I/O where useful; execute blocking adapters in a thread/process; use a job queue for analysis. | High |
| ORM models vs `backend/db/schema.sql` | SQLite/SQLAlchemy omits PostgreSQL checks and indexes; nullability/types differ; neither schema enforces one report per inspection or storage-key uniqueness. There is no migration system. | Local and production behavior will diverge, invalid states remain possible, and concurrent report creation can duplicate rows. | Adopt Alembic as the source of truth; align constraints and types; add uniqueness and indexes based on documented invariants. | High |
| `backend/routers/inspections.py` | The router owns adapter registration, upload orchestration, state changes, DB writes, disk recovery, summary assembly, and history calculations. | The 228-line transport module has several responsibilities and is difficult to unit test. | Extract an ingestion/finalization service and an inspection query service; leave HTTP translation in the router. | Medium |
| `backend/services/analysis.py` and other services | Services create `SessionLocal` and import global `storage_service`, detector, and report modules directly. | High-level workflows depend on concrete infrastructure and require a real database/filesystem for tests. | Inject repositories and `Storage`, `Detector`, and job interfaces; wire defaults in an application composition module. | Medium |
| Capture adapter contract | `receive_media` accepts an untyped `metadata: dict`, ignores it in the mobile adapter, and returns only strings. Adapter registration lives in a router; `manual`/`fixed_camera` are schema values without adapters. | Metadata and supported-source rules can drift, and core code reconstructs information the adapter should return. | Use typed metadata/result DTOs and a registry dependency; explicitly distinguish valid stored sources from currently ingestible sources. | Medium |
| `backend/services/media_sync.py`, `backend/sync_storage.py` | Recovery logic is duplicated, searches working-directory fallbacks, copies files synchronously, and a GET path can mutate storage/database when media rows are absent. It hardcodes source `mobile`. | Reads are surprising, duplicate implementations drift, and recovered metadata can be incorrect. | Make recovery an explicit admin/maintenance command using one shared service; never repair state during normal GET requests. | Medium |
| Inspection queries and change detection | Summary building queries truck/findings/media per inspection and history once per finding; change detection performs a query per prior inspection. | This is an N+1 pattern that grows rapidly with fleet history. | Use joins/select-in loading and batched queries; compute first-seen/history counts in repositories with bounded query counts. | Medium |
| Database lifecycle | Foreign keys have no explicit delete policy and SQLite foreign-key enforcement is not enabled explicitly. | Deletes or bad imports can leave orphaned media/findings/reports. | Define cascade/restrict behavior and enable/test foreign-key enforcement for SQLite. | Medium |
| Frontend `CapturePage.tsx` | One 396-line component owns truck loading/registration, inspection lifecycle, six-angle state, upload progress, and three page phases. | Independent behaviors are coupled and difficult to test or change safely. | Extract a capture-session hook/state reducer, a truck selector/registration component, and phase-specific components. | Medium |
| Frontend API boundary | `mapInspection.ts` casts arbitrary strings to unions and maps unknown finding types without validation. `api.ts` repeats response handling and exposes status-only errors. | Contract drift becomes invalid UI state and useful structured API errors are lost. | Parse runtime schemas or generated OpenAPI types; centralize request/error decoding; reject or explicitly map unknown enum values. | Medium |
| Configuration and documentation | Backend docs, UI help, production fallback, Vite proxy, and `start.ps1` disagree between ports 8000 and 8001. `.env.example` and backend README contain a developer-specific Windows path; app versions disagree. | Setup is unreliable and environment behavior is scattered. | Choose one documented development port, use `VITE_API_URL` for deployed builds, remove personal paths, and define app version once. | Medium |
| Reports and UI controls | Backend documentation describes `/inspections/{id}/report`, but implementation uses `/reports/{inspection_id}`. Export PDF, filter, navigation, notifications, and account controls render without implemented behavior. | The documented contract is inaccurate and controls imply functionality that does not exist. | Align endpoint docs/tests and disable, hide, or label placeholder controls until their behavior exists. | Low |
| `styles.css`, severity helpers | The stylesheet is 1,171 lines, while severity ranking/labels are repeated in Python and multiple frontend files. | Parallel edits are conflict-prone and semantic rules can drift. | Split styles by shell/dashboard/capture when actively modifying them; centralize frontend severity metadata and keep a contract test against backend values. | Low |

## Refactoring Recommendations

Apply these in order and keep each change independently reviewable:

1. Secure media ingestion: validated angles and types, generated filenames, path containment, streaming, quotas, and safe cleanup on failure.
2. Define the inspection state machine and change the flow to `create -> upload many -> finalize -> analyze once -> complete/failed`. Make analysis idempotent and concurrency-safe.
3. Add authentication, fleet authorization, and protected media delivery before exposing the service beyond trusted local development.
4. Add a backend test harness around the current behavior, then introduce typed errors and strict Pydantic validation without guessing client expectations.
5. Move upload/finalization and summary assembly from `routers/inspections.py` into application services. Inject storage/detector/repository interfaces at the composition root.
6. Adopt migrations, reconcile SQLAlchemy and PostgreSQL schemas, and add database constraints for state/source/type values and one report per inspection.
7. Move blocking analysis to a durable worker. Record job attempts and detector failures so retries cannot duplicate data or claim a false clear inspection.
8. Batch inspection/history queries and remove implicit media synchronization from GET requests. Consolidate recovery into an explicit maintenance command.
9. Decompose `CapturePage` around a tested capture-session reducer/hook, and validate frontend API payloads at runtime or generate types from OpenAPI.
10. Consolidate ports/version/configuration, correct endpoint documentation, remove tracked runtime data, and clearly label unfinished UI actions.

Do not combine all ten items into a single rewrite. Security and lifecycle correctness should land with characterization tests first; structural cleanup can then follow stable boundaries.

## Testing Recommendations

No automated tests currently exist. Add the following layers:

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
- The application currently has no authentication or authorization. Treat it as local-development-only until those controls and tenant isolation are implemented.
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
