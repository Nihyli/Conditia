# Conditia — Security, Scalability & Consistency Review

**Date:** 2026-07-06
**Scope:** Entire repository (`backend/`, `frontend/`, `.github/`, startup scripts, docs)
**Stack:** FastAPI + async SQLAlchemy + SQLite/Postgres(Supabase) backend; React/TypeScript/Vite frontend
**Method:** OWASP Top 10 (2021) source audit + OWASP API Security Top 10 (2023) endpoint audit + infrastructure/scale review + startup-script reliability review

---

## Executive summary

The codebase is in **much better shape than a typical MVP**. The June review's biggest blockers
(shared-key-only auth, RLS missing from Alembic, no job leases) have been fixed: JWT auth with
DB-backed roles exists, RLS ships in migration `0006`, and analysis jobs use owner+expiry leases
(`0007`). Both dependency audits run clean. There is no SQL injection surface, no XSS sink, no
committed cloud credential, uploads are sniffed/verified/size-capped with path-traversal guards,
and the API-key compare is timing-safe. That is a genuinely strong baseline.

What remains falls into three buckets:

1. **Security gaps that must be closed before real customer data** — DB TLS verification is
   disabled, rate limiting is off by default and unbounded in memory, the well-known dev JWT
   secret would pass production validation, and a runtime database + real inspection photos are
   committed to git history.
2. **Functional inconsistencies that will break in production auth mode** — media images cannot
   load in JWT mode (no way to send the Authorization header from an `<img>` tag), and
   multi-fleet users hard-fail with a 409 the frontend can't recover from.
3. **Scale ceilings** — analysis runs inside the API process, per-truck history is recomputed
   on every list request, the rate limiter/job dispatch are single-process, and there is no
   deployment artifact (Dockerfile/worker) at all.

### Finding counts

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 5 |
| Medium | 8 |
| Low | 7 |
| Info / hygiene | 5 |

### Verification performed (clean checks)

- `pip-audit -r backend/requirements.txt` — **no known vulnerabilities** (run 2026-07-06)
- `npm audit --omit=dev` (frontend) — **0 vulnerabilities**, 9 prod deps
- SQL injection: grepped for f-string/`%`-formatted `execute`, raw SQL, `text(` — only static
  `SELECT 1` health probe and static migration DDL. All queries use the SQLAlchemy expression
  API with bound parameters. **Clean.**
- XSS: grepped `dangerouslySetInnerHTML`, `innerHTML`, `eval(`, `document.write` — **zero hits**.
  All rendering goes through React's escaping. **Clean.**
- Secrets: grepped provider key prefixes (`sk_live`, `AKIA…`, `ghp_`, `AIza…`, `xox…`, `sk-ant-`)
  across tracked files — **zero hits**. `.gitignore` covers `.env`, `service-account*.json`. **Clean.**
- Mass assignment: every create/update schema sets `ConfigDict(extra="forbid")`; responses use
  explicit Pydantic DTOs, never raw ORM dumps. **Clean.**
- Path traversal: `LocalStorageService._resolve` resolves and checks `is_relative_to(base)`;
  filenames are server-generated UUIDs; client filename is never used. **Clean.**
- Upload validation: magic-byte sniffing (PNG/JPEG/GIF/WebP/WebM/MP4/MOV only — SVG correctly
  rejected), Pillow decode + decompression-bomb guard, byte-counted size caps enforced during
  streaming (not trusting Content-Length), atomic temp-file rename. **Clean.**
- CORS: explicit origin list, `allow_credentials=False`, localhost origins rejected in
  production by config validation. **Clean.**
- API-key comparison uses `secrets.compare_digest` (timing-safe). **Clean.**
- BOLA/tenancy: every ID-parameterized endpoint joins through `Truck.fleet_id == principal.fleet_id`
  before returning data, and returns a uniform 404. Sister-route audit found no unguarded writer.
  **Clean (with the VIN caveat in SEC-7).**
- Security headers: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Permissions-Policy`, restrictive CSP on all JSON responses, `X-Request-ID` correlation. **Good.**
- Production boot guards: refuses to start with auth disabled, SQLite, local storage, docs
  enabled, seeding enabled, or localhost CORS. **Good.**

---

## Part 1 — Security findings (OWASP Top 10)

### [CRITICAL] SEC-1 · A02: Database TLS certificate verification disabled

**File:** `backend/database.py:54-62`
**CWE:** CWE-295 (Improper Certificate Validation)

The asyncpg SSL context for Supabase/Postgres connections is built with:

```python
ctx.check_hostname = False
ctx.verify_mode = ssl_lib.CERT_NONE
```

for every connection unless the operator explicitly appends `sslmode=verify-full` to the URL —
which the `.env.example` never mentions. Traffic is encrypted but the server identity is never
verified, so an attacker who can intercept the network path (cloud NAT hop, compromised DNS,
BGP-level interception) can present any certificate and read/modify **all tenant data,
memberships, and findings in transit**. For a business whose product *is* a defensible
evidence record, silent DB MITM is an existential risk.

The comment is right that Supabase pooler certs aren't in the system trust store — but Supabase
publishes its CA certificate for exactly this reason.

**Remediation (in priority order):**
1. Download the Supabase CA cert (Dashboard → Settings → Database → SSL) into the deployment,
   and build the context with `ssl_lib.create_default_context(cafile=SUPABASE_CA_PATH)` with
   `verify_mode=CERT_REQUIRED`. Add a `DATABASE_SSL_CA` setting; when set, always verify.
2. If (1) is genuinely infeasible for a deployment target, keep `CERT_NONE` **only** behind an
   explicit `DATABASE_SSL_INSECURE=true` env var that logs a startup warning, and document the
   compensating control (e.g., VPC-private networking).
3. Make the production config validator refuse `CERT_NONE` unless the explicit opt-out is set.

**Verification:** connect with the CA pinned and confirm success; then point `DATABASE_URL` at a
host with a mismatched cert and confirm the connection is refused.

---

### [HIGH] SEC-2 · A04/API4: Rate limiting off by default, unbounded memory, proxy-blind

**Files:** `backend/main.py:162-217`, `backend/config.py:37`
**CWE:** CWE-770 (Allocation Without Limits), CWE-307 (Improper Restriction of Authentication Attempts)

Three stacked problems:

1. **`rate_limit_per_minute` defaults to `0` (disabled)** and the production validator does not
   require it to be set. A default production deploy has **no throttle at all** on JWT
   brute-forcing (`/auth/me` verifies signatures as fast as you can send them), upload floods,
   or list hammering.
2. **`_rate_window` grows forever.** Every distinct client IP inserts a dict entry that is never
   evicted (only reset when the *same* key returns after 60s). A source able to rotate IPs
   (IPv6 space, botnet) grows the dict until the process OOMs.
3. **Keyed on `request.client.host`.** Behind any reverse proxy / load balancer (which production
   will have), every user shares the proxy's IP → one noisy client rate-limits **all** customers
   out of the product. This is the shared-bucket lockout the OWASP guidance warns about.

**Remediation:**
- Require a positive `RATE_LIMIT_PER_MINUTE` in the production validator.
- Evict expired entries (periodic sweep or an LRU cap, e.g. `cachetools.TTLCache`).
- Resolve the client key from the trusted proxy hop (uvicorn `--proxy-headers` +
  `FORWARDED_ALLOW_IPS`, then read `X-Forwarded-For` left-most-trusted), and prefer keying
  authenticated requests by `principal.user_id` instead of IP.
- Longer term: move limiting to the gateway or a shared Redis so it survives multi-instance.

---

### [HIGH] SEC-3 · A04/API4: Unbounded resource consumption per inspection (storage + paid API)

**Files:** `backend/routers/inspections.py:169-220`, `backend/services/analysis.py:69-107`, `backend/services/vision.py:77-117`
**CWE:** CWE-770

Two unbounded loops, both attacker-reachable with an inspector token:

1. **Storage exhaustion.** Each upload request is capped (6 files × 25 MB), but there is no cap
   on the *number of upload requests* per inspection while it sits in `uploading`. A hostile or
   buggy client can attach thousands of files to one inspection → disk/bucket exhaustion and a
   giant media list for every later read. No per-tenant quota exists.
2. **Paid-API cost explosion.** `extract_frames` samples every 2 seconds with **no cap on frame
   count or video duration**, and each frame becomes a Google Vision API call
   (`detect_damage`), instantiating a **new `ImageAnnotatorClient` per frame**. A 25 MB WebM at
   low bitrate can be hours long → thousands of billable Vision calls from a single upload.

**Remediation:**
- Cap media rows per inspection (e.g., 30) checked inside `ingest` alongside the state check.
- Cap extracted frames per video (e.g., `MAX_FRAMES_PER_VIDEO = 60`) and reject/flag longer
  videos for human review; reuse one Vision client per batch.
- Add a per-fleet daily analysis budget before the detector loop; overflow → `review_required`.

---

### [HIGH] SEC-4 · A02/A05: Known dev JWT secret passes production validation

**Files:** `backend/scripts/mint_dev_token.py:33`, `README.md:63`, `backend/config.py:52-55`
**CWE:** CWE-798 (Use of Hard-coded Credentials)

`conditia-local-dev-jwt-secret-change-me-32chars` is printed in the README, echoed by
`mint_dev_token.py` (which even prints `JWT_SECRET=<value>` for pasting into `.env`), and — being
39 characters — **satisfies the production `len >= 32` check**. The path from "followed the
README" to "production signs sessions with a public secret" is one copy-paste. Anyone can then
mint an admin token for any fleet (memberships are still checked, but see SEC-8: fleet admins
can be impersonated by user-id).

**Remediation:**
- Blocklist the known dev secret (and low-entropy strings generally) in
  `validate_security_posture` when `environment == "production"`.
- Have `mint_dev_token.py` refuse to run when `ENVIRONMENT=production`.
- Longer term, drop shared-secret HS256 entirely (SEC-8).

---

### [HIGH] SEC-5 · A05: Runtime database and customer media committed to git

**Files (tracked):** `backend/conditia.db` (81 KB), `backend/storage/**/**.png` (real capture uploads), `backend/$null`
**CWE:** CWE-538 (Insertion of Sensitive Information into Externally Accessible File)

`.gitignore` excludes `*.db` and `backend/storage/`, but these files were committed before the
rules landed and remain tracked — the ignore rules are decoys. Today the DB holds demo data;
the moment anyone runs against real data and commits, VINs, plates, GPS coordinates, and
condition photos become permanent repo history. Anyone with repo access (contractors, CI,
a future leak) gets the data. `backend/$null` is a stray PowerShell-redirect artifact.

**Remediation:**
```bash
git rm --cached backend/conditia.db "backend/\$null"
git rm -r --cached backend/storage
git commit -m "Remove runtime artifacts from version control"
# then purge history before the repo is ever shared more widely:
git filter-repo --path backend/conditia.db --path backend/storage --invert-paths
```
Treat any credentials that ever touched that DB as rotated.

---

### [HIGH] SEC-6 · A07: No audit trail for security-relevant events

**Files:** `backend/routers/findings.py:40-67`, `backend/routers/memberships.py`, `backend/security.py`
**CWE:** CWE-778 (Insufficient Logging)

For a product whose pitch is "defensible evidence for liability disputes", the system cannot
answer *who did what*:

- `Finding` has no `resolved_by` — any inspector can mark damage `false_positive` and the record
  shows nothing about the actor. That is a direct integrity hole in the evidence chain.
- Membership grants/role-changes/removals are not logged with the acting admin.
- Failed/successful auth attempts are not logged (no signal for credential stuffing).
- `Inspection.created_by` is captured but never exposed in any API response.

**Remediation:** add `resolved_by` (and set it from `principal.user_id`) to findings; emit
structured log events (actor, action, resource, request_id) for auth failures, membership
changes, finding resolution, and finalization; surface `created_by` in `InspectionOut`.
Longer term, an append-only `audit_log` table is the natural backbone for the evidence story.

---

### [MEDIUM] SEC-7 · A01/API1: Global VIN uniqueness leaks cross-tenant fleet contents

**Files:** `backend/models/db_models.py:77`, `backend/routers/trucks.py:30-38`
**CWE:** CWE-203 (Observable Discrepancy)

`Truck.vin` is globally unique. A fleet-A admin who POSTs a VIN already registered by fleet B
receives `409 "A truck with this VIN already exists"` — a cross-tenant oracle. VINs are
semi-public but enumerable (sequential serials per plant), so a competitor with an account can
probe which assets other customers manage on the platform.

**Remediation:** change the constraint to `UniqueConstraint("fleet_id", "vin")`. If a global
identity is ever needed, keep it internal and return the same 409 message regardless of tenant.

---

### [MEDIUM] SEC-8 · A07: JWT design — shared-secret HS256, no `iss` check, no revocation

**File:** `backend/security.py:30-55`
**CWE:** CWE-347 (Improper Verification of Cryptographic Signature — hardening), CWE-613

What exists is correct as far as it goes (algorithm pinned to HS256, `aud` verified, `exp`/`sub`
required). But:

- **Shared secret**: the same key signs and verifies; every service holding it can mint admin
  tokens. Supabase supports asymmetric signing (RS256/ES256 via a JWKS endpoint) — verify with
  the public key and the secret disappears from your servers entirely.
- **No `iss` validation**: any HS256 token with the right secret and `aud=authenticated` is
  accepted regardless of issuer.
- **No revocation story**: tokens are valid until `exp` (24 h for dev tokens). A fired employee
  keeps fleet access for up to a day. Membership deletion helps (the DB lookup fails), which is
  a good design — call that out and keep it — but document that fleet removal is the revocation
  mechanism, and prefer short-lived access tokens (≤1 h) + refresh in production.

**Remediation:** validate `iss` against the Supabase project URL; support JWKS verification
(`PyJWT` `PyJWKClient`); shorten prod token lifetime.

---

### [MEDIUM] SEC-9 · A07: Bearer token stored in `sessionStorage`

**File:** `frontend/src/auth/session.ts:1-19`
**CWE:** CWE-522 (Insufficiently Protected Credentials)

The JWT lives in `sessionStorage`, readable by any JS that ever executes in the origin (a
future XSS, a compromised npm dependency, a malicious browser extension). Today the XSS surface
is clean (verified), but this is one supply-chain incident away from token theft. `sessionStorage`
also silently signs users out on every new tab, which will be reported as "sign-in breaks".

**Remediation:** when the real Supabase login lands (see INC-1), move to the Supabase JS client
session handling, or an HttpOnly `SameSite=Strict` cookie set by a thin BFF endpoint. Until
then, accept the risk consciously and keep prod token lifetimes short.

---

### [MEDIUM] SEC-10 · A05: `/health` leaks stack details unauthenticated

**File:** `backend/main.py:252-260`
**CWE:** CWE-200

`/health` reveals the database dialect, app version, feature list, and whether Google Vision is
configured — useful recon for tailoring attacks, available to anyone. `/auth/me` similarly
reveals the configured `auth_mode` to unauthenticated callers only through error semantics
(acceptable), but `/health` returns everything as data.

**Remediation:** return `{"status": "ok"}` publicly; move version/database/vision detail into
an authenticated or internal-only endpoint (or gate on a header from the load balancer).

---

### [MEDIUM] SEC-11 · A04: Analysis pipeline deletes findings before rebuilding them

**File:** `backend/services/analysis.py:188-231`
**CWE:** CWE-459

Re-analysis wipes all `Finding` rows for the inspection, including any whose `status` a human
already changed (`acknowledged`, `resolved`, `false_positive` and `resolution_notes`). The
current state machine makes re-analysis rare (only lease-expiry reclamation), but that path
exists: a job that overruns its 30-minute lease is reclaimed, re-run, and silently destroys
human triage work — again, an evidence-integrity problem.

**Remediation:** either carry human dispositions forward (match by `finding_type`+`zone`), or
refuse to delete findings that are not in `open` status and flag for manual merge.

---

### [MEDIUM] SEC-12 · A09: Report data is a second, unscoped copy of findings

**Files:** `backend/services/report_generator.py:46-65`, `backend/routers/reports.py`

`Report.raw_json` embeds a snapshot of all findings. The report endpoints do scope by fleet
(verified clean), but the snapshot never updates when findings are resolved and duplicates
grow with every inspection. Not a leak today; a consistency trap (stale severity shown in
"exports") and a place where a future endpoint could accidentally serve unscoped data.

**Remediation:** generate report JSON on demand from the findings table, or include a
`generated_at`-based staleness notice in the UI.

---

### [LOW] SEC-13 · A05: No HSTS header

`_add_security_headers` sets a strong header baseline but not `Strict-Transport-Security`.
If TLS terminates at a gateway that already injects HSTS, document that; otherwise add
`max-age=63072000; includeSubDomains` for production responses.

### [LOW] SEC-14 · A01: `Truck.fleet_id` is nullable

Trucks created by a service principal with no `api_fleet_id` (only possible outside production)
get `fleet_id=NULL` and become invisible to every JWT user while still counting in service-level
stats. Make `fleet_id` required at the API layer for all principals.

### [LOW] SEC-15 · A07: `X-Fleet-ID` compared as raw string

`_select_membership` compares the header against `membership.fleet_id` with string equality.
An uppercase or braced UUID form fails with 403 even for a legitimate member. Normalize through
`UUID(value)` before comparing (and return 400 on malformed input).

### [LOW] SEC-16 · A09: `LocalStorageService.delivery_url` silently validates path only

Fine functionally, but `StorageError`s from `delete()` cleanup in `MobileAdapter.receive_media`
propagate and mask the original upload failure; wrap cleanup in best-effort logging like
`InspectionIngestionService._delete_after_failed_commit` already does.

### [INFO] SEC-17 · RLS is owner-bypassed by design — document it

Migration `0006` enables RLS without `FORCE ROW LEVEL SECURITY`. The backend connects as the
table owner, so RLS never applies to it — all real isolation is the app-level fleet predicate;
RLS only protects direct PostgREST/anon access. That's a legitimate design, but the migration
docstring oversells it ("even if the API's fleet predicate is bypassed…"). Either connect the
API through a non-owner role with RLS + `set_config('request.jwt.claims', …)`, or fix the
comment so nobody assumes DB-level protection exists when it doesn't.

---

## Part 2 — API endpoint inventory (OWASP API Top 10)

Every endpoint was traced from handler to data access. Auth model: `require_api_access`
dependency on the parent router runs for all routes; role-gated routes add `require_roles(...)`.

| Endpoint | Auth | Tenancy scope | Disposition |
|---|---|---|---|
| `GET /health`, `/ready`, `/` | none | n/a | Clean — but see SEC-10 (over-shares) |
| `GET /auth/me` | any principal | self | Clean |
| `GET /fleet/stats` | any principal | fleet-scoped | Clean |
| `GET /fleet/members` | any principal | fleet-scoped | Clean |
| `POST /fleet/members` | admin | fleet-scoped | Clean |
| `PATCH /fleet/members/{id}` | admin | fleet-scoped | Clean — last-admin guard present |
| `DELETE /fleet/members/{id}` | admin | fleet-scoped | Clean — last-admin guard present |
| `POST /trucks` | admin | fleet-forced | SEC-7 (cross-tenant VIN 409) |
| `GET /trucks`, `/trucks/{id}`, `/trucks/{id}/inspections` | any principal | fleet-scoped | Clean |
| `POST /inspections` | inspector/admin | truck ownership checked | Clean |
| `GET /inspections`, `/{id}`, `/coverage`, `/findings`, `/media` | any principal | fleet-scoped join | Clean |
| `POST /inspections/{id}/upload` | inspector/admin | ownership checked | SEC-3 (no per-inspection cap) |
| `POST /inspections/{id}/finalize` | inspector/admin | ownership checked | Clean — atomic state guard |
| `GET /findings`, `PATCH /findings/{id}` | read: any / write: inspector-admin | fleet-scoped join | SEC-6 (no actor), SEC-11 |
| `GET /reports`, `/reports/{id}` | any principal | fleet-scoped join | Clean — see SEC-12 |
| `GET /inspection-media/{id}/content` | any principal | fleet-scoped join | INC-2 (unusable in JWT mode) |

**API-level notes:**
- **API1 (BOLA):** consistently guarded via fleet joins returning uniform 404. Strong.
- **API3 (mass assignment / excessive exposure):** `extra="forbid"` on all writes; DTO-projected
  responses. Strong.
- **API5 (function-level authz):** role gates present on every writer; no sister-route gap found.
- **API9 (inventory):** `DOCS_ENABLED` correctly forced off in production; no stray debug routes.

---

## Part 3 — Functional inconsistencies (will break in production)

### [HIGH] INC-1 · Frontend cannot obtain a real token — no Supabase login wired up

**Files:** `frontend/src/pages/LoginPage.tsx`, `frontend/src/auth/*`

Production is documented to use "Supabase-issued JWTs", but the frontend has **no Supabase login
flow** — the only way in is to paste a token minted by the backend dev script. There is no
`@supabase/supabase-js`, no email/password or OAuth screen, no refresh handling. As shipped, a
real customer literally cannot log in to a production deployment. This is the single biggest gap
between the docs and the code.

**Remediation:** integrate the Supabase JS auth client (login UI + session/refresh), and have it
supply the bearer token the API already accepts. This also resolves SEC-9 (token storage).

### [HIGH] INC-2 · Inspection media images won't load in JWT auth mode

**Files:** `frontend/src/api.ts:275-277`, `frontend/src/components/InspectionMediaViewer.tsx`, `backend/routers/media.py`

`mediaUrl()` returns a plain URL dropped into `<img src>` / `<video src>`. Browsers do **not**
attach the `Authorization` header to media element requests, so in `AUTH_MODE=jwt` every media
request hits `require_api_access` with no token → **401, broken images across the whole app**.
It works today only because dev runs `AUTH_MODE=disabled`. This will surface the instant auth is
turned on.

**Remediation:** issue short-lived signed media URLs (the Supabase backend already returns signed
URLs; extend the same pattern to local storage with an HMAC-signed, expiring query token that a
dedicated signature-checked route validates), or fetch media as a blob with the header and use
`URL.createObjectURL`.

### [MEDIUM] INC-3 · Multi-fleet users hard-fail with an unrecoverable 409

**Files:** `backend/security.py:85-89`, `frontend/src/*`

A user in more than one fleet gets `409 "set the X-Fleet-ID header"` on every request, but the
frontend never sends `X-Fleet-ID` and has no fleet-picker UI. Any multi-fleet user is fully
locked out. The backend contract is reasonable; the frontend half doesn't exist.

**Remediation:** add a fleet selector that persists the chosen fleet and sends `X-Fleet-ID` on
every request (the CORS config already allows the header).

### [MEDIUM] INC-4 · `severity="high"` accepted but comments claim it maps to `critical`

**Files:** `backend/models/db_models.py:211`, `backend/services/vision.py:68-74`, `backend/services/report_generator.py:25`

The detector emits `high`; the DB `ck_finding_severity` constraint allows `high`;
`report_generator` counts both `high` and `critical` as "critical"; but the model comment says
"accepts 'high' -> mapped to critical" — no such mapping happens, `high` is stored as-is. The
severity taxonomy (`low/medium/high/critical/clear`) is also muddier than the docs' four-color
model (Critical/Medium/Low/Clear).

**Remediation:** pick one taxonomy, enforce it at the write boundary, delete the misleading comment.

### [LOW] INC-5 · Avatar initials fallback is "CF", product is "Conditia"

`AuthProvider.initialsFor` returns `"CF"` (leftover from a prior name) as the avatar fallback.
Cosmetic, but visible.

### [LOW] INC-6 · Migrations run twice in dev / never in production start

`start.ps1` runs `alembic upgrade head`, and `lifespan` **also** runs migrations in non-production.
Harmless (idempotent) but confusing. In production `lifespan` skips migrations entirely, so a
production start via anything other than the Windows-only `start.ps1` never migrates. There is no
cross-platform/production start path at all (see SCALE-6).

---

## Part 4 — Startup scripts & CI reliability

You flagged that startup scripts "break a lot." Here's the root cause and the fix.

### Why `start.ps1` is fragile

- **It's a 168-line Windows-only recovery script** fighting the real root cause: `.venv` file
  locks from Cursor/uvicorn holding the Python DLL open on Windows. The `.venv` → `.venv2`
  fallback, `taskkill`, and `Get-CimInstance` process hunting are all symptom management. The
  clean fix is to **stop depending on a locked local venv** — run the backend in Docker (see
  SCALE-6 / pivot). That deletes ~150 lines of this script and the whole class of failure.
- **`taskkill /F /IM python.exe /T` kills every Python process on the machine**, not just
  Conditia's — it will also kill unrelated notebooks/scripts. Scope it to the marker match only.
- **Migration-failure advice prints a manual Supabase SQL-reset step** — a data-loss footgun if
  someone runs it against the wrong project.

### CI gaps (`.github/workflows/ci.yml`)

- **`pip_audit` runs against `requirements-dev.txt`, not `requirements.txt`.** The runtime
  dependency set is never audited in CI even though the README says to audit it. Add
  `pip_audit -r requirements.txt`.
- **No Postgres integration job.** All tests run on SQLite, so RLS (`0006`), TIMESTAMPTZ, asyncpg
  SSL, and the `verify-full` path are **never exercised**. The production database is completely
  untested. Add a job with a `postgres:16` service container.
- **Migrations only checked on SQLite.** Run `alembic upgrade head` + `check` against the Postgres
  service too.
- **No secret scanning** (gitleaks/trufflehog) — given SEC-5, add one so a real `.env`/DB can never
  be committed again.
- **`push` triggers `main` and `Shelton`** — a personal branch name baked into shared CI; likely
  wants a wildcard or just `pull_request`.
- Good: `permissions: contents: read` is correctly minimal.

---

## Part 5 — Scalability & infrastructure ceilings

### [HIGH] SCALE-1 · Analysis runs inside the API process via `BackgroundTasks`

**Files:** `backend/routers/inspections.py:241`, `backend/services/analysis_jobs.py`

`finalize` schedules `run_analysis_job` as a FastAPI background task in the web process. CPU-bound
OpenCV frame extraction and blocking Vision calls then compete with request handling. Under load,
one video analysis stalls API latency for every user on that instance. This is the #1
architectural limiter.

**Fix:** extract a standalone worker. The job table + lease design (`0007`) is already
worker-ready — you're ~80% there. Add a process that polls `analysis_jobs` with
`UPDATE … WHERE status='pending' … RETURNING` (or `FOR UPDATE SKIP LOCKED`), and have `finalize`
only enqueue. This lets the API scale independently of analysis capacity.

### [MEDIUM] SCALE-2 · Per-truck history recomputed on every inspection list

**File:** `backend/services/inspection_queries.py:44-58`

`build_inspection_summaries` loads the **entire inspection history for every truck referenced** on
each list request to compute "first detected N inspections ago", ordering it in Python. For a
truck with thousands of inspections, listing 25 recent ones pulls tens of thousands of rows —
O(history) per page view.

**Fix:** compute `first_detected_inspections_ago` at write time (store it on the finding), or use
a windowed SQL query bounded to the trucks on the current page (`ROW_NUMBER()` over inspections).

### [MEDIUM] SCALE-3 · Rate limiter & job ownership are per-process

`_rate_window` and the analysis `_OWNER` are in-process. The moment you run 2+ API instances,
rate limits become per-instance (N× the intended budget) and reclamation logic can't reason about
"running" jobs globally. Both need a shared store (Redis) or gateway-level enforcement before
horizontal scale.

### [MEDIUM] SCALE-4 · No cursor pagination — offset/limit capped at 100

All list endpoints cap at `limit=100` with no keyset pagination. Fleet managers with large
histories cannot page past the first 100 rows. Add keyset pagination (`started_at < last_seen`).

### [MEDIUM] SCALE-5 · SQLite as default dev DB hides Postgres-only behavior

Developing on SQLite means RLS, TIMESTAMPTZ, concurrent-writer locking, and `FOR UPDATE SKIP
LOCKED` are never seen until production. Combined with the CI gap, the first real test of the
production database is production. Run Postgres locally (Docker compose) as the default.

### [MEDIUM] SCALE-6 · No deployment artifact at all

No Dockerfile, no compose file, no worker entrypoint, no production process manager — the only
start path is a Windows PowerShell script. Before scaling anything you need a reproducible image
for (a) the API and (b) the worker, plus a deploy manifest. This also fixes the `start.ps1`
fragility class wholesale.

### [LOW] SCALE-7 · No media retention / lifecycle policy

Media accumulates forever; no TTL, archival tier, or per-fleet quota. Storage cost grows unbounded
for a product whose core action is "upload lots of photos/video." Define retention with a
legal-hold exception (relevant to the evidence pivot).

### [LOW] SCALE-8 · No explicit connection-pool sizing for the Supabase pooler

The async engine uses defaults. Through PgBouncer transaction mode you want a small, explicitly
sized pool (`statement_cache_size=0` is already set) to avoid exhausting pooler connections.

---

## Prioritized remediation plan

### Immediately (before any real customer data touches this)
1. **SEC-1** — enable DB TLS certificate verification (pin the Supabase CA).
2. **SEC-5** — untrack + purge the DB and media from git; rotate anything exposed.
3. **SEC-4** — blocklist the dev JWT secret in production; gate `mint_dev_token.py`.
4. **SEC-2** — require rate limiting in prod, cap the limiter's memory, key off the real client.

### This week
5. **INC-1 / INC-2** — wire real Supabase login + signed media URLs (the app is unusable in prod
   auth mode without these).
6. **SEC-3** — cap media per inspection and frames per video; add a per-fleet analysis budget.
7. **SEC-6** — add `resolved_by` + auth/membership/resolution audit logging.
8. **SCALE-1** — split analysis into a standalone worker (design already supports it).
9. **CI** — audit `requirements.txt`, add a Postgres integration job, add secret scanning.

### Scheduled (before multi-tenant GA)
10. **SEC-7, SEC-8, SEC-10, SEC-11, SEC-12, INC-3, INC-4**
11. **SCALE-2, SCALE-4, SCALE-5, SCALE-6** — history precompute, keyset pagination,
    Postgres-by-default dev, containerized deploy.
12. Remaining Low/Info items.

---

## Part 6 — Strategic direction / pivot ideas

The code is fine. The **strategic risk is that "AI damage detection" is the weakest, most
commoditized, and most legally fragile part of the product** — and the docs already admit the
detector is experimental and always needs human review. Lean away from it, not into it.

### The real moat is the timeline, not the detector
The business overview nails it: the defensible question is *"was this dent here last week?"* No
one buys "our AI finds dents" (Ravin, Tractable, UVeye, and every insurer's app already claim
that). People pay for **an immutable, timestamped, legally-defensible chain of custody for asset
condition**. That reframes the product from "computer vision" to **"evidence infrastructure."**

1. **Double down on chain-of-custody, drop the CV ambition.** Make the system of record
   bulletproof: hash media at upload, timestamp it, chain hashes per asset, keep a tamper-evident
   audit log, and export evidence packets a claims adjuster or court will accept. This is
   buildable now, needs no ML, and directly monetizes the liability-dispute pain that is the
   strongest part of the pitch. The audit-trail gaps (SEC-6) are literally step one of this pivot.

2. **Make change-detection deterministic before it's ML.** Today "first seen" matches on
   `(finding_type, zone)` — crude, and dependent on the flaky detector firing at all. A guided
   capture + human-confirm flow ("tap the new damage you see") produces cleaner, more defensible
   timeline data than an experimental label detector, at zero per-frame API cost. Use ML later as
   an *assist* to the human, not the source of truth.

3. **Sell the workflow, not the algorithm.** Guided walk-around + manager dashboard + exportable
   report is a complete product for check-in/check-out custody transfer (rental returns, yard
   hand-offs, driver shift changes, repair drop-off). That's a wedge you can charge for today with
   no detector at all.

4. **If you keep CV, make it a vendor-swappable commodity.** The `detector` abstraction is already
   clean — treat detection as a replaceable input (Google today, a specialist vendor or fine-tuned
   model later) and never let business logic depend on any one provider's output quality. Compete
   on the record, not the recognizer.

### One-line version
> Stop marketing an AI that finds damage. Start selling the **legally-defensible, timestamped
> condition record** the guided capture + timeline produces — that's the part competitors can't
> copy and that customers actually pay to settle disputes with.