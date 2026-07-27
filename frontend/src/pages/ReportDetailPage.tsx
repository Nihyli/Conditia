import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Markdown from "react-markdown";
import { getReport } from "../api";
import { PageAlert } from "../components/PageAlert";
import { formatCapturedAt } from "../formatTime";
import { ROUTES } from "../nav";
import { parseSeverity, severityClass, severityLabel } from "../severity";
import type { ApiReport } from "../api";
import { IconDownload } from "../components/icons";

export function ReportDetailPage() {
  const { inspectionId = "" } = useParams();
  const [report, setReport] = useState<ApiReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!inspectionId) return;
    try {
      setReport(await getReport(inspectionId));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load report");
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
        message="Could not load report."
        detail={error}
        onRetry={() => void load()}
      />
    );
  }

  if (loading || !report) {
    return <p className="muted">Loading report…</p>;
  }

  const { capturedAtLabel } = formatCapturedAt(report.generated_at);
  const findings = report.raw_json?.findings ?? [];
  const narrativeMarkdown = report.raw_json?.narrative_markdown;

  return (
    <section className="panel report-print">
      <div className="panel__head no-print">
        <h2 className="panel__title">Inspection report</h2>
        <div className="panel__spacer" />
        <button className="ghost-btn" onClick={() => window.print()}>
          <IconDownload />
          Print / Save as PDF
        </button>
        <Link to={ROUTES.inspectionDetail(report.inspection_id)} className="ghost-btn">
          View inspection
        </Link>
      </div>

      <div className="report-header">
        <h1 className="report-header__title">Conditia condition report</h1>
        <p className="muted">Generated {capturedAtLabel}</p>
        <p className="report-summary">{report.summary}</p>
        <dl className="detail-grid">
          <div>
            <dt>Total findings</dt>
            <dd className="mono">{report.total_findings}</dd>
          </div>
          <div>
            <dt>Critical findings</dt>
            <dd className="mono">{report.critical_findings}</dd>
          </div>
          <div>
            <dt>Inspection ID</dt>
            <dd className="mono">{report.inspection_id}</dd>
          </div>
        </dl>
        {report.raw_json?.requires_human_review ? (
          <p className="error-note">
            Manual review required — automated triage is not a clear result.
          </p>
        ) : null}
      </div>

      {narrativeMarkdown ? (
        <div className="report-narrative">
          <Markdown>{narrativeMarkdown}</Markdown>
        </div>
      ) : null}

      {findings.length === 0 ? (
        <div className="empty">
          <div className="empty__title">No findings recorded</div>
        </div>
      ) : (
        <>
          <div className="report-section-label">Findings</div>
          <div className="findings">
            {findings.map((f) => {
              const sev = parseSeverity(f.severity);
              return (
                <article className="finding" key={f.id}>
                  <div className="finding__body">
                    <div className="finding__top">
                      <span className={`sev ${severityClass[sev]}`}>
                        <span className="sev__dot" />
                        {severityLabel[sev]}
                      </span>
                      <span className="finding__title">{f.title ?? f.type}</span>
                    </div>
                    <div className="finding__desc">
                      {f.location ?? f.zone ?? "Unknown location"} ·{" "}
                      <span className="mono">{Math.round(f.confidence * 100)}%</span>{" "}
                      confidence · {f.status}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
