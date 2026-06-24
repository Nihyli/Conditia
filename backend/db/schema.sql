-- Conditia — canonical native-typed reference DDL for Supabase / PostgreSQL.
--
-- NOTE: The application creates all tables automatically on startup via
-- SQLAlchemy create_all (text UUIDs + timezone-aware timestamps), so you do NOT
-- need to run this file to bring the app up on Postgres — just set DATABASE_URL.
-- This script is kept as the reference for a fully native schema (UUID / JSONB /
-- enum / CHECK constraints) and as the place to layer RLS policies. Applying it
-- and letting the ORM also manage tables would create type mismatches, so pick
-- one approach per database.
--
-- Hardware-agnostic by design: capture_source is the only place the system
-- records what collected the footage.

-- Fleet accounts
CREATE TABLE IF NOT EXISTS fleets (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- Trucks registered to a fleet
CREATE TABLE IF NOT EXISTS trucks (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fleet_id      UUID REFERENCES fleets(id),
  vin           TEXT UNIQUE NOT NULL,
  make          TEXT,
  model         TEXT,
  year          INTEGER,
  license_plate TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Each inspection event.
-- capture_source: 'mobile' for MVP. 'drone' / 'fixed_camera' are valid future
-- values requiring no schema changes.
CREATE TABLE IF NOT EXISTS inspections (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  truck_id       UUID REFERENCES trucks(id),
  started_at     TIMESTAMPTZ DEFAULT now(),
  completed_at   TIMESTAMPTZ,
  status         TEXT CHECK (status IN ('pending','processing','complete','failed')),
  capture_source TEXT CHECK (capture_source IN ('mobile','drone','fixed_camera','manual'))
                 DEFAULT 'mobile',
  created_by     UUID
);

-- Raw media captured during an inspection.
-- drone_flight_id is NULL for mobile captures; populated automatically for
-- drone captures in Phase 5 — no migration needed.
CREATE TABLE IF NOT EXISTS inspection_media (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id   UUID REFERENCES inspections(id),
  media_type      TEXT CHECK (media_type IN ('photo','video')),
  capture_angle   TEXT CHECK (capture_angle IN (
                    'front','rear','driver_side',
                    'passenger_side','top','undercarriage')),
  capture_source  TEXT DEFAULT 'mobile',
  drone_flight_id TEXT,
  storage_path    TEXT NOT NULL,
  captured_at     TIMESTAMPTZ DEFAULT now(),
  gps_lat         DOUBLE PRECISION,
  gps_lng         DOUBLE PRECISION
);

-- Individual damage findings from the analysis pipeline.
-- first_seen_inspection_id enables change detection — tracks when each finding
-- was first observed on this truck across all past inspections.
CREATE TABLE IF NOT EXISTS findings (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id            UUID REFERENCES inspections(id),
  media_id                 UUID REFERENCES inspection_media(id),
  title                    TEXT,
  finding_type             TEXT CHECK (finding_type IN (
                             'dent','scratch','crack',
                             'missing_component','rust','anomaly')),
  severity                 TEXT CHECK (severity IN ('low','medium','high','critical','clear')),
  confidence               DOUBLE PRECISION,
  zone                     TEXT,
  location                 TEXT,
  bounding_box             JSONB,
  description              TEXT,
  annotated_image_path     TEXT,
  first_seen_inspection_id UUID REFERENCES inspections(id)
);

-- Final report generated per inspection
CREATE TABLE IF NOT EXISTS reports (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id     UUID REFERENCES inspections(id),
  generated_at      TIMESTAMPTZ DEFAULT now(),
  summary           TEXT,
  total_findings    INTEGER,
  critical_findings INTEGER,
  pdf_path          TEXT,
  raw_json          JSONB
);

CREATE INDEX IF NOT EXISTS idx_inspections_truck ON inspections(truck_id);
CREATE INDEX IF NOT EXISTS idx_media_inspection ON inspection_media(inspection_id);
CREATE INDEX IF NOT EXISTS idx_findings_inspection ON findings(inspection_id);
CREATE INDEX IF NOT EXISTS idx_findings_truck_lookup ON findings(finding_type, zone);

-- ---------------------------------------------------------------------------
-- Auth / users (local dev + Supabase profile mirror)
-- ---------------------------------------------------------------------------

CREATE TYPE app_role AS ENUM ('admin', 'fleet_manager', 'inspector', 'viewer');

CREATE TABLE IF NOT EXISTS users (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email          TEXT UNIQUE NOT NULL,
  password_hash  TEXT,
  full_name      TEXT,
  role           app_role NOT NULL DEFAULT 'viewer',
  fleet_id       UUID REFERENCES fleets(id),
  auth_provider  TEXT NOT NULL DEFAULT 'local',
  created_at     TIMESTAMPTZ DEFAULT now()
);

-- Link inspections to the user who created them.
ALTER TABLE inspections
  ADD CONSTRAINT inspections_created_by_fkey
  FOREIGN KEY (created_by) REFERENCES users(id);
