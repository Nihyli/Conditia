import { IconRefresh } from "./icons";

export function PageAlert({
  message,
  detail,
  onRetry,
}: {
  message: string;
  detail?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="dashboard-alert">
      <p className="error-note">{message}</p>
      {detail ? <p className="muted">{detail}</p> : null}
      {onRetry ? (
        <button className="primary-btn" onClick={onRetry}>
          <IconRefresh size={16} />
          Retry
        </button>
      ) : null}
    </div>
  );
}
