import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getTruck, getTruckInspections } from "../api";
import { PageAlert } from "../components/PageAlert";
import { StatusBadge } from "../components/StatusBadge";
import { formatCapturedAt } from "../formatTime";
import { ROUTES } from "../nav";
import type { ApiInspectionRecord, ApiTruck } from "../api";
import type { Inspection } from "../types";

function parseInspectionStatus(raw: string): Inspection["status"] {
  const valid: Inspection["status"][] = [
    "uploading",
    "submitted",
    "processing",
    "complete",
    "review_required",
    "failed",
  ];
  if (valid.includes(raw as Inspection["status"])) {
    return raw as Inspection["status"];
  }
  return "failed";
}

export function TruckDetailPage() {
  const { truckId = "" } = useParams();
  const [truck, setTruck] = useState<ApiTruck | null>(null);
  const [inspections, setInspections] = useState<ApiInspectionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!truckId) return;
    try {
      const [truckRow, inspRows] = await Promise.all([
        getTruck(truckId),
        getTruckInspections(truckId),
      ]);
      setTruck(truckRow);
      setInspections(inspRows);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load truck");
    } finally {
      setLoading(false);
    }
  }, [truckId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <PageAlert message="Could not load truck." detail={error} onRetry={() => void load()} />
    );
  }

  if (loading || !truck) {
    return <p className="muted">Loading truck…</p>;
  }

  return (
    <>
      <section className="panel">
        <div className="panel__head">
          <h2 className="panel__title">
            {[truck.make, truck.model].filter(Boolean).join(" ") || truck.vin}
          </h2>
          <div className="panel__spacer" />
          <Link to={`/capture/${truck.id}`} className="primary-btn">
            Start inspection
          </Link>
        </div>
        <dl className="detail-grid">
          <div>
            <dt>VIN</dt>
            <dd className="mono">{truck.vin}</dd>
          </div>
          <div>
            <dt>License plate</dt>
            <dd>{truck.license_plate ?? "—"}</dd>
          </div>
          <div>
            <dt>Year</dt>
            <dd className="mono">{truck.year ?? "—"}</dd>
          </div>
        </dl>
      </section>

      <section className="panel">
        <div className="panel__head">
          <h2 className="panel__title">Inspection history</h2>
        </div>
        {inspections.length === 0 ? (
          <div className="empty">
            <div className="empty__title">No inspections yet</div>
            <p className="muted">Run a guided walk-around to begin tracking condition.</p>
          </div>
        ) : (
          <div className="insp-list">
            {inspections.map((insp) => {
              const { capturedAtLabel, relativeLabel } = formatCapturedAt(
                insp.started_at
              );
              return (
                <Link
                  key={insp.id}
                  to={ROUTES.inspectionDetail(insp.id)}
                  className="insp-row"
                >
                  <span className="insp-row__id">{capturedAtLabel}</span>
                  <span className="insp-row__meta">
                    <span className="insp-row__time">
                      {relativeLabel} · {insp.capture_source}
                    </span>
                  </span>
                  <StatusBadge status={parseInspectionStatus(insp.status)} />
                </Link>
              );
            })}
          </div>
        )}
      </section>
    </>
  );
}
