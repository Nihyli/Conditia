export function PlaceholderView({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="panel">
      <div className="empty">
        <div className="empty__title">{title}</div>
        <p className="muted">{description}</p>
      </div>
    </section>
  );
}
