# Conditia

Conditia records the physical condition of fleet assets from guided phone
captures. The current repository contains a React/Vite dashboard and a FastAPI
ingestion/analysis backend.

## Repository layout

```text
frontend/  React, TypeScript, Vite dashboard and guided capture flow
backend/   FastAPI, Pydantic, async SQLAlchemy, SQLite/PostgreSQL
data/      Engineering guidance and production-readiness review
```

## Local setup

Prerequisites: Node.js 22.12+ and Python 3.10+.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to the backend on port 8001.
Swagger is available at http://127.0.0.1:8001/docs in development.

Demo seeding is disabled by default. Set `SEED_ON_STARTUP=true` in
`backend/.env` only when synthetic demo data is wanted.

## Inspection lifecycle

1. Register a truck and create an inspection (`uploading`).
2. Upload one or more verified image/video files. Uploading does not analyze.
3. Finalize once (`submitted`).
4. The analysis worker atomically claims the inspection (`processing`).
5. The result becomes `complete`, `review_required`, or `failed`.

With no configured detector/video decoder, the result is `review_required`—the
system never reports an unanalyzed inspection as clear. Google label detection
is experimental and also requires human review.

## Verification

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/pip-audit -r requirements.txt

cd ../frontend
npm test
npm run build
npm audit --omit=dev
```

CI runs the same checks and verifies the initial Alembic migration.

## Production boundary

Production configuration refuses to start with authentication disabled, a
missing fleet scope, or local storage. The current
API-key mode is a service perimeter scoped to one fleet; it is not a substitute
for user-level identity, roles, audit logs, or a production object-storage
adapter. Do not deploy this as a public multi-tenant application until those
remaining boundaries and a validated damage model are implemented.

See [backend/README.md](backend/README.md) for API/configuration details and
[data/AGENT_CODE_REVIEW.md](data/AGENT_CODE_REVIEW.md) for the original review.
