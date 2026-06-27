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

## Signing in

By default auth is off (`AUTH_MODE=disabled` in `backend/.env`). The dashboard
loads with no login screen. That's fine for local UI work.

Turn auth on when you want to test fleet scoping, roles, or the sign-in flow.

### JWT mode (local)

**1. Configure the backend**

Copy the example env if you haven't already:

```bash
cd backend
cp .env.example .env
```

Add or uncomment:

```dotenv
AUTH_MODE=jwt
JWT_SECRET=conditia-local-dev-jwt-secret-change-me-32chars
```

The secret has to match what you use to mint tokens. The dev script prints the
same default if you don't set one.

**2. Apply migrations and mint a token**

Still in `backend/` with the venv active:

```bash
alembic upgrade head
python scripts/mint_dev_token.py
```

The script creates a dev user (`driver@conditia.local`), links them to your demo
fleet as an `inspector`, and prints a long string starting with `eyJ`. That's
your access token. It lasts 24 hours.

You only need the token itself — not the `export CONDITIA_TOKEN=…` wrapper.
The sign-in page strips that if you paste the whole line.

**3. Restart the API**

Uvicorn only reads `.env` on startup. If you changed auth settings, kill it
and start again:

```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

**4. Sign in on the frontend**

Open http://127.0.0.1:5173, paste the token, hit **Open dashboard**.

Quick sanity check from a terminal:

```bash
# no token → 401
curl -s http://127.0.0.1:8001/auth/me

# with token → your user id, fleet id, role
curl -s -H "Authorization: Bearer <paste-eyJ-token-here>" http://127.0.0.1:8001/auth/me
```

### When sign-in breaks

| What you see | Likely cause |
|---|---|
| Login page but token "doesn't verify" | Backend still on `AUTH_MODE=disabled`, or `JWT_SECRET` doesn't match |
| Login page immediately, no error | Old uvicorn process — no `/auth/me` route. Restart the backend |
| Dashboard at `:8001` instead of UI | Wrong URL. Frontend is **:5173**, API is **:8001** |
| Worked yesterday, not today | Token expired. Run `mint_dev_token.py` again |

To go back to no-auth dev, set `AUTH_MODE=disabled` and restart uvicorn.

Production uses Supabase-issued JWTs and `fleet_memberships` rows — see
[backend/README.md](backend/README.md#security-configuration).

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
.venv/bin/python -m pytest -q --cov --cov-report=term-missing --cov-fail-under=80
.venv/bin/pip-audit -r requirements.txt

cd ../frontend
npm run test:coverage
npm run build
npm audit --omit=dev
```

CI runs the same checks and verifies the Alembic migration chain. Coverage gates
are intentionally risk-based rather than test-count based: backend total coverage
must remain at least 80%; frontend statements/branches/functions/lines must remain
at least 85/75/80/90 percent. Add behavior-focused tests when changing a boundary
or business rule instead of creating shallow assertions to inflate the count.

## Production boundary

Production refuses to start with auth disabled or local file storage. User
sessions go through JWT (`AUTH_MODE=jwt`); roles come from `fleet_memberships`,
not the token payload alone. `api_key` mode remains for scripts — don't put that
key in the frontend.

Don't ship this as a public multi-tenant app until RLS is in Alembic, analysis
runs on a real worker queue, and the damage model is validated. Details in
[data/AGENT_CODE_REVIEW.md](data/AGENT_CODE_REVIEW.md).

See [backend/README.md](backend/README.md) for API/configuration details and
[data/AGENT_CODE_REVIEW.md](data/AGENT_CODE_REVIEW.md) for the original review.
