import type { Inspection, Severity } from "../types";
import { severityColor, severityRank } from "../severity";
import { IconFilter } from "./icons";

function worstSeverity(inspection: Inspection): Severity {
  if (inspection.findings.length === 0) return "clear";
  return inspection.findings.reduce<Severity>((worst, f) => {
    return severityRank[f.severity] > severityRank[worst] ? f.severity : worst;
  }, "clear");
}

export function RecentInspections({
  inspections,
  activeId,
  onSelect,
}: {
  inspections: Inspection[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Recent inspections</h2>
        <div className="panel__spacer" />
        <button className="ghost-btn" disabled title="Filtering is not available yet">
          <IconFilter />
          Filter
        </button>
      </div>

      <div className="insp-list">
        {inspections.map((insp) => {
          const sev = worstSeverity(insp);
          return (
            <button
              key={insp.id}
              className={`insp-row${insp.id === activeId ? " is-active" : ""}`}
              onClick={() => onSelect(insp.id)}
            >
              <span className="insp-row__id">{insp.truckLabel}</span>
              <span className="insp-row__meta">
                {(insp.make || insp.model) && (
                  <span className="insp-row__truck">
                    {[insp.make, insp.model].filter(Boolean).join(" ")}
                  </span>
                )}
                <span className="insp-row__time">
                  {insp.capturedAtLabel} · {insp.relativeLabel}
                </span>
              </span>
              <span
                className="insp-row__flag"
                style={{ background: severityColor[sev] }}
                aria-label={sev}
              />
            </button>
          );
        })}
      </div>
    </section>
  );
}
