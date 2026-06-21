import { useState } from "react";
import { mediaUrl } from "../api";
import type { InspectionMedia } from "../types";

const ANGLE_ORDER = [
  "front",
  "driver_side",
  "rear",
  "passenger_side",
  "top",
  "undercarriage",
];

function formatAngle(angle: string | null): string {
  if (!angle) return "Unknown angle";
  return angle.replace(/_/g, " ");
}

function sortMedia(items: InspectionMedia[]): InspectionMedia[] {
  return [...items].sort((a, b) => {
    const ai = ANGLE_ORDER.indexOf(a.captureAngle ?? "");
    const bi = ANGLE_ORDER.indexOf(b.captureAngle ?? "");
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });
}

export function InspectionMediaViewer({
  media,
}: {
  media: InspectionMedia[];
}) {
  const sorted = sortMedia(media);
  const [activeId, setActiveId] = useState<string | null>(
    sorted[0]?.id ?? null
  );

  const active = sorted.find((m) => m.id === activeId) ?? sorted[0] ?? null;

  if (sorted.length === 0) {
    return (
      <div className="media-viewer">
        <p className="muted media-viewer__status">
          No photos or videos are attached to this inspection.
        </p>
      </div>
    );
  }

  return (
    <div className="media-viewer">
      <div className="media-viewer__head">
        <h3 className="media-viewer__title">Captured media</h3>
        <span className="muted">
          {sorted.length} clip{sorted.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="media-viewer__stage">
        {active?.mediaType === "video" ? (
          <video
            key={active.id}
            className="media-viewer__player"
            src={mediaUrl(active.id)}
            controls
            playsInline
          />
        ) : active ? (
          <img
            className="media-viewer__player"
            src={mediaUrl(active.id)}
            alt={formatAngle(active.captureAngle)}
          />
        ) : null}
      </div>

      <div className="media-viewer__thumbs">
        {sorted.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`media-thumb${item.id === active?.id ? " is-active" : ""}`}
            onClick={() => setActiveId(item.id)}
          >
            {item.mediaType === "video" ? (
              <video
                className="media-thumb__img"
                src={mediaUrl(item.id)}
                muted
                playsInline
                preload="metadata"
              />
            ) : (
              <img
                className="media-thumb__img"
                src={mediaUrl(item.id)}
                alt={formatAngle(item.captureAngle)}
              />
            )}
            <span className="media-thumb__label">
              {formatAngle(item.captureAngle)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
