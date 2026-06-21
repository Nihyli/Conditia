import { useCallback, useEffect, useState } from "react";
import {
  getDataStatus,
  seedDemoData,
  unseedAllData,
  type ApiDataStatus,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import { canAccessAdmin } from "../auth/types";
import { PlaceholderView } from "./PlaceholderView";

export function SettingsView({
  onDataChanged,
}: {
  onDataChanged: () => void;
}) {
  const { user } = useAuth();
  const [status, setStatus] = useState<ApiDataStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"seed" | "unseed" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await getDataStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load data status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleSeed(force: boolean) {
    setBusy("seed");
    setMessage(null);
    setError(null);
    try {
      const result = await seedDemoData(force);
      setMessage(result.message);
      if (result.seeded) {
        await refresh();
        onDataChanged();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Seed failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleUnseed() {
    const ok = window.confirm(
      "Remove all trucks, inspections, findings, and uploaded media? This cannot be undone."
    );
    if (!ok) return;

    setBusy("unseed");
    setMessage(null);
    setError(null);
    try {
      const result = await unseedAllData(true);
      setMessage(result.message);
      await refresh();
      onDataChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unseed failed");
    } finally {
      setBusy(null);
    }
  }

  if (!user || !canAccessAdmin(user.role)) {
    return (
      <PlaceholderView
        title="Settings"
        description="Fleet preferences, user management, and integrations are coming soon. Contact an admin for data management."
      />
    );
  }

  return (
    <div className="settings">
      <section className="panel">
        <div className="panel__head">
          <h2 className="panel__title">Data management</h2>
        </div>

        <div className="settings__body">
          <p className="muted settings__lead">
            Load the Midwest Freight demo fleet for testing, or wipe everything
            for a clean slate.
          </p>

          {loading ? (
            <p className="muted">Loading status…</p>
          ) : status ? (
            <dl className="settings__stats">
              <div>
                <dt>Trucks</dt>
                <dd>{status.trucks}</dd>
              </div>
              <div>
                <dt>Inspections</dt>
                <dd>{status.inspections}</dd>
              </div>
              <div>
                <dt>Findings</dt>
                <dd>{status.findings}</dd>
              </div>
              <div>
                <dt>Media files</dt>
                <dd>{status.storage_files}</dd>
              </div>
            </dl>
          ) : null}

          {error ? <p className="error-note">{error}</p> : null}
          {message ? <p className="settings__message">{message}</p> : null}

          <div className="settings__actions">
            {status?.has_data ? (
              <button
                type="button"
                className="primary-btn"
                disabled={busy !== null}
                onClick={() => void handleSeed(true)}
              >
                {busy === "seed" ? "Seeding…" : "Replace with demo data"}
              </button>
            ) : (
              <button
                type="button"
                className="primary-btn"
                disabled={busy !== null}
                onClick={() => void handleSeed(false)}
              >
                {busy === "seed" ? "Seeding…" : "Seed demo data"}
              </button>
            )}

            <button
              type="button"
              className="danger-btn"
              disabled={busy !== null || !status?.has_data}
              onClick={() => void handleUnseed()}
            >
              {busy === "unseed" ? "Clearing…" : "Clear all data"}
            </button>
          </div>

          {status?.has_data && !busy ? (
            <p className="muted settings__hint">
              “Replace with demo data” clears your current fleet first, then loads{" "}
              {status.demo_fleet_name ?? "the demo fleet"} ({5} trucks with sample
              findings).
            </p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
