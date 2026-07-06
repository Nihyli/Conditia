import { useEffect, useState } from "react";
import { resolveMediaUrl } from "../api";
import { useAuth } from "../auth/AuthProvider";
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

function useResolvedMediaUrls(
  media: InspectionMedia[],
  authMode: string | undefined
): Record<string, string> {
  const [urls, setUrls] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    const sorted = sortMedia(media);

    async function load() {
      const next: Record<string, string> = {};
      for (const item of sorted) {
        if (authMode === "jwt") {
          try {
            next[item.id] = await resolveMediaUrl(item.id);
          } catch {
            next[item.id] = "";
          }
        } else {
          next[item.id] = `/api/inspection-media/${encodeURIComponent(item.id)}/content`;
        }
      }
      if (!cancelled) {
        setUrls(next);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [media, authMode]);

  return urls;
}

export function InspectionMediaViewer({
  media,
}: {
  media: InspectionMedia[];
}) {
  const { session } = useAuth();
  const sorted = sortMedia(media);
  const urls = useResolvedMediaUrls(media, session?.auth_mode);
  const [activeId, setActiveId] = useState<string | null>(
    sorted[0]?.id ?? null
  );

  const active = sorted.find((m) => m.id === activeId) ?? sorted[0] ?? null;
  const activeUrl = active ? urls[active.id] : undefined;

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
        {!activeUrl ? (
          <p className="muted media-viewer__status">Loading media…</p>
        ) : active?.mediaType === "video" ? (
          <video
            key={active.id}
            className="media-viewer__player"
            src={activeUrl}
            controls
            playsInline
          />
        ) : active ? (
          <img
            className="media-viewer__player"
            src={activeUrl}
            alt={formatAngle(active.captureAngle)}
          />
        ) : null}
      </div>

      <div className="media-viewer__thumbs">
        {sorted.map((item) => {
          const thumbUrl = urls[item.id];
          return (
            <button
              key={item.id}
              type="button"
              className={`media-thumb${item.id === active?.id ? " is-active" : ""}`}
              onClick={() => setActiveId(item.id)}
            >
              {!thumbUrl ? (
                <span className="media-thumb__label">…</span>
              ) : item.mediaType === "video" ? (
                <video
                  className="media-thumb__img"
                  src={thumbUrl}
                  muted
                  playsInline
                  preload="metadata"
                />
              ) : (
                <img
                  className="media-thumb__img"
                  src={thumbUrl}
                  alt={formatAngle(item.captureAngle)}
                />
              )}
              <span className="media-thumb__label">
                {formatAngle(item.captureAngle)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
