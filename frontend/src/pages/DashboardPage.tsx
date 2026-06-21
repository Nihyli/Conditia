import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getFleetStats, getInspections, getTrucks, type ApiTruck } from "../api";
import { Sidebar } from "../components/Sidebar";
import { Topbar } from "../components/Topbar";
import { StatCards } from "../components/StatCards";
import { RecentInspections } from "../components/RecentInspections";
import { DamageMap } from "../components/DamageMap";
import { mapFleetStats, mapInspectionSummary } from "../mapInspection";
import { FindingsView } from "../views/FindingsView";
import { PlaceholderView } from "../views/PlaceholderView";
import { TrucksView } from "../views/TrucksView";
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
  const [trucks, setTrucks] = useState<ApiTruck[]>([]);
  const [stats, setStats] = useState<FleetStat[]>([]);
  const [activeInspectionId, setActiveInspectionId] = useState<string | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const goToInspection = useCallback((id: string) => {
    setActiveNav("inspections");
    setActiveInspectionId(id);
  }, []);

  const load = useCallback(async () => {
    try {
      const [inspRows, truckRows] = await Promise.all([
        getInspections(),
        getTrucks().catch(() => [] as ApiTruck[]),
      ]);
      const mapped = inspRows.map(mapInspectionSummary);

      let statsRow;
      try {
        statsRow = await getFleetStats();
      } catch {
        statsRow = {
          active_trucks: new Set(inspRows.map((i) => i.truck_id)).size,
          inspections_today: inspRows.filter((i) => {
            const d = new Date(i.started_at);
            return d.toDateString() === new Date().toDateString();
          }).length,
          inspections_pending: inspRows.filter(
            (i) => i.status === "pending" || i.status === "processing"
          ).length,
          inspections_complete_today: inspRows.filter((i) => {
            const d = new Date(i.started_at);
            return (
              d.toDateString() === new Date().toDateString() &&
              i.status === "complete"
            );
          }).length,
          open_findings: inspRows.reduce((n, i) => n + i.finding_count, 0),
        };
      }

      setInspections(mapped);
      setTrucks(truckRows);
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
      (i) => i.status === "pending" || i.status === "processing"
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
    trucks.length > 0
      ? trucks.length
      : stats.find((s) => s.id === "active")?.value !== "0"
        ? Number(stats.find((s) => s.id === "active")?.value)
        : undefined;

  const inspectionPanel =
    inspections.length === 0 ? (
      <div className="panel">
        <div className="empty">
          <div className="empty__title">No inspections yet</div>
          <p className="muted">
            Register a truck, then run your first guided walk-around.
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
    );

  function renderContent() {
    switch (activeNav) {
      case "overview":
        return (
          <>
            <StatCards stats={stats} />
            {inspectionPanel}
          </>
        );
      case "inspections":
        return inspectionPanel;
      case "trucks":
        return (
          <TrucksView
            trucks={trucks}
            inspections={inspections}
            onSelectInspection={goToInspection}
          />
        );
      case "findings":
        return (
          <FindingsView
            inspections={inspections}
            onSelectInspection={goToInspection}
          />
        );
      case "reports":
        return (
          <PlaceholderView
            title="Reports"
            description="PDF export and scheduled fleet reports are coming in the next release."
          />
        );
      case "history":
        return (
          <PlaceholderView
            title="Inspection history"
            description="Full historical timeline and comparison tools are coming soon."
          />
        );
      case "samsara":
        return (
          <PlaceholderView
            title="Samsara integration"
            description="Connect your Samsara telematics account to sync fleet data. Planned for post-MVP."
          />
        );
      case "settings":
        return (
          <PlaceholderView
            title="Settings"
            description="Fleet preferences, user management, and API keys will live here."
          />
        );
      default:
        return inspectionPanel;
    }
  }

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
                Backend should be on port <code>8001</code> (frontend proxy:{" "}
                <code>/api</code> → 8001). Verify:{" "}
                <code>Invoke-RestMethod http://127.0.0.1:8001/health</code>
              </p>
              <button className="primary-btn" onClick={() => void load()}>
                <IconRefresh size={16} />
                Retry
              </button>
            </div>
          ) : loading ? (
            <p className="muted">Loading fleet data…</p>
          ) : (
            renderContent()
          )}
        </main>
      </div>
    </div>
  );
}
