import { useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { Topbar } from "../components/Topbar";
import { StatCards } from "../components/StatCards";
import { RecentInspections } from "../components/RecentInspections";
import { DamageMap } from "../components/DamageMap";
import { inspections } from "../data";

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

export function DashboardPage() {
  const [activeNav, setActiveNav] = useState("overview");
  const [activeInspectionId, setActiveInspectionId] = useState(
    inspections[0].id
  );

  const activeInspection =
    inspections.find((i) => i.id === activeInspectionId) ?? inspections[0];

  return (
    <div className="app">
      <Sidebar active={activeNav} onSelect={setActiveNav} />

      <div className="main">
        <Topbar title={navTitles[activeNav] ?? "Fleet overview"} />

        <main className="content">
          <StatCards />

          <div className="work">
            <RecentInspections
              inspections={inspections}
              activeId={activeInspectionId}
              onSelect={setActiveInspectionId}
            />
            <DamageMap inspection={activeInspection} />
          </div>
        </main>
      </div>
    </div>
  );
}
