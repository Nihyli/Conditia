import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getInspection } from "../api";
import { DamageMap } from "../components/DamageMap";
import { PageAlert } from "../components/PageAlert";
import { StatusBadge } from "../components/StatusBadge";
import { mapInspectionSummary } from "../mapInspection";
import { ROUTES } from "../nav";
import type { Inspection } from "../types";

export function InspectionDetailPage() {
  const { inspectionId = "" } = useParams();
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!inspectionId) return;
    try {
      const row = await getInspection(inspectionId);
      setInspection(mapInspectionSummary(row));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load inspection");
    } finally {
      setLoading(false);
    }
  }, [inspectionId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <PageAlert
        message="Could not load inspection."
        detail={error}
        onRetry={() => void load()}
      />
    );
  }

  if (loading || !inspection) {
    return <p className="muted">Loading inspection…</p>;
  }

  return (
    <>
      {(inspection.status === "review_required" ||
        inspection.status === "failed") && (
        <div className="dashboard-alert">
          <p className="error-note">
            {inspection.status === "review_required"
              ? "Manual review required"
              : "Analysis failed"}
          </p>
          <p className="muted">
            {inspection.status === "review_required"
              ? "Automated analysis could not produce a confident result. Review the captured media below — this is not a clear inspection."
              : "The analysis pipeline encountered an error. Review the captured media and re-run the inspection if needed."}
          </p>
        </div>
      )}

      <section className="panel panel--compact">
        <div className="panel__head">
          <h2 className="panel__title">{inspection.truckLabel}</h2>
          <StatusBadge status={inspection.status} />
          <div className="panel__spacer" />
          <Link to={ROUTES.reportDetail(inspection.id)} className="ghost-btn">
            View report
          </Link>
        </div>
      </section>

      <DamageMap inspection={inspection} />
    </>
  );
}
