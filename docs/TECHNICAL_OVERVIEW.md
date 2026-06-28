# Conditia — Technical Overview

This document describes Conditia's technical architecture, the design goals
behind it, and the current state of the system. It reflects the **`Shelton`
branch**, which is the production-hardened line of development.

---

## 1. Technical goal

Build a **hardware-agnostic asset-condition intelligence platform** whose
defining capability is **change detection over time** — reliably answering "when
did this damage first appear on this asset?" — while remaining a **trustworthy
system of record**.

Three engineering principles flow from that goal:

1. **One pipeline, many capture sources.** The capture source (mobile, drone,
   fixed camera, manual) is a single recorded attribute. Mobile is the only
   *ingestion* source implemented today, but adding a new source must not require
   reworking analysis, storage, or the data model.
2. **Never fabricate certainty.** An inspection is only marked `complete` when it
   was genuinely analyzed. Missing detector capability or a decode failure yields
   `review_required` or `failed` — never a false "clear." Integrity beats
   coverage.
3. **Durability and correctness over convenience.** Analysis is dispatched
   through a database-backed job with atomic claiming and crash recovery, the
   schema is migration-managed, and production configuration is validated at
   startup.

---

## 2. High-level architecture

```text
conditia/
├── frontend/   React 18 + TypeScript + Vite dashboard & guided capture (Vitest)
│   └── proxies /api → http://127.0.0.1:8001 in dev
├── backend/    FastAPI + Pydantic + async SQLAlchemy
│   ├── routers/      HTTP API (auth, fleet, trucks, inspections, media, findings, reports)
│   ├── services/     analysis pipeline, jobs, change detection, reports, storage, vision
│   ├── adapters/     capture-source adapters (mobile implemented; registry-based)
│   ├── models/       SQLAlchemy ORM (db_models) + Pydantic schemas
│   ├── migrations/   Alembic migration chain (0001 → 0005)
│   ├── domain.py     typed enums shared across API/persistence/services
│   ├── security.py   auth modes (disabled/api_key/jwt) + role guards
│   ├── config.py     env-driven settings + production-posture validation
│   └── database.py   async engine, URL normalization, migration runner
└── docs/, data/      design context & code-review history
```

The frontend and backend are decoupled; in development Vite proxies `/api` to the
backend on **port 8001** (avoids CORS and `localhost` vs `127.0.0.1` mismatches).

---

## 3. Backend

### 3.1 Framework & stack

- **FastAPI** (app version `0.3.0`) with an async lifespan.
- **Async SQLAlchemy 2.0** ORM with `asyncpg` (PostgreSQL) or `aiosqlite`
  (SQLite) drivers.
- **Pydantic v2** for request/response schemas and settings.
- **Alembic** for schema migrations.
- **Pillow** for image validation; optional Google Cloud Vision for experimental
  detection; optional OpenCV for video frames.

### 3.2 Domain model

Core tables (`backend/models/db_models.py`), all using portable string UUID
primary keys so the same models run on SQLite and PostgreSQL:

- **`fleets`** — fleet accounts.
- **`trucks`** — assets (VIN unique, make/model/year/plate), FK to fleet.
- **`inspections`** — one capture event per asset; carries the lifecycle
  `status` and the `capture_source`.
- **`inspection_media`** — uploaded photos/videos with capture angle, GPS,
  storage path; constrained by CHECK constraints on type/angle/source.
- **`analysis_jobs`** — durable dispatch record (one per inspection, unique),
  with `status`, `attempts`, and `last_error` for retry/recovery.
- **`findings`** — individual damage findings: `finding_type`, `severity`,
  `confidence`, `zone`, optional bounding box, lifecycle (`status`,
  `resolved_at`, `resolution_notes`), and **`first_seen_inspection_id`** which
  powers change detection.
- **`reports`** — generated per-inspection summary (`total_findings`,
  `critical_findings`, `summary`, `raw_json`, optional `pdf_path`).
- **`fleet_memberships`** — composite-key (`fleet_id`, `user_id`) mapping of a
  JWT user to a fleet and a `role` (CHECK-constrained to
  `viewer`/`inspector`/`admin`). This is the source of truth for user identity
  and authorization, looked up server-side on each request.

Domain enums live in `domain.py` (`CaptureSource`, `CaptureAngle`,
`InspectionStatus`, `AnalysisJobStatus`, `FindingType`, `FindingStatus`,
`Severity`, `FleetRole`) and are enforced both in Pydantic and via DB CHECK
constraints.

### 3.3 The inspection lifecycle

The lifecycle is an explicit state machine, decoupling *upload* from *analysis*:

```text
POST /inspections                       -> status = uploading
POST /inspections/{id}/upload (repeat)  -> verify signature & quota, store media
                                           (status stays uploading; no analysis)
POST /inspections/{id}/finalize         -> status = submitted, enqueue ONE job
analysis worker claims the job          -> submitted → processing (atomic)
   extract frames → detect → change-match → write findings → generate report
                                        -> complete | review_required | failed
```

Why explicit `finalize`: uploads can arrive in multiple requests; analysis must
run exactly once, after the driver confirms the walk-around is complete.

### 3.4 Analysis pipeline & durable jobs

- **`services/analysis_jobs.py`** dispatches work through the `analysis_jobs`
  table. A job is **atomically claimed** with a conditional `UPDATE ... WHERE
  status = 'pending'`; if the row count isn't exactly 1, a duplicate delivery is
  a safe no-op.
- On startup, **`resume_incomplete_analysis_jobs()`** reclaims any job left
  `pending`/`running` by a crashed worker (resetting a stuck `processing`
  inspection back to `submitted`) and re-runs it. This gives crash recovery
  without an external queue.
- **`services/analysis.py`** runs the actual pipeline: frame extraction →
  damage detection → change matching → finding persistence → report generation,
  ending in a terminal inspection status.
- The in-process background worker is appropriate for development; a durable
  external queue and isolated worker remain a production prerequisite.

### 3.5 Change detection (the differentiator)

`services/change_detection.py` answers "when did this finding first appear?"

- For each new finding it walks the asset's **prior** inspections (oldest-first,
  only `complete`/`review_required` ones) and matches on **(finding_type,
  zone)**, returning the inspection id where that defect was first seen — or the
  current inspection if it's new.
- An **unlocalized finding (no zone) is always treated as new**, because a label
  with no location is not a stable identity and must not be attributed to an
  unrelated historical defect.
- This MVP matching is intentionally conservative; a production version would
  tighten it with bounding-box location signatures and tolerance.

### 3.6 Detection / vision integrity

Damage detection is **not yet a validated model**. The system is built so that
the absence of a real detector can never produce a misleading clean result:
missing capability or experimental Google label detection routes the inspection
to **`review_required`**, and decode/detector failures route to **`failed`**.
The Google integration is a triage signal only — its confidence is retained but
its severity always requires human review.

### 3.7 API surface

Meta routes (`/health`, `/ready`, `/`) are unguarded; all `/auth`, `/fleet`,
`/trucks`, `/inspections`, `/inspection-media`, `/findings`, and `/reports`
routes are mounted under an API router guarded by `require_api_access` (mutating
finding routes add `require_roles`):

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness + build/feature info (no DB) |
| GET | `/ready` | Readiness — executes `SELECT 1` against the DB |
| GET | `/auth/me` | Current principal: auth mode, user id, fleet id, role |
| GET | `/fleet/stats` | KPI counts (trucks, today/pending/complete, open findings) |
| POST | `/trucks` / GET `/trucks` | Register / list assets (fleet-scoped, bounded) |
| GET | `/trucks/{id}` / `/trucks/{id}/inspections` | Asset detail / its inspections |
| POST | `/inspections` | Create an `uploading` inspection |
| POST | `/inspections/{id}/upload` | Upload verified media |
| POST | `/inspections/{id}/finalize` | Submit once for analysis |
| GET | `/inspections` / `/inspections/{id}` | Inspection summaries / detail (findings + media) |
| GET | `/inspections/{id}/findings` / `/inspections/{id}/media` | Per-inspection findings / media |
| GET | `/inspection-media/{id}/content` | Authorized media delivery (local file or signed redirect) |
| GET | `/findings` | List findings (filter by severity/status, fleet-scoped) |
| PATCH | `/findings/{id}` | Update finding status/notes (`inspector`/`admin` only) |
| GET | `/reports` / `/reports/{inspection_id}` | List reports / structured report once generated |

### 3.8 Security & hardening

- **Auth & roles (`security.py`):** `AUTH_MODE` selects one of three strategies,
  each resolving to a `Principal(user_id, fleet_id, role)`:
  - `jwt` — verifies a bearer token (HS256, `authenticated` audience, required
    `sub`/`exp`), then looks up the user's `fleet_memberships` row to derive the
    fleet scope and `FleetRole`. This is **real user identity with roles**, not
    just a perimeter. A token without a membership row is rejected (403).
  - `api_key` — constant-time `X-API-Key` check scoped to one configured
    `API_FLEET_ID`, with no user id; a service account (role `admin`).
  - `disabled` — development only; every request runs as `admin` with no scope.

  `require_roles(*roles)` layers role authorization on top (e.g. only
  `inspector`/`admin` may mutate findings). Cross-tenant PostgreSQL RLS policies
  are still defined only in `db/schema.sql` (not yet in Alembic), and there is no
  immutable audit log yet.
- **Upload safety:** files are signature-checked, server-renamed to opaque keys,
  path-contained, streamed on a worker thread, and bounded by `MAX_UPLOAD_BYTES`,
  `MAX_FILES_PER_UPLOAD`, `MAX_REQUEST_BYTES`, and `MAX_IMAGE_PIXELS`
  (decompression-bomb guard).
- **Transport hardening (`main.py`):** security headers
  (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`), per-request IDs, a global exception handler that returns
  a request id, and a request-size middleware that rejects oversized bodies with
  413.
- **Production posture validation (`config.py`):** in `ENVIRONMENT=production`
  the app **refuses to start** unless auth is enabled, the DB is PostgreSQL via
  asyncpg, Supabase object storage is configured, docs are disabled, seeding is
  off, a fleet scope is set, and CORS uses non-localhost origins.

### 3.9 Storage

A storage-service abstraction supports a **local private directory** for
development and **Supabase Storage** for production (private bucket, short-lived
authorized redirects). The legacy static media mount is removed; media is served
through an authorized content endpoint.

---

## 4. Database & migrations

### 4.1 SQLite (dev) → PostgreSQL/Supabase (prod)

The same ORM runs on both engines. `database.py` provides
**`build_async_url()`**, which normalizes a database URL so a pasted Supabase
connection string "just works":

- rewrites `postgres://` / `postgresql://` → `postgresql+asyncpg://`;
- converts the libpq-only `sslmode` query arg into an asyncpg `ssl` context,
  following libpq semantics (`require` encrypts without chain verification, which
  matches Supabase's managed pooler certs; `verify-ca`/`verify-full` verify),
  and auto-enables TLS for `*.supabase.co` / `*.supabase.com`;
- sets `statement_cache_size=0` so the Supabase transaction pooler (PgBouncer)
  works.

### 4.2 Schema management

- **Alembic owns the PostgreSQL schema** (`migrations/`, chain `0001` → `0005`;
  `0005` adds the `fleet_memberships` table that backs JWT user authorization).
  `migrations/env.py` builds its engine from the same `build_async_url()` so
  migrations connect identically to runtime.
- On **SQLite dev**, `init_db()` uses `create_all`. On **PostgreSQL**, `init_db`
  does *not* create tables; instead the app runs **`alembic upgrade head`** at
  startup (in development) via `run_migrations()`, which shells out to Alembic in
  a **subprocess** — necessary because Alembic's async `env.py` calls
  `asyncio.run()`, which cannot nest inside Uvicorn's running event loop.
- **Timestamps are `TIMESTAMPTZ`** (migration `0004`), matching the
  timezone-aware UTC values the ORM produces — asyncpg rejects writing aware
  datetimes into naive columns.

---

## 5. Frontend

- **React 18 + TypeScript + Vite.** An `AppLayout` shell (sidebar + topbar)
  hosts the console routes: `/` (overview), `/trucks` and `/trucks/:truckId`,
  `/inspections` and `/inspections/:inspectionId`, `/findings`, `/reports` and
  `/reports/:inspectionId`, `/history`, `/integrations/samsara`, and
  `/settings`. Guided capture (`/capture`, `/capture/:truckId`) renders outside
  the shell, and a catch-all redirects to `/`.
- **Auth (`auth/AuthProvider`, `pages/LoginPage`):** on load the app calls
  `/auth/me`; in `jwt` mode a user without a session sees the token sign-in
  screen, and the pasted bearer token is stored in `sessionStorage` and attached
  to API requests. The **Settings** page surfaces the signed-in account (user,
  fleet, role, auth mode), role capabilities, and sign-out.
- **Overview** is a light, scannable fleet-operations console: KPI stat row, a
  recent-inspections list, and a per-truck **damage map** with severity-colored
  zones plus findings annotated with "first/previously detected." Findings,
  reports, trucks, and history each have dedicated list/detail pages; Samsara
  telematics integration is a documented placeholder.
- **Guided capture** (`features/capture/useCaptureSession`,
  `components/capture/*`) walks a phone user through the required angles and
  uploads media.
- **Design system** (`.impeccable.md`): light theme, restrained tinted-blue
  neutrals with a single blue accent, severity-only color
  (Critical/Medium/Low/Clear), monospaced numerics (Geist Mono) for an
  instrument feel, UI font Hanken Grotesk. Explicit anti-references: no
  glassmorphism, gradient text, or neon-on-dark.
- **Testing:** Vitest + Testing Library with risk-based coverage gates
  (statements/branches/functions/lines ≥ 85/75/80/90).

---

## 6. Configuration (key env vars)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLite by default; any Postgres/Supabase URL is auto-normalized to asyncpg |
| `ENVIRONMENT` | `development` \| `test` \| `production` (production enforces the security posture) |
| `AUTH_MODE` / `API_KEY` / `API_FLEET_ID` | Perimeter auth and fleet scope |
| `STORAGE_BACKEND` | `local` \| `supabase` |
| `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_STORAGE_BUCKET` | Supabase storage config |
| `DOCS_ENABLED` | Toggle Swagger/Redoc (must be false in production) |
| `SEED_ON_STARTUP` | Load the demo fleet if empty (dev only) |
| `MAX_UPLOAD_BYTES` / `MAX_FILES_PER_UPLOAD` / `MAX_REQUEST_BYTES` / `MAX_IMAGE_PIXELS` | Upload quotas & safety |
| `GOOGLE_APPLICATION_CREDENTIALS` | Enables experimental Vision triage |

---

## 7. Running locally (Windows)

```powershell
cd C:\Users\yhail\Projects\conditia\backend
.\.venv2\Scripts\Activate.ps1
python -m uvicorn main:app --host 127.0.0.1 --port 8001   # runs alembic 0001→0004 on Postgres
python seed.py --force                                    # optional demo fleet
```

```powershell
cd C:\Users\yhail\Projects\conditia\frontend
npm run dev    # http://127.0.0.1:5173, proxies /api → :8001
```

Verify: `Invoke-RestMethod http://127.0.0.1:8001/health`. A convenience
`backend\start.ps1` script stops port-8001 listeners, rebuilds the venv if
broken, runs migrations, and starts the server.

> Environment notes: this machine uses `.venv2` (the original `.venv` was
> file-locked), and `uvicorn[standard]` was replaced with plain
> `uvicorn` + `watchfiles` to avoid a Windows `httptools` install lock.

---

## 8. Quality & CI

- **Backend:** `ruff` lint, `pytest` with coverage (≥ 80% total), `pip-audit`.
  A full `tests/` suite covers the API, ingestion, queries, analysis/vision,
  change detection, migrations, the report generator, and storage.
- **Frontend:** Vitest coverage gates and a type-checked production build,
  `npm audit`.
- **CI** runs the same checks and verifies the Alembic migration chain.

---

## 9. Current state & known gaps

**Working:** guided mobile capture, structured upload, the explicit inspection
lifecycle, durable analysis jobs with crash recovery, change-over-time
detection, the fleet console (overview KPIs and damage map, trucks, inspections,
findings with role-gated resolution, reports, history, settings/account), JWT
user identity with fleet-membership roles, and structured report generation. The
backend runs on Supabase PostgreSQL via the asyncpg/pooler normalization
described above.

**Known gaps / production prerequisites:**

1. **Validated damage model** — current detection is a placeholder; everything
   un-analyzed routes to `review_required`.
2. **Tenant isolation in migrations & audit log** — JWT identity, roles, and the
   `fleet_memberships` table now exist, but cross-tenant PostgreSQL RLS still
   lives only in `db/schema.sql` (not Alembic), and there is no immutable audit
   log of who changed what.
3. **Durable external job infrastructure** — the in-process worker needs to
   become an isolated, retrying worker for production.
4. **Production object-storage adapter** — finalize the Supabase Storage path
   and authorized media delivery.
5. **Reports/PDF export, telematics, and org management** — PDF export, the
   Samsara integration, and in-console user/role/API-key management are not yet
   built.

The guiding rule for closing these gaps is unchanged: **prefer truthful,
review-gated behavior over fabricated certainty**, because Conditia's value is
its credibility as a system of record.
