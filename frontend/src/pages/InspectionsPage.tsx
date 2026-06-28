import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getInspections } from "../api";
import { PageAlert } from "../components/PageAlert";
import { StatusBadge } from "../components/StatusBadge";
import { mapInspectionSummary } from "../mapInspection";
import { ROUTES } from "../nav";
import { severityColor, severityRank } from "../severity";
import type { Inspection, Severity } from "../types";

function worstSeverity(inspection: Inspection): Severity {
  if (inspection.findings.length === 0) return "clear";
  return inspection.findings.reduce<Severity>(
    (worst, f) =>
      severityRank[f.severity] > severityRank[worst] ? f.severity : worst,
    "clear"
  );
}

export function InspectionsPage() {
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const rows = await getInspections();
      setInspections(rows.map(mapInspectionSummary));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load inspections");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <PageAlert
        message="Could not load inspections."
        detail={error}
        onRetry={() => void load()}
      />
    );
  }

  if (loading) {
    return <p className="muted">Loading inspections…</p>;
  }

  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">All inspections</h2>
      </div>
      {inspections.length === 0 ? (
        <div className="empty">
          <div className="empty__title">No inspections yet</div>
          <p className="muted">
            <Link to="/capture" className="text-link">
              Start your first inspection
            </Link>
          </p>
        </div>
      ) : (
        <div className="insp-list">
          {inspections.map((insp) => {
            const sev = worstSeverity(insp);
            return (
              <Link
                key={insp.id}
                to={ROUTES.inspectionDetail(insp.id)}
                className="insp-row"
              >
                <span className="insp-row__id">{insp.truckLabel}</span>
                <span className="insp-row__meta">
                  <span className="insp-row__truck">
                    {[insp.make, insp.model].filter(Boolean).join(" ")}
                  </span>
                  <span className="insp-row__time">
                    {insp.capturedAtLabel} · {insp.relativeLabel}
                  </span>
                </span>
                <StatusBadge status={insp.status} />
                <span
                  className="insp-row__flag"
                  style={{ background: severityColor[sev] }}
                  aria-label={sev}
                />
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
