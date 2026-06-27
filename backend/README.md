# Conditia backend

FastAPI ingestion and analysis service. Mobile is the only registered ingestion
source. Other persisted source values are retained for compatibility with
historical/imported records, not as partially implemented adapters.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

- API docs: http://127.0.0.1:8001/docs
- Health: http://127.0.0.1:8001/health
- Database readiness: http://127.0.0.1:8001/ready
- Demo seeding: off unless `SEED_ON_STARTUP=true`

Copy `.env.example` to `.env` for overrides. Local development uses SQLite and
private on-disk storage rooted at `backend/storage`.

## Upload and analysis flow

```text
POST /inspections
  -> status=uploading
POST /inspections/{id}/upload (repeat as needed)
  -> verify signature and quota
  -> generate an opaque contained storage key
  -> persist media metadata; status remains uploading
POST /inspections/{id}/finalize
  -> status=submitted
  -> enqueue one analysis task
analysis claim
  -> submitted -> processing (atomic compare/update)
  -> frames -> detector -> change matching -> report
  -> complete | review_required | failed
```

The in-process background task is appropriate for local development. A durable
queue/outbox and isolated worker are still required for production retries and
crash recovery.

## Main endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/trucks` | Register a validated truck/VIN |
| GET | `/trucks` | List trucks (bounded and fleet-scoped) |
| POST | `/inspections` | Create an uploading inspection |
| POST | `/inspections/{id}/upload` | Upload verified media |
| POST | `/inspections/{id}/finalize` | Submit once for analysis |
| GET | `/inspections` | Bounded inspection summaries |
| GET | `/inspections/{id}` | Inspection, findings, and media |
| GET | `/reports/{inspection_id}` | Structured report, when generated |

## Security configuration

Development defaults to `AUTH_MODE=disabled`. Production requires:

```dotenv
ENVIRONMENT=production
AUTH_MODE=api_key
API_KEY=<at-least-32-random-characters>
API_FLEET_ID=<fleet UUID assigned to this deployment>
STORAGE_BACKEND=supabase
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<server-side service role key>
SUPABASE_STORAGE_BUCKET=inspection-media
DOCS_ENABLED=false
CORS_ORIGINS=https://fleet.example.com
```

Clients send the perimeter key as `X-API-Key`. This mode scopes data queries to
one configured fleet, but does not provide per-user identity or roles. Put a
fleet-aware identity gateway in front of the service before multi-tenant use.
Production uses a private object bucket and short-lived authorized redirects;
the application no longer exposes a static storage-directory mount.

Uploads are signature checked, server-renamed, path-contained, streamed on a
worker thread, and bounded by `MAX_UPLOAD_BYTES` and
`MAX_FILES_PER_UPLOAD`. Gateway-level request/rate limits are still required.

## Database and migrations

The ORM and initial Alembic migration contain application constraints. Verify a
fresh database with:

```bash
DATABASE_URL=sqlite+aiosqlite:////tmp/conditia.db alembic upgrade head
DATABASE_URL=sqlite+aiosqlite:////tmp/conditia.db alembic check
```

For an existing pre-Alembic database, back it up and review/stamp/migrate it
explicitly; do not blindly run the initial migration over existing tables. The
prototype compatibility path is `alembic stamp 0001_initial` followed by
`alembic upgrade head` after the backup and schema have been verified.
Revision `0003_normalize_sqlite_uuids` also normalizes prototype SQLite
UUID text without deleting rows so ORM relationships continue to resolve.
`db/schema.sql` includes the additional Supabase membership/RLS policies.

## Analysis integrity

No detector or decoder failure is converted into a clear report. Missing
capability and experimental Google label detection produce `review_required`.
The Google integration is only a triage signal: its confidence is retained, but
its provisional severity requires human review. A validated damage model,
calibrated severity policy, and durable job infrastructure remain production
prerequisites.
