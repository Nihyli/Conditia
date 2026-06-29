import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { getFindings, updateFinding } from "../api";
import { PageAlert } from "../components/PageAlert";
import { mapFindingDetail } from "../mapInspection";
import { ROUTES } from "../nav";
import {
  severityClass,
  severityColor,
  severityFill,
  severityLabel,
} from "../severity";
import type { FindingDetail, FindingStatus } from "../types";

const SEVERITY_OPTIONS = ["", "critical", "high", "medium", "low"] as const;
const STATUS_OPTIONS = [
  "",
  "open",
  "acknowledged",
  "resolved",
  "false_positive",
] as const;

function changeLabel(ago: number) {
  if (ago === 0) return "New — first detected this inspection";
  return `Previously detected — ${ago} inspection${ago === 1 ? "" : "s"} ago`;
}

export function FindingsPage() {
  const { session } = useAuth();
  const canManage = session?.role === "inspector" || session?.role === "admin";
  const [findings, setFindings] = useState<FindingDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const rows = await getFindings({
        severity: severity || undefined,
        status: (status as FindingStatus) || undefined,
      });
      setFindings(rows.map(mapFindingDetail));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load findings");
    } finally {
      setLoading(false);
    }
  }, [severity, status]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleUpdate(findingId: string, nextStatus: FindingStatus) {
    setUpdatingId(findingId);
    try {
      await updateFinding(findingId, {
        status: nextStatus,
        resolution_notes: notes[findingId]?.trim() || undefined,
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update finding");
    } finally {
      setUpdatingId(null);
    }
  }

  if (error && findings.length === 0 && !loading) {
    return (
      <PageAlert
        message="Could not load findings."
        detail={error}
        onRetry={() => void load()}
      />
    );
  }

  return (
    <>
      <section className="panel">
        <div className="panel__head">
          <h2 className="panel__title">Findings</h2>
        </div>
        <div className="filter-row">
          <label className="form-field form-field--inline">
            <span>Severity</span>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
            >
              {SEVERITY_OPTIONS.map((opt) => (
                <option key={opt || "all"} value={opt}>
                  {opt ? opt : "All severities"}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field form-field--inline">
            <span>Status</span>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt || "all"} value={opt}>
                  {opt ? opt.replace("_", " ") : "All statuses"}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {loading ? (
        <p className="muted">Loading findings…</p>
      ) : findings.length === 0 ? (
        <section className="panel">
          <div className="empty">
            <div className="empty__title">No findings match</div>
            <p className="muted">Adjust filters or run an inspection to generate findings.</p>
          </div>
        </section>
      ) : (
        <div className="findings">
          {findings.map((f) => (
            <article className="finding finding--actionable" key={f.id}>
              <div
                className="finding__thumb"
                style={{
                  background: severityFill[f.severity],
                  borderColor: severityColor[f.severity],
                  color: severityColor[f.severity],
                }}
              >
                {f.zone}
              </div>
              <div className="finding__body">
                <div className="finding__top">
                  <span className={`sev ${severityClass[f.severity]}`}>
                    <span className="sev__dot" />
                    {severityLabel[f.severity]}
                  </span>
                  <span className="finding__title">{f.title}</span>
                  <span className="status-badge status-badge--neutral">
                    {f.status.replace("_", " ")}
                  </span>
                </div>
                <div className="finding__desc">
                  {f.location} ·{" "}
                  <span className="mono">{Math.round(f.confidence * 100)}%</span>{" "}
                  confidence ·{" "}
                  <Link
                    to={ROUTES.inspectionDetail(f.inspectionId)}
                    className="text-link"
                  >
                    View inspection
                  </Link>
                </div>
                <span
                  className={`finding__change ${
                    f.firstDetectedInspectionsAgo === 0 ? "is-new" : "is-old"
                  }`}
                >
                  <span className="finding__change-dot" />
                  {changeLabel(f.firstDetectedInspectionsAgo)}
                </span>
                {canManage &&
                (f.status === "open" || f.status === "acknowledged") ? (
                  <div className="finding__actions">
                    <input
                      className="finding__notes"
                      placeholder="Resolution notes (optional)"
                      value={notes[f.id] ?? ""}
                      onChange={(e) =>
                        setNotes((cur) => ({ ...cur, [f.id]: e.target.value }))
                      }
                    />
                    {f.status === "open" ? (
                      <button
                        className="ghost-btn"
                        disabled={updatingId === f.id}
                        onClick={() => void handleUpdate(f.id, "acknowledged")}
                      >
                        Acknowledge
                      </button>
                    ) : null}
                    <button
                      className="ghost-btn"
                      disabled={updatingId === f.id}
                      onClick={() => void handleUpdate(f.id, "resolved")}
                    >
                      Resolve
                    </button>
                    <button
                      className="ghost-btn"
                      disabled={updatingId === f.id}
                      onClick={() => void handleUpdate(f.id, "false_positive")}
                    >
                      False positive
                    </button>
                  </div>
                ) : null}
                {(f.status === "resolved" || f.status === "false_positive") &&
                f.resolutionNotes ? (
                  <p className="finding__resolution muted">
                    Resolution: {f.resolutionNotes}
                  </p>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
