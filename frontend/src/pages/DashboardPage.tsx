import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getFleetStats, getInspections } from "../api";
import { Sidebar } from "../components/Sidebar";
import { Topbar } from "../components/Topbar";
import { StatCards } from "../components/StatCards";
import { RecentInspections } from "../components/RecentInspections";
import { DamageMap } from "../components/DamageMap";
import { mapFleetStats, mapInspectionSummary } from "../mapInspection";
import type { FleetStat, Inspection } from "../types";
import { IconRefresh } from "../components/icons";

const navTitles: Record<string, string> = {
  overview: "Fleet overview",
  trucks: "Trucks",
  inspections: "Inspections",
  findings: "Findings",
  reports: "Reports",
  history: "History",
  samsara: "Samsara integration",
  settings: "Settings",
};

const POLL_MS = 5000;

export function DashboardPage() {
  const [activeNav, setActiveNav] = useState("overview");
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
        // Fallback if /fleet/stats is missing (old backend) — derive from inspections.
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

  // Poll while any inspection is still processing.
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

  const truckBadge =
    stats.find((s) => s.id === "active")?.value !== "0"
      ? Number(stats.find((s) => s.id === "active")?.value)
      : undefined;

  return (
    <div className="app">
      <Sidebar
        active={activeNav}
        onSelect={setActiveNav}
        trucksBadge={truckBadge}
      />

      <div className="main">
        <Topbar title={navTitles[activeNav] ?? "Fleet overview"} />

        <main className="content">
          {error ? (
            <div className="dashboard-alert">
              <p className="error-note">Could not load fleet data.</p>
              <p className="muted">{error}</p>
              <p className="muted">
                Backend should be running at{" "}
                <code>http://127.0.0.1:8001</code> (dev proxy:{" "}
                <code>/api</code>). Check{" "}
                <a href="http://127.0.0.1:8001/docs" target="_blank" rel="noreferrer">
                  /docs
                </a>{" "}
                — if <code>/fleet/stats</code> is missing, restart the backend.
              </p>
              <button className="primary-btn" onClick={() => void load()}>
                <IconRefresh size={16} />
                Retry
              </button>
            </div>
          ) : loading ? (
            <p className="muted">Loading fleet data…</p>
          ) : (
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
          )}
        </main>
      </div>
    </div>
  );
}
