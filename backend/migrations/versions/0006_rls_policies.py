"""Row-level security policies for tenant isolation (PostgreSQL/Supabase only).

These policies protect direct PostgREST/anon-key access by restricting rows to
the authenticated user's fleet memberships.  The backend API connects as the
table owner, which bypasses RLS (ENABLE without FORCE) — all real tenant
isolation for API requests is the application-level fleet predicate in each
query.  SQLite (local dev) has no RLS, so this migration is a no-op there.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_rls_policies"
down_revision: str | Sequence[str] | None = "0005_fleet_memberships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLES = (
    "fleets",
    "fleet_memberships",
    "trucks",
    "inspections",
    "inspection_media",
    "analysis_jobs",
    "findings",
    "reports",
)

# asyncpg refuses multiple commands in one prepared statement, so every batch
# below is split into single statements before execution.
def _statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


_ENABLE = "\n".join(
    f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" for table in _TABLES
)

_POLICIES = """
CREATE INDEX IF NOT EXISTS idx_memberships_user
  ON fleet_memberships(user_id, fleet_id);

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
"""

_DROP_POLICIES = "\n".join(
    f"DROP POLICY IF EXISTS {name} ON {table};"
    for name, table in (
        ("memberships_select_own", "fleet_memberships"),
        ("fleets_member_access", "fleets"),
        ("trucks_member_access", "trucks"),
        ("inspections_member_access", "inspections"),
        ("media_member_access", "inspection_media"),
        ("analysis_jobs_member_access", "analysis_jobs"),
        ("findings_member_access", "findings"),
        ("reports_member_access", "reports"),
    )
)

_DISABLE = "\n".join(
    f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;" for table in _TABLES
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for statement in _statements(_ENABLE) + _statements(_POLICIES):
        op.execute(statement)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for statement in _statements(_DROP_POLICIES) + _statements(_DISABLE):
        op.execute(statement)
