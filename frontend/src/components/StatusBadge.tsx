import type { Inspection } from "../types";

const labels: Record<Inspection["status"], string> = {
  uploading: "Uploading",
  submitted: "Submitted",
  processing: "Processing",
  complete: "Complete",
  review_required: "Review required",
  failed: "Failed",
};

const classes: Record<Inspection["status"], string> = {
  uploading: "status-badge status-badge--neutral",
  submitted: "status-badge status-badge--neutral",
  processing: "status-badge status-badge--active",
  complete: "status-badge status-badge--ok",
  review_required: "status-badge status-badge--warn",
  failed: "status-badge status-badge--fail",
};

export function StatusBadge({ status }: { status: Inspection["status"] }) {
  return <span className={classes[status]}>{labels[status]}</span>;
}
