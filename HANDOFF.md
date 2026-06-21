# Conditia — Agent Handoff Document

**Last updated:** 2026-06-20  
**Project path:** `C:\Users\yhail\Projects\conditia`  
**Product:** Conditia (`conditia.ai`) — hardware-agnostic asset condition intelligence. Trucking MVP first; phone capture → upload → dashboard with damage reports and change-over-time tracking.

---

## 1. Executive summary

Conditia is a monorepo with a **React/Vite frontend** (Samsara-style fleet console) and **FastAPI backend** (SQLite dev, Supabase-ready). Core flows work: mobile walk-around capture, inspection upload, fleet dashboard with KPIs, sidebar views, damage map, seed/unseed, and **role-based auth** (local JWT + Supabase Auth scaffold).

**Not production-ready yet:** real damage detection is stubbed, media sync can be flaky, Supabase Postgres not wired (only Auth creds in `.env`), PDF export is UI-only.

---

## 2. Git & branches

| Branch | Notes |
|--------|--------|
| `main` | Stable-ish; has `supabase auth` commit (`adc37cb`) |
| `Dev` | Active dev branch; latest commit `9e8bf46` — "Truck sillohete upgrade" |
| `origin/Dev`, `origin/main`, `origin/Shelton` | Remotes exist |

**Check for uncommitted work** before assuming handoff matches git:
```powershell
cd C:\Users\yhail\Projects\conditia
git status
git branch
```

Recent session work (damage map zone fixes, cab red tint, login token race fix) may exist **only on disk** if not committed after `9e8bf46`.

`.env` is gitignored — never commit `backend/.env` (contains Supabase secrets).

---

## 3. How to run (Windows)

### Backend (port **8001** — not 8000)

Port 8000 had a **zombie process** serving an old API without `fleet_stats`, `media`, etc. Standard workaround: run on **8001**.

```powershell
cd C:\Users\yhail\Projects\conditia\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # PyJWT, bcrypt (NOT passlib — removed)
python -m auth.seed_users         # demo login accounts (if empty)
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

Verify:
```powershell
Invoke-RestMethod http://127.0.0.1:8001/health | ConvertTo-Json
# Expect: version 0.2.0, auth_enabled, auth_provider
```

### Frontend

```powershell
cd C:\Users\yhail\Projects\conditia\frontend
npm install
npm run dev
# http://localhost:5173 — proxies /api → http://127.0.0.1:8001
```

---

## 4. Seeding data

### Demo users (local auth)

Auto-seeded on backend startup if `users` table empty.

```powershell
python -m auth.seed_users
```

| Email | Password | Role |
|-------|----------|------|
| admin@conditia.ai | demo1234 | admin |
| manager@conditia.ai | demo1234 | fleet_manager |
| inspector@conditia.ai | demo1234 | inspector |
| viewer@conditia.ai | demo1234 | viewer |

### Demo fleet (Midwest Freight Co. — 5 trucks, sample findings)

- **UI:** Login as admin → Settings → Seed demo data / Replace with demo data  
- **CLI:** `python seed.py` or `python seed.py --force`  
- **API:** `POST /admin/seed?force=true` (admin JWT required)

### Media backfill (files on disk but not in DB)

```powershell
python sync_storage.py
```

Storage layout: `backend/storage/{inspection-uuid}/{angle}/{file.webm}`

---

## 5. Auth architecture

### Modes (`AUTH_PROVIDER` in `backend/.env`)

| Value | Behavior |
|-------|----------|
| `local` | Email/password via `POST /auth/login`, JWT signed with `JWT_SECRET` |
| `supabase` | Frontend uses `@supabase/supabase-js`; backend validates Supabase JWT |
| `auto` (default) | Supabase if `SUPABASE_URL` + `SUPABASE_JWT_SECRET` + `SUPABASE_ANON_KEY`; else local |

**User's current setup:** Supabase credentials exist in `backend/.env`, but **`AUTH_PROVIDER=local`** was added so demo accounts work. Supabase Auth users are **not** the same as local demo users.

### Roles & permissions

| Role | Dashboard | Capture | Create trucks | Settings | Admin seed/unseed |
|------|-----------|---------|---------------|----------|-------------------|
| admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| fleet_manager | ✓ | ✓ | ✓ | ✓ (no data admin) | ✗ |
| inspector | ✓ | ✓ | ✗ | ✗ | ✗ |
| viewer | ✓ read-only | ✗ | ✗ | ✗ | ✗ |

### Frontend auth files

- `frontend/src/auth/AuthContext.tsx` — login, token sync (uses `setAuthToken` for immediate API calls)
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/auth/ProtectedRoute.tsx`
- `frontend/src/api.ts` — attaches `Authorization: Bearer`

### Known auth fixes applied (session)

1. **passlib + bcrypt** removed → direct `bcrypt` (passlib breaks on bcrypt 4.1+)
2. **Login race:** token set synchronously before `/auth/me`; local login uses response user directly
3. **Supabase vs local mismatch:** error "Use Supabase Auth on the client…" when backend is supabase mode but frontend calls `/auth/login`

---

## 6. Supabase status

| Component | Status |
|-----------|--------|
| Auth credentials in `.env` | ✓ Present (project ref `kjbbocoohedltrctpxdt`) |
| Supabase Auth login | Not primary — `AUTH_PROVIDER=local` for dev |
| Supabase Postgres (`DATABASE_URL`) | ✗ Still SQLite |
| `db/schema.sql` on Supabase | ✗ Not applied yet |
| Supabase Storage for media | ✗ Still local disk |

**Recommended next infra step:** Run `backend/db/schema.sql` in Supabase SQL editor, set `DATABASE_URL=postgresql+asyncpg://...`, uncomment `asyncpg` in requirements, set `AUTH_PROVIDER=supabase`, create users in Supabase dashboard with `app_metadata.role`.

---

## 7. Architecture map

```
conditia/
├── frontend/          React 18 + Vite + TS + react-router-dom
│   ├── src/pages/     DashboardPage, CapturePage, LoginPage
│   ├── src/views/     TrucksView, FindingsView, SettingsView, PlaceholderView
│   ├── src/components/ Sidebar, Topbar, DamageMap, StatCards, ...
│   ├── src/auth/      AuthContext, ProtectedRoute, types
│   └── vite.config.ts proxy /api → :8001
├── backend/
│   ├── main.py        FastAPI v0.2.0, lifespan seeds users
│   ├── auth/          JWT, bcrypt, roles, dependencies, seed_users
│   ├── routers/       auth, admin, fleet, trucks, inspections, findings, reports
│   ├── models/        SQLAlchemy ORM + Pydantic schemas
│   ├── services/      analysis, vision (STUB), media_sync, storage
│   ├── seed.py        Demo fleet + seed/unseed/clear
│   ├── sync_storage.py
│   └── db/schema.sql  Production Postgres DDL
└── .impeccable.md     Design context (light/precise, Samsara-style)
```

### Key API routes

| Route | Auth | Notes |
|-------|------|-------|
| `GET /health` | Public | version, auth_provider |
| `GET /auth/config` | Public | provider, supabase keys for client |
| `POST /auth/login` | Public | local only |
| `GET /auth/me` | JWT | |
| `GET /fleet/stats` | JWT | |
| `GET /inspections` | JWT | includes `media[]`, `findings[]` |
| `POST /inspections/{id}/upload` | JWT inspector+ | |
| `POST /admin/seed`, `/admin/unseed` | JWT admin | |

---

## 8. Frontend routing

| Path | Component | Guard |
|------|-----------|-------|
| `/login` | LoginPage | Public |
| `/` | DashboardPage | ProtectedRoute |
| `/capture`, `/capture/:truckId` | CapturePage | ProtectedRoute + requireCapture |

Dashboard **sidebar nav is state-based** (`activeNav` in DashboardPage), not URL routes: overview, trucks, inspections, findings, reports, history, samsara, settings.

---

## 9. Damage map — zones & rendering

**File:** `frontend/src/components/DamageMap.tsx`  
**Component:** `TruckSilhouette` — side-profile SVG (viewBox `560×210`), user-designed cab with clip path, fifth wheel, exhaust, headlight, etc.

### Display zones (4 rects + cab shape)

| Display | API zones mapped | Tint area |
|---------|------------------|-----------|
| rear | `trailer_rear` | Rear trailer box |
| side | `trailer_mid`, `passenger_side`, `driver_side` | Mid trailer |
| front | `trailer_front` | Trailer nose (near fifth wheel) |
| cab | `cab`, **`front`** | Cab body path |

**Important:** API zone `front` = **cab front** (bumper, headlight, grille), NOT trailer nose.

### Marker positions (`ZONE_MARKER`)

| API zone | Marker ~position |
|----------|------------------|
| trailer_rear | (60, 105) |
| trailer_mid | (194, 105) |
| trailer_front | (318, 105) |
| **front** | **(520, 122)** — headlight |
| cab | (400, 100) |
| passenger_side | (150, 105) |
| driver_side | (230, 105) |

### Severity rendering

- Trailer zones: colored `rect` with fill + stroke
- Cab: cab **path** uses `sevFill`/`sevColor` directly (fix: was gray fill covering red tint)
- Headlight rect: highlights when zone=`front` has a finding
- Markers: one per API zone (worst severity if multiple)

### Known seed data imprecision

- TRK-017 "Tire sidewall wear" uses zone `front` but should be wheels — marker wrongly at headlight
- Consider adding `wheel` zone + updating `backend/seed.py`

---

## 10. Backend domain model

**SQLite DB:** `backend/conditia.db` (path via `backend/paths.py`)

Tables: `fleets`, `trucks`, `users`, `inspections`, `inspection_media`, `findings`, `reports`

**Vision/detection:** `backend/services/vision.py` returns **no findings** unless Google Vision configured. Demo findings come from **seed data only**.

**Media sync:** `services/media_sync.py` + `sync_storage.py` backfill `inspection_media` from disk.

---

## 11. Environment variables (backend)

See `backend/.env.example`. Critical ones:

```env
DATABASE_URL=sqlite+aiosqlite:///...
STORAGE_DIR=C:/Users/yhail/Projects/conditia/backend/storage
AUTH_ENABLED=true
AUTH_PROVIDER=local          # or auto | supabase
JWT_SECRET=...
ADMIN_ENABLED=true
SEED_ON_STARTUP=false

# Supabase (user has these set — do not commit)
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_JWT_SECRET=...
```

---

## 12. Known issues & war stories

1. **Zombie on :8000** — old backend without v0.2.0 features; always use **8001** + Vite proxy
2. **passlib + bcrypt** — broken; use `bcrypt` directly in `auth/passwords.py`
3. **Media not showing** — DB rows missing; run `sync_storage.py` or `POST /inspections/{id}/sync-media`
4. **Login "Use Supabase Auth…"** — backend supabase mode + frontend local login; set `AUTH_PROVIDER=local` or wire Supabase client login
5. **Agent shell** — often returned empty output in Cursor; user runs commands locally
6. **Damage map** — cab tint was hidden under gray fill (fixed in session); verify committed

---

## 13. Recommended next steps (priority)

1. **Commit uncommitted session work** to `Dev` (damage map zone fixes, auth fixes if not in git)
2. **Verify happy path:** login → seed fleet → capture → upload → media + findings on dashboard
3. **Supabase Postgres migration** — schema.sql, DATABASE_URL, asyncpg
4. **Supabase Auth for shared dev** — create real users, `AUTH_PROVIDER=supabase`
5. **Media pipeline hardening** — always write `inspection_media` on upload
6. **Real detection** — Google Vision or YOLO in `vision.py`
7. **Fix seed zones** — tire → wheel zone; audit all demo findings
8. **PDF export** — wire Export PDF button
9. **Deploy** — frontend static + backend container + Supabase

---

## 14. Key files quick index

| Area | Path |
|------|------|
| Damage map | `frontend/src/components/DamageMap.tsx` |
| Dashboard + sidebar | `frontend/src/pages/DashboardPage.tsx` |
| Auth context | `frontend/src/auth/AuthContext.tsx` |
| API client | `frontend/src/api.ts` |
| Vite proxy | `frontend/vite.config.ts` |
| FastAPI app | `backend/main.py` |
| Config | `backend/config.py` |
| Seed fleet | `backend/seed.py` |
| Seed users | `backend/auth/seed_users.py` |
| Admin API | `backend/routers/admin.py` |
| Inspections/upload | `backend/routers/inspections.py` |
| Production schema | `backend/db/schema.sql` |
| Design tokens | `frontend/src/styles.css` |

---

## 15. User context

- **OS:** Windows 10/11, PowerShell
- **Git user:** Yohannes (yhailu006@gmail.com)
- **Prefers:** Samsara-style light fleet UI, Conditia branding (not VisionFleet)
- **Workspace rule:** Project lives at `C:\Users\yhail\Projects\conditia`; use `Dev` branch for active work

---

## 16. Transcript reference

Full conversation transcript for this build session:  
`C:\Users\yhail\.cursor\projects\empty-window\agent-transcripts\ca24d0a9-6eb3-47f2-bb32-e74a00d4bf43\ca24d0a9-6eb3-47f2-bb32-e74a00d4bf43.jsonl`

Search keywords: `seed`, `auth`, `Supabase`, `DamageMap`, `8001`, `login`, `TruckSilhouette`, `AUTH_PROVIDER`.

---

*End of handoff — start next session by reading this file + `git status` + hitting `/health` on :8001.*
