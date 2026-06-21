# Conditia

The system of record for physical asset condition. Conditia turns footage of a
truck (today, captured on a phone) into a structured, timestamped damage report
with change-over-time tracking — proving not just *what* is damaged, but *when*
it first appeared and *who* is responsible.

Hardware-agnostic by design: phone capture today, drone / fixed-camera later,
all feeding the same backend pipeline with zero downstream changes.

## Monorepo layout

```
conditia/
├── frontend/        React + Vite + TypeScript fleet dashboard (Samsara-style)
│   └── src/
│       ├── components/   Sidebar, Topbar, StatCards, RecentInspections, DamageMap...
│       ├── api.ts        API client (proxied to backend in dev)
│       └── styles.css    Hand-authored design tokens (OKLCH) + components
├── backend/         FastAPI ingestion + analysis pipeline
└── .impeccable.md   Design context / brand direction
```

## Prerequisites

| Tool | Version |
|---|---|
| **Node.js** | 18+ |
| **Python** | 3.10+ (3.12 recommended) |

No Supabase, Postgres, or Google Cloud credentials are required for local dev.
The backend uses SQLite and on-disk media storage by default.

Check your versions:

```bash
node --version    # v18.x or higher
python3 --version # 3.10.x or higher
```

If `python3` is older than 3.10 (common on macOS), use a newer interpreter
explicitly — e.g. `python3.12` from Homebrew or Anaconda.

## First-time setup

Run these once after cloning the repo.

### 1. Backend

```bash
cd backend
python3 -m venv .venv
```

**macOS / Linux** — activate the venv and install deps:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Frontend

```bash
cd frontend
npm install
```

## Run the project

Start **both** services (use two terminals). The frontend dev server proxies
API calls to the backend on port **8001**.

**Terminal 1 — backend:**

```bash
cd backend
source .venv/bin/activate          # macOS / Linux
# .\.venv\Scripts\Activate.ps1     # Windows
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

**Terminal 2 — frontend:**

```bash
cd frontend
npm run dev
```

Then open:

| Service | URL |
|---|---|
| Dashboard | http://localhost:5173/ |
| API docs | http://127.0.0.1:8001/docs |
| Health check | http://127.0.0.1:8001/health |

Verify the backend is up:

```bash
curl http://127.0.0.1:8001/health
```

You should see `{"status":"ok", ...}`.

### First use

Demo seeding is **off by default**, so the dashboard starts with an empty fleet.
To try the full flow:

1. Open http://localhost:5173/
2. Click **New inspection**
3. Register a truck, capture footage, and upload
4. The dashboard updates live as the inspection completes

## Fresh start (reset local data)

To wipe the local SQLite database and uploaded media:

**macOS / Linux:**

```bash
cd backend
rm -f conditia.db
rm -rf storage
```

**Windows (PowerShell):**

```powershell
cd backend
Remove-Item conditia.db -ErrorAction SilentlyContinue
Remove-Item -Recurse storage -ErrorAction SilentlyContinue
```

Restart the backend afterward. See [backend/README.md](backend/README.md) for
API details, architecture, and production deployment notes.

## Design direction

Light, precise, instrument-like fleet-operations console in the spirit of
Samsara / Motive. See [.impeccable.md](.impeccable.md) for the full brand and
design context. Severity color is the only strong color and always carries
meaning (Critical = red, Medium = amber, Low = blue, Clear = green).

## Status

- [x] Fleet dashboard UI wired to live API (no mock inspection data)
- [x] Mobile capture flow with truck registration + upload to backend
- [x] FastAPI backend with adapter-pattern ingestion + SQLite (local)
- [ ] Real damage detection (Google Vision / YOLO — currently stubbed)
- [ ] Supabase production deploy
