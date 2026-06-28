export function SettingsPage() {
  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Settings</h2>
      </div>
      <div className="empty">
        <div className="empty__title">Not configured yet</div>
        <p className="muted">
          User accounts, roles, fleet organization, and API keys are not
          available in this MVP. Access is currently scoped via a service-level
          API key on the backend.
        </p>
      </div>
    </section>
  );
}
