# Conditia Production-Readiness Code Review

**Review date:** 2026-06-20  
**Repository reviewed:** entire current worktree, including tracked runtime artifacts and uncommitted frontend configuration changes  
**Actual stack:** FastAPI, Pydantic, async SQLAlchemy, SQLite/PostgreSQL, React, TypeScript, and Vite

## Executive summary

Conditia is a functional local-development prototype, not a production-ready system. The frontend compiles successfully and the code already has some useful boundaries: Pydantic DTOs are separate from SQLAlchemy models, capture devices have an adapter interface, TypeScript strict mode is enabled, and database access generally uses parameterized SQLAlchemy or SQLite calls. No hardcoded API key, password, bearer token, or private key was found in the current text files, and no direct SQL-injection sink was found.

Those positives are outweighed by several release blockers:

- The entire API and all uploaded media are unauthenticated and unscoped; there is no fleet/tenant authorization.
- Destructive seed/reset endpoints are enabled by default and can erase the database and uploaded files.
- User-controlled upload path components permit path traversal and arbitrary file overwrite within the service account's filesystem permissions.
- Uploads are unbounded, unverified, loaded fully into memory, and served back from a public static mount.
- Every angle upload launches a non-idempotent full analysis job, so normal six-angle use races, completes too early, and can duplicate findings/reports.
- Detector errors are silently converted to “no findings,” while the default detector is a stub. The system can therefore produce a successful clear report without performing a valid damage analysis.
- The intended PostgreSQL/Supabase schema lacks RLS and differs materially from the SQLAlchemy schema. There is no migration system.
- The pinned backend HTTP/upload stack has known vulnerabilities. No automated test suite or CI exists.

**Recommendation:** do not expose this application to untrusted users, customer data, or the public internet until the Critical and High findings are resolved and covered by automated tests.

## Scope and verification performed

- Reviewed all Python, SQL, TypeScript/TSX, HTML, configuration, dependency, PowerShell, documentation, and ignore files.
- Inspected the tracked SQLite schema/data counts and all tracked media file types. The repository contains one truck record, three inspections, eight media rows, three reports, a 56 KB SQLite database, and approximately 688 KB of captured images.
- Searched for common secret/key/token/password patterns. No credential value was found; placeholder configuration keys were found as expected.
- Confirmed ORM and maintenance SQL use SQLAlchemy expressions or bound SQLite parameters; no string-built SQL query was found.
- Ran `npm run build`: passed (TypeScript checks and Vite production build).
- Ran `python -m compileall -q backend`: passed with a `SyntaxWarning` in `backend/sync_storage.py:7` for an invalid escape sequence in the module docstring.
- Attempted to import the backend: blocked by the local environment lacking `aiosqlite`; this is an environment/setup limitation, not evidence that the application fails when requirements are installed.
- Ran `pip-audit -r backend/requirements.txt`: reported 15 advisory entries affecting `python-multipart==0.0.17` and transitive `starlette==0.41.3` (one Starlette advisory was duplicated in tool output).
- Ran `npm audit`: reported one High Vite issue and one Moderate esbuild issue in development dependencies. `npm audit --omit=dev` reported zero production dependency vulnerabilities.
- Searched for test/spec/fixture and CI files: no application tests or CI workflow were found.

## Technology note: Spring Boot / Java criteria

There is no Java or Spring Boot code in this repository. The requested Spring concerns were evaluated against their FastAPI equivalents: routers as controllers, application services, repositories/data access, Pydantic validation, exception handlers, configuration, logging, transaction boundaries, dependency injection, and package structure. A Java/Spring rewrite is neither required nor recommended merely to address these findings.

## Detailed findings

### SEC-01 — No authentication, authorization, or tenant isolation

- **File/location:** `backend/main.py:43-53`; all files under `backend/routers/`; `backend/models/db_models.py:29-61`
- **Severity:** Critical
- **Category:** Security
- **Problem:** Every read and write endpoint is public. `/media` exposes captured fleet media without authorization. API queries return global records, and the data model does not consistently require or enforce fleet ownership. `created_by` is accepted directly from the client rather than derived from an authenticated principal.
- **Why it matters:** Any network client can enumerate VINs, inspections, findings, reports, and media; register trucks; create inspections; upload files; and alter global state. In a multi-tenant system, this is a complete confidentiality and integrity failure (BOLA/IDOR).
- **Recommended fix:** Add an identity provider-backed authentication dependency, derive actor identity server-side, make fleet ownership mandatory, and apply fleet predicates in every repository query. Protect media with an authorized endpoint or short-lived signed URLs. Add negative authorization tests for every resource type.
- **Example improved code:**

```python
@router.get("/{inspection_id}", response_model=InspectionSummary)
async def get_inspection(
    inspection_id: UUID,
    principal: Principal = Depends(require_principal),
    service: InspectionQueryService = Depends(get_inspection_query_service),
):
    return await service.get_for_fleet(inspection_id, principal.fleet_id)
```

### SEC-02 — Unauthenticated destructive administration is enabled by default

- **File/location:** `backend/config.py:21-22`; `backend/routers/admin.py:10-43`; `backend/seed.py:175-206,217-250`
- **Severity:** Critical
- **Category:** Security
- **Problem:** `admin_enabled` defaults to `True`. The “authorization” check only tests that feature flag. Anyone can call `/admin/unseed` or `/admin/seed?force=true`; both can delete every fleet row and uploaded media file.
- **Why it matters:** A single unauthenticated HTTP request can cause total, irreversible data loss. A frontend confirmation dialog does not protect the API.
- **Recommended fix:** Remove destructive administration from the public runtime API. Prefer an authenticated, separately deployed maintenance command. If an endpoint is unavoidable, default it off, require a privileged role plus recent re-authentication, use CSRF protection for cookie sessions, require an auditable confirmation token, and back up before deletion.

### SEC-03 — Upload path traversal permits arbitrary file overwrite

- **File/location:** `backend/adapters/mobile.py:25-30`; `backend/services/storage.py:19-36`; input entry point `backend/routers/inspections.py:169-198`
- **Severity:** Critical
- **Category:** Security
- **Problem:** `capture_angle` and `UploadFile.filename` are concatenated into a storage path. `LocalStorageService` joins that string to the storage root without normalization or a containment check. Values containing `..` and path separators can escape `backend/storage`.
- **Why it matters:** An unauthenticated attacker can overwrite the SQLite database, source/configuration files, or other service-account-writable files. In development with `uvicorn --reload`, source overwrite may become code execution; in production it is at least arbitrary write and denial of service.
- **Recommended fix:** Allow-list capture angles, ignore client filenames for storage keys, generate opaque server-owned filenames, resolve the destination, and prove it remains below the storage root. Write atomically with non-overwrite semantics.
- **Example improved code:**

```python
ALLOWED_ANGLES = {"front", "rear", "driver_side", "passenger_side", "top", "undercarriage"}

def safe_destination(root: Path, inspection_id: UUID, angle: str, suffix: str) -> Path:
    if angle not in ALLOWED_ANGLES or suffix not in {".jpg", ".png", ".mp4", ".webm"}:
        raise InvalidMedia("Unsupported angle or type")
    destination = (root / str(inspection_id) / angle / f"{uuid4()}{suffix}").resolve()
    if not destination.is_relative_to(root.resolve()):
        raise InvalidMedia("Invalid storage key")
    return destination
```

### SEC-04 — Uploads are unbounded, unverified, non-streaming, and publicly served

- **File/location:** `backend/routers/inspections.py:169-218`; `backend/services/storage.py:19-24`; `backend/main.py:43-46`
- **Severity:** High
- **Category:** Security
- **Problem:** There is no request-size, per-file, file-count, per-inspection, rate, or disk quota. File type is inferred from the filename extension, no MIME/signature/codec validation occurs, empty and active-content files are accepted, and each upload is read fully into memory. Everything under the storage directory is served from `/media` with no authorization or explicit safe content headers.
- **Why it matters:** Attackers can exhaust RAM/disk, overwrite same-name media, upload disguised/active content, and distribute it from the application origin. Large concurrent uploads can take down the API process.
- **Recommended fix:** Enforce gateway and application limits; stream into a quota-controlled temporary file; verify magic bytes and decode with hardened image/video tooling; reject unsupported, empty, or oversized files; generate storage keys; atomically move on success; delete partial files; scan if the threat model requires it; and serve only through authorized/signed delivery with `nosniff` and safe disposition headers.

### SEC-05 — Backend request/upload dependencies have known vulnerabilities

- **File/location:** `backend/requirements.txt:2-12`
- **Severity:** High
- **Category:** Security
- **Problem:** On 2026-06-20, `pip-audit` reported seven advisory entries for `python-multipart==0.0.17` (including CVE-2024-53981 and 2026 upload/parser CVEs) and eight entries for transitive `starlette==0.41.3` (one duplicated by the tool), including CVE-2025-54121, CVE-2025-62727, and 2026 advisories. The fixed versions shown by the audit require upgrading `python-multipart` and likely FastAPI/Starlette together.
- **Why it matters:** These packages sit directly on the untrusted HTTP and multipart upload boundary, which is already the application's highest-risk area.
- **Recommended fix:** Upgrade FastAPI, Starlette, and python-multipart to mutually compatible supported versions, regenerate a locked dependency set with hashes, and rerun API/upload regression tests and `pip-audit`. Do not blindly force a transitive Starlette version outside FastAPI's compatibility range.

### SEC-06 — LAN-exposed Vite development server uses vulnerable versions

- **File/location:** `frontend/package.json:16-21`; `frontend/package-lock.json`; `frontend/vite.config.ts:6-14`
- **Severity:** High
- **Category:** Security
- **Problem:** The installed tree contains `vite@5.4.21` and `esbuild@0.21.5`. `npm audit` reports a High Vite advisory group (path traversal/deny bypass and Windows credential disclosure issues) and a Moderate esbuild development-server advisory. `server.host: true` exposes the dev server to the LAN.
- **Why it matters:** The vulnerable functionality is development-only, but host-wide binding increases its reach to other devices on the network. Running Vite as a production server would be unsafe. Runtime frontend dependencies themselves audited clean with `--omit=dev`.
- **Recommended fix:** Upgrade Vite/plugin-react/esbuild through a tested supported release, bind development to loopback unless LAN access is explicitly needed, and deploy only static build artifacts behind a production web server.

### SEC-07 — Database credentials and internal paths can be logged or returned

- **File/location:** `backend/main.py:15-18,56-65`
- **Severity:** High
- **Category:** Security
- **Problem:** Startup prints the complete `settings.database_url`, which will include username/password for PostgreSQL. `/health` returns the configured absolute storage directory. Plain `print` statements provide no structured redaction or log levels.
- **Why it matters:** Credentials can be copied into container/platform logs accessible to broader operational roles, while filesystem layout disclosure helps attackers and leaks environment details.
- **Recommended fix:** Log only database dialect/host after redaction, never the password or full DSN. Remove `storage_dir` from the public health response. Use structured logging, correlation IDs, explicit levels, and a central redaction policy.

### SEC-08 — Runtime database and captured media are committed to Git

- **File/location:** `backend/conditia.db`; `backend/storage/**`; missing exclusions in `.gitignore:1-32`
- **Severity:** High
- **Category:** Security
- **Problem:** A mutable SQLite database and eight captured images are tracked. `.gitignore` excludes secrets and build artifacts but not `*.db` or `backend/storage/`.
- **Why it matters:** Real VINs, locations, timestamps, findings, actor identifiers, and customer imagery can be committed accidentally and remain recoverable in Git history. Mutable binaries also make review and merges unreliable.
- **Recommended fix:** Add runtime database/storage exclusions, move synthetic fixtures into an explicit test-fixtures directory, remove tracked runtime artifacts in a reviewed cleanup commit, and perform a history/secrets/privacy review before release. Do not rewrite shared history without coordination.

### SEC-09 — Intended Supabase schema has no RLS or ownership enforcement

- **File/location:** `backend/db/schema.sql:6-93`
- **Severity:** High
- **Category:** Security
- **Problem:** The production schema creates public fleet tables without Row Level Security policies. Several ownership FKs are nullable, and child tables do not carry a tenant key. No database-level tenant isolation exists.
- **Why it matters:** If these tables are exposed through Supabase APIs or a compromised/misconfigured service path, data can cross fleet boundaries. Application-only filtering is easy to omit and provides weak defense in depth.
- **Recommended fix:** Enable RLS on every exposed table, define authenticated fleet membership/role policies, make ownership links non-null, propagate/index tenant identifiers where appropriate, restrict service-role credentials to backend use, and test policies with two tenants.

### SEC-10 — Input validation is insufficient for identifiers and domain values

- **File/location:** `backend/models/schemas.py:8-33`; `backend/routers/inspections.py:118-121,169-179`; `backend/routers/findings.py:12-20`
- **Severity:** High
- **Category:** Security
- **Problem:** IDs, VINs, capture sources, capture angles, severities, and actor IDs are arbitrary strings. Years, GPS values, confidence, and list limits are unconstrained. `created_by` is client-asserted. `list_inspections(limit=...)` permits negative or extremely large limits. The ORM repeats these values as unconstrained strings.
- **Why it matters:** Invalid states enter persistence, malformed values reach filesystem logic, unbounded queries enable resource exhaustion, and audit evidence can be forged.
- **Recommended fix:** Use UUID types, enums/Literals, bounded `Query`, constrained fields, VIN normalization/checking, GPS ranges, confidence `0..1`, server-derived actor identity, and database checks. Validate source-specific metadata cross-fields.
- **Example improved code:**

```python
class InspectionCreate(BaseModel):
    truck_id: UUID
    capture_source: Literal["mobile"] = "mobile"

class UploadMetadata(BaseModel):
    capture_angle: CaptureAngle
    gps_lat: float | None = Field(None, ge=-90, le=90)
    gps_lng: float | None = Field(None, ge=-180, le=180)

@router.get("")
async def list_inspections(limit: int = Query(25, ge=1, le=100)):
    ...
```

### OPS-01 — No production security headers, rate limiting, or safe API surface policy

- **File/location:** `backend/main.py:28-53`; `frontend/index.html:3-14`
- **Severity:** Medium
- **Category:** Security
- **Problem:** Swagger/OpenAPI is always enabled, no rate limiting is present, and the application defines no HSTS, CSP, frame, referrer, or content-sniffing policy. External Google Fonts are loaded at runtime. CORS permits credentials plus all methods/headers for configured origins.
- **Why it matters:** These omissions increase enumeration, brute-force/resource-abuse, clickjacking, content-sniffing, and third-party privacy exposure. Some controls belong at the reverse proxy, but the deployment contract does not specify them.
- **Recommended fix:** Define an edge security baseline: TLS/HSTS, request and upload rate limits, CSP, `X-Content-Type-Options: nosniff`, frame restrictions, referrer policy, narrowly scoped CORS, production docs policy, and locally hosted fonts if privacy requirements demand it.

### BR-01 — Each uploaded angle launches full non-idempotent analysis

- **File/location:** `backend/routers/inspections.py:195-227`; `backend/services/analysis.py:52-108`; frontend normal flow `frontend/src/pages/CapturePage.tsx:121-155`
- **Severity:** High
- **Category:** Business Rule
- **Problem:** Every successful upload schedules `analyze_inspection`. The six-angle frontend therefore starts up to six overlapping full jobs. Jobs re-read all media, append findings without replacing/deduplicating, upsert reports without a uniqueness constraint, and independently set the inspection to `complete`.
- **Why it matters:** An inspection may show complete after the first angle while later uploads are pending. Concurrent jobs can duplicate findings, race report generation, or overwrite status. Retried requests and process restarts make results nondeterministic.
- **Recommended fix:** Implement an explicit state machine: `created -> uploading -> submitted -> processing -> complete|failed`. Upload media without analysis, provide one finalize/submit operation, enqueue one durable idempotent job, lock/claim the inspection, use a job/idempotency key, and replace/upsert findings transactionally.

### BR-02 — Detector failure and disabled detection produce false “clear” reports

- **File/location:** `backend/services/vision.py:48-82`; `backend/services/analysis.py:71-104`; `backend/services/report_generator.py:19-29`; `backend/README.md:86-87`
- **Severity:** High
- **Category:** Business Rule
- **Problem:** Detection returns `[]` when Google Vision is not configured and catches every exception to return `[]`. Report generation interprets zero findings as “No findings detected” and analysis marks the inspection complete. Frame extraction similarly catches every exception and may pass a video path as though it were an image.
- **Why it matters:** A missing credential, corrupt file, cloud outage, unsupported video, or detector exception becomes a successful safety result. For physical-asset evidence, that is materially misleading and could affect maintenance/liability decisions.
- **Recommended fix:** Model `not_configured`, `unsupported`, `failed`, and `valid_no_findings` as distinct outcomes. Fail or require manual review when analysis is unavailable. Record detector/model version, input coverage, attempt details, and safe diagnostic codes. Never claim “clear” unless a supported detector successfully analyzed required coverage.

### BR-03 — Change detection can conflate unrelated damage

- **File/location:** `backend/services/change_detection.py:15-47`; `backend/services/vision.py:67-77`
- **Severity:** High
- **Category:** Business Rule
- **Problem:** Historical matching uses only `(finding_type, zone)`. Google Vision detections never set `zone`, location, or a bounding box, so every dent (for example) with `zone=None` on the same truck can be treated as the same defect. The query also considers every other inspection rather than explicitly limiting to earlier successful inspections.
- **Why it matters:** The product's central claim—when damage first appeared—can be wrong. Incorrect first-seen attribution undermines auditability and responsibility decisions.
- **Recommended fix:** Define a tested damage identity/signature using normalized component/zone, geometry or embedding similarity, side/angle, and temporal rules. Compare only prior completed inspections with valid coverage. Preserve uncertainty and require review below a matching threshold.

### TX-01 — Multi-resource operations lack atomicity, rollback, and durable execution

- **File/location:** `backend/services/storage.py:19-29`; `backend/routers/inspections.py:195-221`; `backend/services/analysis.py:60-108`; `backend/services/report_generator.py:50-65`
- **Severity:** High
- **Category:** Spring Boot
- **Problem:** Files are written before database commit with no compensation. Analysis commits status, then findings, then report, then completion across separate transactions. On error it does not explicitly roll back before trying to write `failed`. FastAPI in-process background tasks are not durable across crashes/deployments.
- **Why it matters:** Database failure leaves orphaned media; report failure leaves committed findings and processing status; a failed transaction can prevent the failure status commit; process loss drops jobs. Results cannot be safely retried.
- **Recommended fix:** Define transaction boundaries around each use case, roll back on exceptions, use an outbox/job table for durable dispatch, make worker operations idempotent, and implement storage compensation/garbage collection. One report and one active analysis generation per inspection should be enforced by the database.

### DB-01 — SQLAlchemy and PostgreSQL schemas diverge; no migration system exists

- **File/location:** `backend/models/db_models.py:29-118`; `backend/db/schema.sql:6-93`; `backend/database.py:30-36`
- **Severity:** High
- **Category:** Spring Boot
- **Problem:** Runtime startup uses `create_all`, while documentation calls `schema.sql` canonical. PostgreSQL uses UUIDs, checks, and indexes not represented by ORM metadata; ORM uses `String` IDs and omits checks/indexes. Nullability differs. Neither schema enforces one report per inspection or unique storage paths. Foreign-key delete policies are unspecified, and SQLite foreign keys are not explicitly enabled. No migration history exists.
- **Why it matters:** Local tests and production behave differently; deployments cannot be upgraded reproducibly; invalid/duplicate states survive; and model-vs-UUID binding can fail against the manually created PostgreSQL schema.
- **Recommended fix:** Adopt Alembic as the single schema history, use portable UUID types, align nullability/checks/indexes, add `UNIQUE(reports.inspection_id)` and appropriate media/idempotency constraints, define cascade/restrict policies, enable SQLite FK checks in tests, and verify migrations against PostgreSQL.

### ERR-01 — Error handling is inconsistent and operational failures are hidden

- **File/location:** `backend/routers/trucks.py:12-18`; `backend/routers/inspections.py:195-200`; `backend/services/analysis.py:105-108`; `backend/services/vision.py:80-82`; `backend/main.py:13-24`
- **Severity:** Medium
- **Category:** Spring Boot
- **Problem:** Duplicate VIN and database/storage errors are not translated into stable API errors or explicitly rolled back. Broad `except Exception` blocks either suppress the cause or re-raise without structured contextual logging. There is no global exception strategy or request correlation.
- **Why it matters:** Clients receive inconsistent 500 responses, sessions can remain in failed transaction state, security-relevant details may be logged unpredictably, and operators cannot distinguish expected validation conflicts from infrastructure failures.
- **Recommended fix:** Define typed application exceptions, one safe HTTP exception mapping layer, explicit rollback behavior, structured contextual logs, correlation IDs, and monitoring alerts. Keep technical causes out of client responses.

### ARC-01 — Inspection router violates controller/service separation and SRP

- **File/location:** `backend/routers/inspections.py:32-228`
- **Severity:** Medium
- **Category:** SOLID
- **Problem:** One router owns adapter registration, response aggregation, N+1 history calculations, disk recovery, validation, filesystem ingestion, ORM writes, state transitions, and background dispatch.
- **Why it matters:** HTTP concerns are coupled to business workflow and infrastructure. The module is difficult to unit test, and small changes risk unrelated behavior.
- **Recommended fix:** Keep routes limited to validated transport and error translation. Extract `InspectionCommandService` (create/upload/finalize), `InspectionQueryService` (summary/read models), and narrow repositories. Wire adapters at a composition root.

### ARC-02 — High-level services depend directly on concrete global infrastructure

- **File/location:** `backend/services/analysis.py:12-16,55`; `backend/services/vision.py:11,60-65`; `backend/adapters/mobile.py:3-4`; `backend/services/storage.py:42`
- **Severity:** Medium
- **Category:** SOLID
- **Problem:** Services import `SessionLocal`, global `storage_service`, global settings, detector functions, and report modules directly. Dependencies cannot be substituted without monkeypatching module globals.
- **Why it matters:** This violates Dependency Inversion, makes deterministic tests difficult, and ties core workflows to SQLAlchemy, local disk, and Google Vision.
- **Recommended fix:** Define ports/protocols for repositories, storage, detector, report writer, clock, and job dispatcher. Inject implementations through FastAPI dependencies/application composition. Pass a unit-of-work into the analysis service.

### ARC-03 — Capture adapter contract is not safely substitutable or closed for extension

- **File/location:** `backend/adapters/base.py:14-33`; `backend/adapters/drone.py:20-27`; `backend/routers/inspections.py:32-36,185-200`
- **Severity:** Medium
- **Category:** SOLID
- **Problem:** The interface accepts an untyped `metadata: dict` and returns only strings. `DroneAdapter` is registered as supported but throws for every call, violating the behavior implied by the base contract. Adding a source requires editing the router registry despite comments claiming no other file changes. Schema values include `fixed_camera` and `manual`, but no adapters exist.
- **Why it matters:** Liskov substitution fails at runtime, source capabilities drift across schema/router/UI, and callers reconstruct metadata the adapter should return.
- **Recommended fix:** Use typed source-specific request/result DTOs, capability/status metadata, and a registry injected at application startup. Do not register unavailable adapters as operational. Separate “valid persisted source” from “currently ingestible source.”

### PERF-01 — Inspection reads and change detection contain N+1 query patterns

- **File/location:** `backend/routers/inspections.py:48-95,118-124`; `backend/services/inspection_history.py:26-41`; `backend/services/change_detection.py:26-45`
- **Severity:** Medium
- **Category:** Code Smell
- **Problem:** Each listed inspection queries truck, findings, and media; each finding then reloads the truck's ordered inspection IDs. Change detection queries once per prior inspection. `list_trucks`, `list_findings`, and `list_reports` have no pagination.
- **Why it matters:** Query count grows with inspections × findings × history and can exhaust database connections/latency as fleet history grows. Unbounded collection endpoints create memory and denial-of-service risk.
- **Recommended fix:** Build read models with joins/select-in loading and aggregate history in one bounded query. Add cursor pagination and database indexes verified by query plans. Include query-count/performance tests.

### DATA-01 — Normal GET requests mutate the database/filesystem and recovery logic is duplicated

- **File/location:** `backend/routers/inspections.py:48-68`; `backend/services/media_sync.py:19-129`; `backend/sync_storage.py:25-162`
- **Severity:** Medium
- **Category:** Code Smell
- **Problem:** If no media rows exist, a GET summary scans several working-directory-dependent storage roots, copies files synchronously, inserts rows, and commits. Similar logic is duplicated in a standalone SQLite script. Recovery hardcodes capture source `mobile` and cannot recover GPS/flight metadata reliably.
- **Why it matters:** Reads are surprising and non-idempotent under concurrency, blocking I/O runs in the request loop, duplicate implementations drift, and reconstructed evidence can be inaccurate.
- **Recommended fix:** Consolidate recovery into one explicit authenticated maintenance command/service. Make GETs side-effect free. Store authoritative metadata at ingestion and flag irrecoverable metadata instead of inventing it.

### ASYNC-01 — Blocking I/O and CPU/cloud operations run on the async event loop

- **File/location:** `backend/services/storage.py:19-36`; `backend/services/media_sync.py:85-90`; `backend/services/analysis.py:19-49`; `backend/services/vision.py:62-65`; `backend/seed.py:168-181`
- **Severity:** High
- **Category:** Spring Boot
- **Problem:** `Path.read_bytes/write_bytes`, directory traversal/copying, OpenCV decode/frame extraction, and synchronous Google Cloud calls run inside async request/background functions.
- **Why it matters:** A single large file or slow cloud call can block all requests served by that event loop, causing timeouts and poor availability.
- **Recommended fix:** Stream uploads, move blocking filesystem/cloud calls to controlled threads where appropriate, and put CPU-heavy/video analysis in a bounded worker process/job system with timeouts and backpressure.

### BR-04 — “Open findings” and completion semantics are not modeled

- **File/location:** `backend/routers/fleet.py:52-61`; `backend/models/db_models.py:81-103`; `frontend/src/mapInspection.ts:101-109`
- **Severity:** Medium
- **Category:** Business Rule
- **Problem:** `open_findings` counts every historical finding because findings have no lifecycle/resolution state. The UI presents this as an actionable open count. Similarly, inspections can be complete without required angle coverage or a successful detector.
- **Why it matters:** Dashboard metrics and workflow status do not represent the business meaning users infer from their labels.
- **Recommended fix:** Define finding status (`open`, `acknowledged`, `resolved`, `false_positive`) and resolution audit fields. Define required/optional coverage and completion gates. Calculate metrics from explicit domain state, not row counts.

### BR-05 — Severity is derived from generic label confidence, not damage impact

- **File/location:** `backend/services/vision.py:40-45,65-77`
- **Severity:** High
- **Category:** Business Rule
- **Problem:** Google label confidence thresholds are mapped directly to physical damage severity. Confidence that an image contains a label is not a measure of structural/safety impact. Generic label detection also does not localize damage adequately.
- **Why it matters:** A highly confident benign label may be classified critical, while a safety-critical defect with lower model confidence may be classified low. This can produce unsafe prioritization.
- **Recommended fix:** Separate `model_confidence` from `business_severity`. Derive severity from a validated damage taxonomy, component, extent, and safety rules, with calibrated model output and human review thresholds. Version and test the rules.

### UI-01 — `CapturePage` is a large, tightly coupled workflow component

- **File/location:** `frontend/src/pages/CapturePage.tsx:43-396`
- **Severity:** Medium
- **Category:** Code Smell
- **Problem:** One 396-line component owns truck queries/registration, inspection creation, a six-angle state machine, camera capture, upload progress/error handling, and three page phases. State is spread across many independent `useState` calls.
- **Why it matters:** Invalid UI transitions are easy to introduce, upload retry/cancellation is difficult, and isolated testing requires mounting the whole page with browser media APIs.
- **Recommended fix:** Extract a tested capture-session reducer/hook, truck selection/registration component, and phase components. Represent transitions explicitly and support cancel/retry/finalize semantics.

### UI-02 — API responses are trusted through unchecked TypeScript casts

- **File/location:** `frontend/src/mapInspection.ts:27-49,62-75`; `frontend/src/api.ts:112-135,179-230`
- **Severity:** Medium
- **Category:** Spring Boot
- **Problem:** Network JSON is cast directly to interfaces, and arbitrary strings are cast into `CaptureSource`, status, and finding-type unions. Unknown zones silently become `trailer_mid`; unknown severity silently becomes low. Request functions implement inconsistent error parsing and no timeout/cancellation.
- **Why it matters:** Backend contract drift becomes incorrect UI state rather than a visible contract error; invalid damage can be shown in the wrong location/severity.
- **Recommended fix:** Generate clients from OpenAPI or validate with runtime schemas at the API boundary. Use an explicit unknown state, centralize safe error decoding, and support `AbortSignal`/timeouts.

### CODE-01 — Domain constants and display logic are duplicated

- **File/location:** `backend/utils.py:3-14`; `frontend/src/mapInspection.ts:17-37`; `frontend/src/components/RecentInspections.tsx:4-22`; `frontend/src/components/DamageMap.tsx:5-64`; `frontend/src/pages/CapturePage.tsx:18-25`
- **Severity:** Low
- **Category:** Code Smell
- **Problem:** Severity order/normalization, damage zones, and capture angles are repeated across backend and multiple frontend modules. `styles.css` is also a 1,324-line global stylesheet.
- **Why it matters:** Rules and visual semantics can drift; changes require many edits and are easy to miss.
- **Recommended fix:** Centralize frontend domain metadata, generate/shared-contract enum types where practical, and add contract tests against backend OpenAPI. Split CSS by shell/dashboard/capture when changing those areas, without a cosmetic rewrite.

### CODE-02 — Configuration, versions, ports, and documentation disagree

- **File/location:** `backend/main.py:15-18,28-31,56-64`; `frontend/src/api.ts:6-8`; `frontend/src/pages/CapturePage.tsx:176-182`; `backend/.env.example:6-13`; `README.md:83-103`; `backend/README.md:30-38,78-87`
- **Severity:** Medium
- **Category:** Code Smell
- **Problem:** The app declares/logs versions 0.1.0 and 0.2.0. Backend docs use port 8001, while the production frontend fallback and capture help use 8000. Production builds default to `http://localhost:8000`, which points to each user's machine. `.env.example` contains a developer-specific Windows storage path. The documented report endpoint differs from implementation, and the production dependency `asyncpg` is commented out.
- **Why it matters:** Deployments and onboarding are unreliable, observability cannot identify a canonical release, and a default production build cannot reach its deployed API.
- **Recommended fix:** Define version and base URL once at build/deploy time, prefer same-origin `/api`, fail builds missing required production configuration, remove personal paths, make deployment dependencies explicit, and test documentation examples.

### CODE-03 — UI presents inactive controls and unfinished capabilities as available

- **File/location:** `frontend/src/components/DamageMap.tsx:163-171`; `frontend/src/components/RecentInspections.tsx:35-42`; `frontend/src/components/Topbar.tsx:16-28`; `frontend/src/pages/DashboardPage.tsx:184-203`
- **Severity:** Low
- **Category:** Code Smell
- **Problem:** Export PDF, Filter, organization switcher, notifications, and account controls render without behavior. Reports/history/integration are placeholders, while backend docs describe reporting more strongly than implemented.
- **Why it matters:** Users and reviewers may believe compliance/reporting/account controls exist when they do not.
- **Recommended fix:** Hide or disable unfinished actions with an explicit label, align docs/endpoints, and add acceptance tests before presenting them as operational.

### TEST-01 — No automated tests or CI exist

- **File/location:** repository-wide; `frontend/package.json:6-10` has no test/lint script; `backend/requirements.txt` has no test tooling
- **Severity:** High
- **Category:** Testing
- **Problem:** There are no backend unit/API/integration tests, frontend unit/component tests, end-to-end tests, fixtures, coverage settings, or CI workflow.
- **Why it matters:** Authentication, upload containment, lifecycle, detector failure, schema migration, and business rules can regress without detection. The passing frontend build only checks compilation/bundling.
- **Recommended fix:** Establish pytest with async API/database fixtures, Vitest/React Testing Library, deterministic fake storage/detector/job adapters, PostgreSQL integration tests, and Playwright/Cypress E2E. Run tests, static analysis, builds, audits, and migration checks in CI.

### TEST-02 — Core workflows are hard to test due to globals and side effects

- **File/location:** `backend/database.py:17-21`; `backend/services/storage.py:42`; `backend/services/analysis.py:52-108`; `backend/services/vision.py:48-82`; `backend/routers/inspections.py:48-228`
- **Severity:** Medium
- **Category:** Testing
- **Problem:** Import-time engines/singletons, filesystem creation, direct clocks/cloud clients, in-process background tasks, and router-owned orchestration require real infrastructure or broad monkeypatching.
- **Why it matters:** Failure/concurrency cases—the most important cases—are difficult to reproduce deterministically and will tend to remain untested.
- **Recommended fix:** Apply dependency injection described in ARC-02, provide fakes and an explicit clock, expose a worker use case callable synchronously in tests, and isolate database/storage per test.

### TEST-03 — No contract, migration, concurrency, or security regression coverage

- **File/location:** repository-wide
- **Severity:** High
- **Category:** Testing
- **Problem:** No tests verify frontend/OpenAPI compatibility, SQLAlchemy/PostgreSQL equivalence, RLS, path containment, upload limits/types, authorization, idempotency, concurrent finalize/jobs, detector failure, duplicate VIN handling, or bounded query counts.
- **Why it matters:** These are precisely the areas where the current implementation has production blockers; refactoring without characterization tests can preserve or worsen incorrect behavior.
- **Recommended fix:** Add the focused strategy below before or alongside fixes. Security and lifecycle tests should gate releases.

## Positive observations

- No hardcoded credential value was found in the current text tree. `.env` and common credential filenames are ignored.
- Database queries use SQLAlchemy expressions or SQLite bound parameters; no direct SQL injection was identified.
- Pydantic API schemas and SQLAlchemy persistence models are separated.
- `CaptureAdapter` is a useful starting boundary for hardware-specific ingestion.
- TypeScript strict mode, unused checks, and a production build are enabled and currently pass.
- CORS defaults are limited to local development origins rather than a wildcard.
- The frontend maps wire DTO names into UI models in a dedicated module, although runtime validation is missing.

## Top 10 most important fixes

1. Add authentication, mandatory fleet ownership, authorization on every resource, and protected media delivery.
2. Eliminate upload path traversal with allow-listed metadata, generated object keys, and storage-root containment checks.
3. Remove or strongly isolate destructive admin endpoints; at minimum default them off immediately.
4. Enforce upload limits, streaming, verified media formats, quotas, atomic writes, and safe cleanup.
5. Implement an explicit finalize-once inspection state machine and one durable, idempotent analysis job.
6. Stop treating disabled/failed analysis as “no findings”; model failure/manual-review states and validate the detector/severity rules.
7. Upgrade vulnerable FastAPI/Starlette/python-multipart and Vite/esbuild dependency lines, then rerun audits and regression tests.
8. Adopt migrations, align ORM/PostgreSQL schemas, add constraints, enable FK behavior, and implement/test Supabase RLS.
9. Add strict Pydantic/database validation for identifiers, sources, angles, VINs, GPS, statuses, confidence, and pagination.
10. Build a CI-gated test suite focused first on authorization, uploads, lifecycle concurrency/idempotency, failures, migrations, and API contracts.

## Quick wins (under 30 minutes each)

- Change `admin_enabled` default to `False` and remove data-management controls from non-development builds.
- Stop logging the full database URL and remove `storage_dir` from `/health`.
- Add `backend/conditia.db`, `backend/*.db*`, and `backend/storage/` to `.gitignore` (tracked-file cleanup/history review should be a separate deliberate task).
- Bound `list_inspections.limit` to `1..100`; add pagination defaults to trucks/findings/reports.
- Remove the developer-specific `STORAGE_DIR` from `.env.example` and use the portable default.
- Make the frontend production API URL same-origin or fail the build when it is not configured; remove the localhost production fallback.
- Unify the displayed application version and ports in code/docs.
- Bind Vite to loopback by default (`host: "127.0.0.1"`) unless LAN testing is intentional.
- Hide or disable nonfunctional Export/Filter/account/notification controls.
- Fix the raw-string/backslash warning in `backend/sync_storage.py`'s docstring.

These quick wins reduce exposure and confusion but do not make the application production-ready.

## Larger refactors requiring planning

1. **Identity and tenancy:** authentication provider integration, fleet membership/roles, authorization repositories, RLS, signed media, audit events, and migration of existing records.
2. **Secure ingestion:** streaming/quota service, content verification, atomic storage, server-owned keys, malware/content policy, and storage/database compensation.
3. **Inspection lifecycle:** explicit state machine, coverage requirements, submit/finalize endpoint, idempotency keys, concurrency locks, and deterministic retry behavior.
4. **Durable analysis:** worker queue, outbox, job attempts/timeouts, process isolation for video, model versioning, failure/manual-review outcomes, and observability.
5. **Domain-grade damage/change logic:** validated detector, separation of confidence from severity, defect identity/matching, uncertainty, and human review.
6. **Persistence:** Alembic migrations, PostgreSQL integration, portable UUIDs, constraints/indexes/delete policies, backups, retention, and RLS tests.
7. **Application boundaries:** command/query services, repositories/unit of work, injected ports, thin routers, and one composition root.
8. **Frontend capture decomposition:** reducer/hook-based session, retry/cancel/finalize UX, runtime API validation/generated client, and component tests.

## Suggested cleaner package structure

```text
backend/
  app/
    api/
      routers/
        inspections.py
        trucks.py
        reports.py
        admin.py
      dependencies.py
      error_handlers.py
    application/
      commands/
        create_inspection.py
        ingest_media.py
        finalize_inspection.py
        analyze_inspection.py
      queries/
        inspection_queries.py
        fleet_queries.py
      ports/
        repositories.py
        storage.py
        detector.py
        jobs.py
      unit_of_work.py
    domain/
      inspection.py
      finding.py
      enums.py
      policies/
        severity.py
        change_matching.py
    infrastructure/
      db/
        models.py
        repositories.py
        migrations/
      storage/
        local.py
        supabase.py
      detection/
        google_vision.py
        fake.py
      jobs/
        worker.py
    config.py
    logging.py
    main.py
  tests/
    unit/
    api/
    integration/
    security/

frontend/src/
  app/
    routes.tsx
    shell/
  features/
    capture/
      CapturePage.tsx
      useCaptureSession.ts
      captureReducer.ts
      components/
    dashboard/
    trucks/
    findings/
  shared/
    api/
      client.ts
      generated.ts
      schemas.ts
    domain/
      severity.ts
      inspection.ts
    components/
    styles/
  tests/
```

The structure should be introduced incrementally behind tests; moving files alone does not improve design.

## Suggested testing strategy

### 1. Unit tests

- Inspection state transitions, required-angle coverage, finalize-once behavior, and invalid transitions.
- Severity rules separated from confidence; first-occurrence/change matching with multiple similar defects.
- Storage-key generation and containment, file type/size validation, quota calculations, and cleanup.
- DTO validation for UUIDs, VIN/year, enums, GPS, confidence, and pagination.
- Frontend reducers/mappers/time formatting, including unknown/invalid API values.

### 2. API and security tests

- Authentication required on every endpoint and media request.
- Two-fleet isolation/BOLA attempts for IDs, lists, reports, uploads, and signed media.
- Admin role enforcement, CSRF behavior if cookies are used, audit events, and destructive-action safeguards.
- Traversal payloads in filename/angle/ID; absolute/encoded/mixed-separator variants.
- Oversized, too-many, empty, mislabeled, polyglot, corrupt, and interrupted uploads.
- Duplicate VIN, unsupported source, invalid state, safe error body, and rate-limit behavior.

### 3. Service and concurrency tests

- Multiple angle uploads do not start analysis; finalize starts exactly one job.
- Duplicate finalize/request/job delivery is idempotent.
- Concurrent workers cannot duplicate findings/reports or regress status.
- Storage, database, detector, frame extraction, report, timeout, and worker-crash failures produce retryable/failed/manual-review states—not clear reports.

### 4. Persistence and infrastructure integration tests

- Run migrations from empty and previous schema versions against PostgreSQL.
- Verify constraints, UUID behavior, indexes/query plans, uniqueness, FK enforcement, cascades/restrictions, RLS, and backup/restore.
- Contract-test local and Supabase storage implementations with the same suite.
- Test queue/outbox delivery and retry semantics.

### 5. Frontend component and E2E tests

- Camera permission denial, MediaRecorder unsupported, upload progress/failure/retry/cancel, skip/coverage validation, and finalize.
- Dashboard polling cleanup, failed/manual-review states, authorized media, and empty/error states.
- End-to-end: authenticate -> register truck -> create inspection -> upload required angles -> finalize -> deterministic fake analysis -> review report/finding.

### 6. Contract, performance, and CI gates

- Generate/compare the frontend client with FastAPI OpenAPI.
- Enforce bounded query counts for list/detail endpoints and load-test concurrent uploads/analysis queue backpressure.
- CI: formatting/lint/type checks, backend/frontend tests, production build, migrations on PostgreSQL, dependency/secret/SAST scanning, and container/image scanning.
- Block release on Critical/High dependency findings or security/lifecycle regression failures, with documented exception handling for false positives.

## Final production-readiness score

### **2 / 10**

| Area | Assessment |
|---|---|
| Security | 1/10 — unauthenticated global API/media, destructive admin, traversal, unbounded uploads, vulnerable request stack |
| Business correctness | 2/10 — non-idempotent premature analysis, false-clear failure behavior, weak change/severity rules |
| Architecture/maintainability | 4/10 — useful DTO/adapter starts, but routers and services remain tightly coupled |
| Testing | 1/10 — build checks exist, but no automated behavioral tests or CI |
| Operations/data | 1/10 — no migrations, durable jobs, RLS, production config, observability, or safe artifact handling |

The code is suitable for a controlled local prototype using synthetic data. It is not suitable for production or a security review until the Critical/High items are fixed and proven by tests.
