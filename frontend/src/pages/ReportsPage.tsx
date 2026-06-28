import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getReports } from "../api";
import { PageAlert } from "../components/PageAlert";
import { formatCapturedAt } from "../formatTime";
import { ROUTES } from "../nav";
import type { ApiReport } from "../api";

export function ReportsPage() {
  const [reports, setReports] = useState<ApiReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setReports(await getReports());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load reports");
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
        message="Could not load reports."
        detail={error}
        onRetry={() => void load()}
      />
    );
  }

  if (loading) {
    return <p className="muted">Loading reports…</p>;
  }

  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Inspection reports</h2>
      </div>
      {reports.length === 0 ? (
        <div className="empty">
          <div className="empty__title">No reports yet</div>
          <p className="muted">
            Reports are generated after an inspection completes analysis.
          </p>
        </div>
      ) : (
        <div className="insp-list">
          {reports.map((report) => {
            const { capturedAtLabel, relativeLabel } = formatCapturedAt(
              report.generated_at
            );
            return (
              <Link
                key={report.id}
                to={ROUTES.reportDetail(report.inspection_id)}
                className="insp-row"
              >
                <span className="insp-row__id">
                  Inspection {report.inspection_id.slice(0, 8)}
                </span>
                <span className="insp-row__meta">
                  <span className="insp-row__time">
                    {capturedAtLabel} · {relativeLabel}
                  </span>
                  <span className="insp-row__truck">{report.summary}</span>
                </span>
                <span className="mono report-stat">
                  {report.total_findings} findings
                  {report.critical_findings > 0
                    ? ` · ${report.critical_findings} critical`
                    : ""}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
