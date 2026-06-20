/** Format API timestamps for the dashboard list. */

export function formatCapturedAt(iso: string): {
  capturedAtLabel: string;
  relativeLabel: string;
} {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);

  const timeStr = date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });

  const isToday = date.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday = date.toDateString() === yesterday.toDateString();

  let capturedAtLabel: string;
  if (isToday) capturedAtLabel = `Today, ${timeStr}`;
  else if (isYesterday) capturedAtLabel = `Yesterday, ${timeStr}`;
  else
    capturedAtLabel = date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });

  let relativeLabel: string;
  if (diffMin < 1) relativeLabel = "just now";
  else if (diffMin < 60) relativeLabel = `${diffMin} min ago`;
  else if (diffMin < 24 * 60) {
    const h = Math.floor(diffMin / 60);
    relativeLabel = `${h}h ${diffMin % 60}m ago`;
  } else if (isYesterday) relativeLabel = "yesterday";
  else relativeLabel = date.toLocaleDateString(undefined, { month: "short", day: "numeric" });

  return { capturedAtLabel, relativeLabel };
}
