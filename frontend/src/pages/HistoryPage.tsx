import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getInspections, getTrucks } from "../api";
import { PageAlert } from "../components/PageAlert";
import { StatusBadge } from "../components/StatusBadge";
import { mapInspectionSummary } from "../mapInspection";
import { ROUTES } from "../nav";
import {
  severityClass,
  severityColor,
  severityLabel,
} from "../severity";
import type { ApiTruck } from "../api";
import type { Inspection } from "../types";

export function HistoryPage() {
  const [trucks, setTrucks] = useState<ApiTruck[]>([]);
  const [selectedTruckId, setSelectedTruckId] = useState("");
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [truckRows, inspRows] = await Promise.all([
        getTrucks(),
        getInspections(),
      ]);
      setTrucks(truckRows);
      setInspections(inspRows.map(mapInspectionSummary));
      setSelectedTruckId((cur) => cur || truckRows[0]?.id || "");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const truckInspections = inspections
    .filter((i) => i.truckId === selectedTruckId)
    .sort(
      (a, b) =>
        new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime()
    );

  const selectedTruck = trucks.find((t) => t.id === selectedTruckId);

  if (error) {
    return (
      <PageAlert
        message="Could not load history."
        detail={error}
        onRetry={() => void load()}
      />
    );
  }

  if (loading) {
    return <p className="muted">Loading history…</p>;
  }

  return (
    <>
      <section className="panel">
        <div className="panel__head">
          <h2 className="panel__title">Condition history</h2>
        </div>
        {trucks.length === 0 ? (
          <div className="empty">
            <div className="empty__title">No trucks registered</div>
            <p className="muted">
              <Link to={ROUTES.trucks} className="text-link">
                Register a truck
              </Link>{" "}
              to begin tracking change over time.
            </p>
          </div>
        ) : (
          <label className="form-field form-field--inline">
            <span>Asset</span>
            <select
              value={selectedTruckId}
              onChange={(e) => setSelectedTruckId(e.target.value)}
            >
              {trucks.map((truck) => (
                <option key={truck.id} value={truck.id}>
                  {[truck.make, truck.model, truck.vin].filter(Boolean).join(" · ")}
                </option>
              ))}
            </select>
          </label>
        )}
      </section>

      {selectedTruck && truckInspections.length > 0 ? (
        <div className="timeline">
          {truckInspections.map((insp) => {
            const newFindings = insp.findings.filter(
              (f) => f.firstDetectedInspectionsAgo === 0
            );
            const priorFindings = insp.findings.filter(
              (f) => f.firstDetectedInspectionsAgo > 0
            );
            return (
              <section className="panel timeline__item" key={insp.id}>
                <div className="panel__head">
                  <h3 className="panel__title">{insp.capturedAtLabel}</h3>
                  <StatusBadge status={insp.status} />
                  <div className="panel__spacer" />
                  <Link
                    to={ROUTES.inspectionDetail(insp.id)}
                    className="text-link"
                  >
                    Open inspection
                  </Link>
                </div>
                <p className="muted timeline__when">{insp.relativeLabel}</p>

                {insp.findings.length === 0 ? (
                  <p className="muted">No findings on this inspection.</p>
                ) : (
                  <>
                    {newFindings.length > 0 ? (
                      <div className="timeline__group">
                        <h4 className="timeline__label is-new">
                          New this inspection ({newFindings.length})
                        </h4>
                        <ul className="timeline__findings">
                          {newFindings.map((f) => (
                            <li key={f.id}>
                              <span
                                className={`sev ${severityClass[f.severity]}`}
                              >
                                {severityLabel[f.severity]}
                              </span>{" "}
                              {f.title}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {priorFindings.length > 0 ? (
                      <div className="timeline__group">
                        <h4 className="timeline__label is-old">
                          Previously detected ({priorFindings.length})
                        </h4>
                        <ul className="timeline__findings">
                          {priorFindings.map((f) => (
                            <li key={f.id}>
                              <span
                                className={`sev ${severityClass[f.severity]}`}
                                style={{ color: severityColor[f.severity] }}
                              >
                                {severityLabel[f.severity]}
                              </span>{" "}
                              {f.title} — first seen{" "}
                              {f.firstDetectedInspectionsAgo} inspection
                              {f.firstDetectedInspectionsAgo === 1 ? "" : "s"} ago
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </>
                )}
              </section>
            );
          })}
        </div>
      ) : selectedTruck ? (
        <section className="panel">
          <div className="empty">
            <div className="empty__title">No inspections for this asset</div>
            <p className="muted">
              <Link to={`/capture/${selectedTruck.id}`} className="text-link">
                Run the first inspection
              </Link>
            </p>
          </div>
        </section>
      ) : null}
    </>
  );
}
