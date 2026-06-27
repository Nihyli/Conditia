-- Reset Conditia dev schema on Supabase (run in SQL Editor).
-- Required when old Dev-era tables (VARCHAR ids from create_all) are present.
-- This wipes all app data in this database.

drop table if exists
  reports,
  findings,
  analysis_jobs,
  inspection_media,
  inspections,
  trucks,
  fleets,
  users,
  alembic_version
cascade;
