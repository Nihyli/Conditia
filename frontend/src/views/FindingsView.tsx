import type { Finding, Inspection, Severity } from "../types";

const sevClass: Record<Severity, string> = {
  critical: "crit",
  medium: "medium",
  low: "low",
  clear: "clear",
};

type FindingRow = Finding & {
  inspectionId: string;
  truckLabel: string;
};

export function FindingsView({
  inspections,
  onSelectInspection,
}: {
  inspections: Inspection[];
  onSelectInspection: (id: string) => void;
}) {
  const rows: FindingRow[] = inspections.flatMap((insp) =>
    insp.findings.map((f) => ({
      ...f,
      inspectionId: insp.id,
      truckLabel: insp.truckLabel,
    }))
  );

  if (rows.length === 0) {
    return (
      <section className="panel">
        <div className="empty">
          <div className="empty__title">No findings yet</div>
          <p className="muted">
            Findings appear after analysis runs on uploaded inspection footage.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">All findings</h2>
        <span className="muted">{rows.length} across fleet</span>
      </div>
      <div className="data-table">
        {rows.map((f) => (
          <button
            type="button"
            className="data-row data-row--clickable"
            key={f.id}
            onClick={() => onSelectInspection(f.inspectionId)}
          >
            <div className="data-row__primary">
              <span className={`sev ${sevClass[f.severity]}`}>
                {f.severity}
              </span>
              <span className="data-row__label">{f.title}</span>
              <span className="data-row__sub">
                {f.truckLabel} · {f.location} ·{" "}
                <span className="mono">{Math.round(f.confidence * 100)}%</span>
              </span>
            </div>
            <span className="text-btn">View inspection</span>
          </button>
        ))}
      </div>
    </section>
  );
}
