# Conditia — Backend

FastAPI ingestion + analysis pipeline. Hardware-agnostic by design: every
capture source (mobile today; drone / fixed-camera later) implements one
adapter and flows through the identical analysis pipeline.

## Run it (zero external setup)

Defaults to local SQLite + on-disk media storage, so it runs with no Supabase,
no Google Cloud, no Postgres.

```powershell
cd C:\Users\yhail\Projects\conditia\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

- API docs (Swagger): http://localhost:8000/docs
- Health: http://localhost:8000/health
- On first start it seeds the demo "Midwest Freight Co." fleet (matches the dashboard).

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
pipeline runs anywhere; the seeded demo fleet provides realistic findings for
the dashboard. Real detection accuracy is the Phase 2/3 focus (see the technical
writeup).
