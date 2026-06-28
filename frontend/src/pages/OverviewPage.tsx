import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getFleetStats, getInspections } from "../api";
import { RecentInspections } from "../components/RecentInspections";
import { DamageMap } from "../components/DamageMap";
import { PageAlert } from "../components/PageAlert";
import { StatCards } from "../components/StatCards";
import { mapFleetStats, mapInspectionSummary } from "../mapInspection";
import type { FleetStat, Inspection } from "../types";

const POLL_MS = 5000;

export function OverviewPage() {
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [stats, setStats] = useState<FleetStat[]>([]);
  const [activeInspectionId, setActiveInspectionId] = useState<string | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const inspRows = await getInspections();
      const mapped = inspRows.map(mapInspectionSummary);

      let statsRow;
      try {
        statsRow = await getFleetStats();
      } catch {
        statsRow = {
          active_trucks: new Set(inspRows.map((i) => i.truck_id)).size,
          inspections_today: inspRows.filter((i) => {
            const d = new Date(i.started_at);
            const now = new Date();
            return d.toDateString() === now.toDateString();
          }).length,
          inspections_pending: inspRows.filter(
            (i) =>
              i.status === "uploading" ||
              i.status === "submitted" ||
              i.status === "processing"
          ).length,
          inspections_complete_today: inspRows.filter((i) => {
            const d = new Date(i.started_at);
            const now = new Date();
            return (
              d.toDateString() === now.toDateString() && i.status === "complete"
            );
          }).length,
          open_findings: inspRows.reduce((n, i) => n + i.finding_count, 0),
        };
      }

      setInspections(mapped);
      setStats(mapFleetStats(statsRow));
      setError(null);

      setActiveInspectionId((cur) => {
        if (cur && mapped.some((i) => i.id === cur)) return cur;
        return mapped[0]?.id ?? null;
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load dashboard";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const needsPoll = inspections.some(
      (i) =>
        i.status === "uploading" ||
        i.status === "submitted" ||
        i.status === "processing"
    );
    if (!needsPoll) {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    if (pollRef.current === null) {
      pollRef.current = window.setInterval(() => void load(), POLL_MS);
    }
    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [inspections, load]);

  const activeInspection =
    inspections.find((i) => i.id === activeInspectionId) ?? null;

  if (error) {
    return (
      <PageAlert
        message="Could not load fleet data."
        detail={error}
        onRetry={() => void load()}
      />
    );
  }

  if (loading) {
    return <p className="muted">Loading fleet data…</p>;
  }

  return (
    <>
      <StatCards stats={stats} />

      {inspections.length === 0 ? (
        <div className="panel">
          <div className="empty">
            <div className="empty__title">No inspections yet</div>
            <p className="muted">
              Register a truck, then run your first guided walk-around.
              Uploaded footage appears here once analysis completes.
            </p>
            <Link to="/capture" className="primary-btn" style={{ marginTop: 16 }}>
              Start first inspection
            </Link>
          </div>
        </div>
      ) : (
        <div className="work">
          <RecentInspections
            inspections={inspections}
            activeId={activeInspectionId ?? ""}
            onSelect={setActiveInspectionId}
          />
          {activeInspection ? (
            <DamageMap inspection={activeInspection} />
          ) : null}
        </div>
      )}
    </>
  );
}

/** @deprecated Use OverviewPage inside AppLayout routes. */
export { OverviewPage as DashboardPage };
