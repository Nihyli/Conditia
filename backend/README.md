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

## Going to production (Supabase)

1. Run `db/schema.sql` in the Supabase SQL editor.
2. Set `DATABASE_URL=postgresql+asyncpg://...` and uncomment `asyncpg` in `requirements.txt`.
3. (Optional) Set `GOOGLE_APPLICATION_CREDENTIALS` + uncomment `google-cloud-vision`
   to switch detection from stub to real, and `opencv-python-headless` for video frames.
4. Swap `LocalStorageService` for a Supabase Storage implementation (same interface).

Detection is intentionally stubbed by default (returns no findings) so the full
pipeline runs anywhere. Real detection accuracy is the Phase 2/3 focus.
