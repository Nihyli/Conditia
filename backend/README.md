# Conditia — Backend

FastAPI ingestion + analysis pipeline. Hardware-agnostic by design: every
capture source (mobile today; drone / fixed-camera later) implements one
adapter and flows through the identical analysis pipeline.

## Prerequisites

- **Python 3.10+** (3.12 recommended). Python 3.9 will not work — the codebase
  uses modern type syntax (`str | None`, etc.).

## First-time setup

Defaults to local SQLite + on-disk media storage — no Supabase, Google Cloud,
or Postgres required.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .\.venv\Scripts\Activate.ps1     # Windows
pip install -r requirements.txt
```

On Windows you can also use `.\start.ps1`, which creates the venv if needed and
starts the API on port 8001.

## Run it

```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

The frontend dev server proxies `/api` → `http://127.0.0.1:8001`, so the backend
**must** listen on port **8001** during local development.

- API docs (Swagger): http://127.0.0.1:8001/docs
- Health: http://127.0.0.1:8001/health

Demo seeding is **off by default** (`seed_on_startup: false` in config). Set
`SEED_ON_STARTUP=true` in a `.env` file to load the demo "Midwest Freight Co."
fleet on startup.

## Architecture

```
adapters/      base.py (abstract) + mobile.py (MVP) + drone.py (Phase 5 stub)
services/      storage, vision (Google Vision optional / stubbed), analysis
               pipeline, change_detection, report_generator
routers/       trucks, inspections, findings, reports
models/        db_models.py (SQLAlchemy ORM) + schemas.py (Pydantic)
db/schema.sql  canonical Postgres/Supabase DDL for production
```

### Upload flow (the MVP slice)

```
POST /inspections/{id}/upload  (multipart: files, capture_angle, capture_source)
  -> adapter.receive_media() stores media          (MobileAdapter -> disk)
  -> inspection_media rows written
  -> background task: analyze_inspection()
       extract frames -> detect_damage -> change detection
       -> findings written -> report generated -> status=complete
```

## Key endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/trucks` | Register a truck |
| GET  | `/trucks/{id}/inspections` | Truck inspection history |
| POST | `/inspections` | Start an inspection |
| POST | `/inspections/{id}/upload` | Upload media (any capture source) |
| GET  | `/inspections` | Recent inspections (dashboard feed) |
| GET  | `/inspections/{id}` | Inspection + findings (damage map) |
| GET  | `/inspections/{id}/report` | Generated report |

## Database: SQLite (dev) → Supabase Postgres

The app runs on SQLite by default and on Supabase Postgres when `DATABASE_URL`
points at one. The same SQLAlchemy models drive both — IDs are stored as text
UUIDs and timestamps are timezone-aware, so no per-dialect code is needed.

### Switching to Supabase Postgres

1. `pip install -r requirements.txt` (now includes `asyncpg`).
2. In Supabase → **Project Settings → Database**, copy a connection string and
   set it as `DATABASE_URL` in `backend/.env`. Any standard format works — the
   app rewrites it to the asyncpg driver and enables TLS automatically:
   - **Session pooler** (recommended for dev): host `...pooler.supabase.com`, port `5432`.
   - **Direct**: `db.<ref>.supabase.co:5432` (requires IPv6).
   - **Transaction pooler**: port `6543` — also append `?prepared_statement_cache_size=0`.
3. Verify connectivity and create the tables:
   ```bash
   python check_db.py        # prints server + row counts, runs create_all
   ```
4. (Optional) Seed the demo fleet into Postgres: `python seed.py --force`.

Tables are created automatically on startup via SQLAlchemy `create_all`, so
running `db/schema.sql` by hand is **optional** — that file is the canonical
native-typed DDL (UUID/JSONB/enum/CHECK) kept for reference and RLS setup.

Auth still works the same on Postgres: keep `AUTH_PROVIDER=local` for the demo
accounts (re-seeded on first startup), or set `AUTH_PROVIDER=supabase` to
validate Supabase-issued JWTs instead.

## Other production switches

- Set `GOOGLE_APPLICATION_CREDENTIALS` + add `google-cloud-vision` to switch
  detection from stub to real, and `opencv-python-headless` for video frames.
- Swap `LocalStorageService` for a Supabase Storage implementation (same interface).

Detection is intentionally stubbed by default (returns no findings) so the full
pipeline runs anywhere. Real detection accuracy is the Phase 2/3 focus.
