export function SamsaraPage() {
  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Samsara integration</h2>
      </div>
      <div className="empty">
        <div className="empty__title">Not configured yet</div>
        <p className="muted">
          Telematics integration with Samsara is planned but not wired up. Asset
          sync, trip context, and automated inspection triggers will appear here
          once configured.
        </p>
      </div>
    </section>
  );
}
