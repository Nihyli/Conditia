import { useAuth } from "../auth/AuthProvider";

const AUTH_MODE_LABEL: Record<string, string> = {
  jwt: "User session (JWT)",
  api_key: "Service API key",
  disabled: "Disabled (local development)",
};

const ROLE_CAPABILITIES: { role: string; summary: string }[] = [
  {
    role: "viewer",
    summary:
      "Read-only access to the dashboard, trucks, inspections, findings, and reports.",
  },
  {
    role: "inspector",
    summary:
      "Everything a viewer can do, plus capturing inspections and updating or resolving findings.",
  },
  {
    role: "admin",
    summary:
      "Full fleet access, including service integrations and (planned) member management.",
  },
];

export function SettingsPage() {
  const { session, signOut } = useAuth();
  const authMode = session?.auth_mode ?? "disabled";
  const role = session?.role ?? null;

  return (
    <>
      <section className="panel">
        <div className="panel__head">
          <h2 className="panel__title">Account &amp; access</h2>
          <div className="panel__spacer" />
          {authMode === "jwt" ? (
            <button type="button" className="ghost-btn" onClick={signOut}>
              Sign out
            </button>
          ) : null}
        </div>
        <dl className="detail-grid">
          <div>
            <dt>Signed-in user</dt>
            <dd className="mono">{session?.user_id ?? "—"}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>
              {role ? (
                <span className="status-badge status-badge--active">{role}</span>
              ) : (
                "—"
              )}
            </dd>
          </div>
          <div>
            <dt>Fleet</dt>
            <dd className="mono">{session?.fleet_id ?? "—"}</dd>
          </div>
          <div>
            <dt>Authentication</dt>
            <dd>{AUTH_MODE_LABEL[authMode] ?? authMode}</dd>
          </div>
        </dl>
        {authMode === "disabled" ? (
          <p className="muted" style={{ padding: "0 var(--space-20) var(--space-16)" }}>
            Authentication is disabled for local development, so every request
            runs with full access. Set <code>AUTH_MODE=jwt</code> in{" "}
            <code>backend/.env</code> to test real sign-in, roles, and fleet
            scoping.
          </p>
        ) : null}
      </section>

      <section className="panel">
        <div className="panel__head">
          <h2 className="panel__title">Roles &amp; permissions</h2>
        </div>
        <div className="insp-list">
          {ROLE_CAPABILITIES.map((entry) => (
            <div
              key={entry.role}
              className={`insp-row${entry.role === role ? " is-active" : ""}`}
            >
              <span className="insp-row__id">{entry.role}</span>
              <span className="insp-row__meta">
                <span className="insp-row__truck">{entry.summary}</span>
              </span>
              {entry.role === role ? (
                <span className="status-badge status-badge--active">Current</span>
              ) : (
                <span />
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <h2 className="panel__title">Not available yet</h2>
        </div>
        <div className="empty">
          <div className="empty__title">Organization management is coming</div>
          <p className="muted">
            Inviting users, editing fleet membership and roles, switching
            organizations, and managing service API keys aren&apos;t in the
            console yet. Memberships are provisioned directly in the backend
            (<code>fleet_memberships</code>).
          </p>
        </div>
      </section>
    </>
  );
}
