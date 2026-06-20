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
│       ├── data.ts       Mock fleet data (until backend is wired)
│       └── styles.css    Hand-authored design tokens (OKLCH) + components
├── backend/         FastAPI ingestion + analysis pipeline (scaffolded next)
└── .impeccable.md   Design context / brand direction
```

## Frontend — run it

> Requires Node 18+.

```bash
cd frontend
npm install
npm run dev
```

Then open the printed local URL. The dashboard currently runs on mock data
(`src/data.ts`) so it renders fully without the backend.

## Design direction

Light, precise, instrument-like fleet-operations console in the spirit of
Samsara / Motive. See [.impeccable.md](.impeccable.md) for the full brand and
design context. Severity color is the only strong color and always carries
meaning (Critical = red, Medium = amber, Low = blue, Clear = green).

## Status

- [x] Fleet dashboard UI (Fleet Overview: KPIs, recent inspections, damage map, findings)
- [ ] Backend: FastAPI + adapter-pattern ingestion + Supabase
- [ ] Mobile capture flow (6-angle guided walk-around)
- [ ] Analysis pipeline (frame extraction + damage detection + change detection)
