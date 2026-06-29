import { useMemo, useState } from "react";
import type { Inspection, Severity } from "../types";
import { severityColor, severityRank } from "../severity";

function worstSeverity(inspection: Inspection): Severity {
  if (inspection.findings.length === 0) return "clear";
  return inspection.findings.reduce<Severity>((worst, f) => {
    return severityRank[f.severity] > severityRank[worst] ? f.severity : worst;
  }, "clear");
}

const STATUS_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "complete", label: "Complete" },
  { value: "processing", label: "Processing" },
  { value: "submitted", label: "Submitted" },
  { value: "uploading", label: "Uploading" },
  { value: "review_required", label: "Review required" },
  { value: "failed", label: "Failed" },
];

export function RecentInspections({
  inspections,
  activeId,
  onSelect,
}: {
  inspections: Inspection[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  const [statusFilter, setStatusFilter] = useState("");

  const filtered = useMemo(() => {
    if (!statusFilter) return inspections;
    return inspections.filter((insp) => insp.status === statusFilter);
  }, [inspections, statusFilter]);

  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Recent inspections</h2>
        <div className="panel__spacer" />
        <label className="form-field form-field--inline">
          <select
            className="select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by status"
          >
            {STATUS_FILTER_OPTIONS.map((opt) => (
              <option key={opt.value || "all"} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {filtered.length === 0 ? (
        <div className="empty">
          <div className="empty__title">No inspections match</div>
          <p className="muted">Try a different status filter.</p>
        </div>
      ) : (
      <div className="insp-list">
        {filtered.map((insp) => {
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
      )}
    </section>
  );
}
