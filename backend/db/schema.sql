-- Conditia — production schema for Supabase / PostgreSQL.
-- Local dev uses SQLAlchemy create_all on SQLite; this file is the canonical
-- production DDL. Hardware-agnostic by design: capture_source is the only place
-- the system records what collected the footage.

-- Fleet accounts
CREATE TABLE IF NOT EXISTS fleets (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Supabase Auth users are assigned to fleets by a trusted backend/service role.
CREATE TABLE IF NOT EXISTS fleet_memberships (
  fleet_id UUID NOT NULL REFERENCES fleets(id) ON DELETE CASCADE,
  user_id  UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role     TEXT NOT NULL CHECK (role IN ('viewer','inspector','admin')),
  PRIMARY KEY (fleet_id, user_id)
);

-- Trucks registered to a fleet
CREATE TABLE IF NOT EXISTS trucks (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fleet_id      UUID REFERENCES fleets(id) ON DELETE RESTRICT,
  vin           TEXT UNIQUE NOT NULL,
  make          TEXT,
  model         TEXT,
  year          INTEGER,
  license_plate TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (year IS NULL OR year >= 1900)
);

-- Each inspection event.
-- capture_source: 'mobile' for MVP. 'drone' / 'fixed_camera' are valid future
-- values requiring no schema changes.
CREATE TABLE IF NOT EXISTS inspections (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  truck_id       UUID NOT NULL REFERENCES trucks(id) ON DELETE CASCADE,
  started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at   TIMESTAMPTZ,
  status         TEXT NOT NULL CHECK (status IN (
                   'uploading','submitted','processing','complete','review_required','failed'
                 )) DEFAULT 'uploading',
  capture_source TEXT CHECK (capture_source IN ('mobile','drone','fixed_camera','manual'))
                 NOT NULL DEFAULT 'mobile',
  created_by     UUID
);

-- Raw media captured during an inspection.
-- drone_flight_id is NULL for mobile captures; populated automatically for
-- drone captures in Phase 5 — no migration needed.
CREATE TABLE IF NOT EXISTS inspection_media (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id   UUID NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
  media_type      TEXT NOT NULL CHECK (media_type IN ('photo','video')),
  capture_angle   TEXT CHECK (capture_angle IN (
                    'front','rear','driver_side',
                    'passenger_side','top','undercarriage')),
  capture_source  TEXT NOT NULL CHECK (capture_source IN (
                    'mobile','drone','fixed_camera','manual'
                  )) DEFAULT 'mobile',
  drone_flight_id TEXT,
  storage_path    TEXT UNIQUE NOT NULL,
  captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  gps_lat         DOUBLE PRECISION,
  gps_lng         DOUBLE PRECISION,
  CHECK (gps_lat IS NULL OR gps_lat BETWEEN -90 AND 90),
  CHECK (gps_lng IS NULL OR gps_lng BETWEEN -180 AND 180)
);

-- Durable analysis dispatch. One finalized inspection creates one job.
CREATE TABLE IF NOT EXISTS analysis_jobs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id UUID UNIQUE NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
  status        TEXT NOT NULL CHECK (status IN ('pending','running','complete','failed'))
                DEFAULT 'pending',
  attempts      INTEGER NOT NULL DEFAULT 0,
  last_error    TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Individual damage findings from the analysis pipeline.
-- first_seen_inspection_id enables change detection — tracks when each finding
-- was first observed on this truck across all past inspections.
CREATE TABLE IF NOT EXISTS findings (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id            UUID NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
  media_id                 UUID REFERENCES inspection_media(id) ON DELETE SET NULL,
  title                    TEXT,
  finding_type             TEXT NOT NULL CHECK (finding_type IN (
                             'dent','scratch','crack',
                             'missing_component','rust','anomaly')),
  severity                 TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical','clear')),
  confidence               DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  status                   TEXT NOT NULL CHECK (status IN (
                             'open','acknowledged','resolved','false_positive'
                           )) DEFAULT 'open',
  resolved_at              TIMESTAMPTZ,
  resolution_notes         TEXT,
  zone                     TEXT,
  location                 TEXT,
  bounding_box             JSONB,
  description              TEXT,
  annotated_image_path     TEXT,
  first_seen_inspection_id UUID REFERENCES inspections(id) ON DELETE SET NULL
);

-- Final report generated per inspection
CREATE TABLE IF NOT EXISTS reports (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id     UUID UNIQUE NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
  generated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  summary           TEXT,
  total_findings    INTEGER NOT NULL DEFAULT 0,
  critical_findings INTEGER NOT NULL DEFAULT 0,
  pdf_path          TEXT,
  raw_json          JSONB
);

CREATE INDEX IF NOT EXISTS idx_inspections_truck ON inspections(truck_id);
CREATE INDEX IF NOT EXISTS idx_media_inspection ON inspection_media(inspection_id);
CREATE INDEX IF NOT EXISTS idx_findings_inspection ON findings(inspection_id);
CREATE INDEX IF NOT EXISTS idx_findings_truck_lookup ON findings(finding_type, zone);
CREATE INDEX IF NOT EXISTS idx_memberships_user ON fleet_memberships(user_id, fleet_id);
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status_created ON analysis_jobs(status, created_at);

-- Defense-in-depth tenant isolation for Supabase's data API. The trusted backend
-- service role provisions memberships and may bypass RLS; browser clients cannot.
ALTER TABLE fleets ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleet_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE trucks ENABLE ROW LEVEL SECURITY;
ALTER TABLE inspections ENABLE ROW LEVEL SECURITY;
ALTER TABLE inspection_media ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS memberships_select_own ON fleet_memberships;
CREATE POLICY memberships_select_own ON fleet_memberships FOR SELECT
USING (user_id = auth.uid());

DROP POLICY IF EXISTS fleets_member_access ON fleets;
CREATE POLICY fleets_member_access ON fleets FOR SELECT
USING (EXISTS (
  SELECT 1 FROM fleet_memberships fm
  WHERE fm.fleet_id = fleets.id AND fm.user_id = auth.uid()
));

DROP POLICY IF EXISTS trucks_member_access ON trucks;
CREATE POLICY trucks_member_access ON trucks FOR ALL
USING (EXISTS (
  SELECT 1 FROM fleet_memberships fm
  WHERE fm.fleet_id = trucks.fleet_id AND fm.user_id = auth.uid()
))
WITH CHECK (EXISTS (
  SELECT 1 FROM fleet_memberships fm
  WHERE fm.fleet_id = trucks.fleet_id AND fm.user_id = auth.uid()
));

DROP POLICY IF EXISTS inspections_member_access ON inspections;
CREATE POLICY inspections_member_access ON inspections FOR ALL
USING (EXISTS (
  SELECT 1 FROM trucks t JOIN fleet_memberships fm ON fm.fleet_id = t.fleet_id
  WHERE t.id = inspections.truck_id AND fm.user_id = auth.uid()
))
WITH CHECK (EXISTS (
  SELECT 1 FROM trucks t JOIN fleet_memberships fm ON fm.fleet_id = t.fleet_id
  WHERE t.id = inspections.truck_id AND fm.user_id = auth.uid()
));

DROP POLICY IF EXISTS media_member_access ON inspection_media;
CREATE POLICY media_member_access ON inspection_media FOR ALL
USING (EXISTS (
  SELECT 1 FROM inspections i
  JOIN trucks t ON t.id = i.truck_id
  JOIN fleet_memberships fm ON fm.fleet_id = t.fleet_id
  WHERE i.id = inspection_media.inspection_id AND fm.user_id = auth.uid()
))
WITH CHECK (EXISTS (
  SELECT 1 FROM inspections i
  JOIN trucks t ON t.id = i.truck_id
  JOIN fleet_memberships fm ON fm.fleet_id = t.fleet_id
  WHERE i.id = inspection_media.inspection_id AND fm.user_id = auth.uid()
));

DROP POLICY IF EXISTS analysis_jobs_member_access ON analysis_jobs;
CREATE POLICY analysis_jobs_member_access ON analysis_jobs FOR SELECT
USING (EXISTS (
  SELECT 1 FROM inspections i
  JOIN trucks t ON t.id = i.truck_id
  JOIN fleet_memberships fm ON fm.fleet_id = t.fleet_id
  WHERE i.id = analysis_jobs.inspection_id AND fm.user_id = auth.uid()
));

DROP POLICY IF EXISTS findings_member_access ON findings;
CREATE POLICY findings_member_access ON findings FOR ALL
USING (EXISTS (
  SELECT 1 FROM inspections i
  JOIN trucks t ON t.id = i.truck_id
  JOIN fleet_memberships fm ON fm.fleet_id = t.fleet_id
  WHERE i.id = findings.inspection_id AND fm.user_id = auth.uid()
))
WITH CHECK (EXISTS (
  SELECT 1 FROM inspections i
  JOIN trucks t ON t.id = i.truck_id
  JOIN fleet_memberships fm ON fm.fleet_id = t.fleet_id
  WHERE i.id = findings.inspection_id AND fm.user_id = auth.uid()
));

DROP POLICY IF EXISTS reports_member_access ON reports;
CREATE POLICY reports_member_access ON reports FOR ALL
USING (EXISTS (
  SELECT 1 FROM inspections i
  JOIN trucks t ON t.id = i.truck_id
  JOIN fleet_memberships fm ON fm.fleet_id = t.fleet_id
  WHERE i.id = reports.inspection_id AND fm.user_id = auth.uid()
))
WITH CHECK (EXISTS (
  SELECT 1 FROM inspections i
  JOIN trucks t ON t.id = i.truck_id
  JOIN fleet_memberships fm ON fm.fleet_id = t.fleet_id
  WHERE i.id = reports.inspection_id AND fm.user_id = auth.uid()
));
