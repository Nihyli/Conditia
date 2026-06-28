import type { DamageZone, Finding, Inspection, Severity } from "../types";
import {
  severityClass,
  severityColor,
  severityFill,
  severityLabel,
  severityRank,
} from "../severity";
import { IconDownload } from "./icons";
import { InspectionMediaViewer } from "./InspectionMediaViewer";
import {
  silhouetteSeverity,
  silhouetteZones,
} from "./truckSilhouetteZones";

const zoneCaption: Record<DamageZone, string> = {
  front: "front",
  cab: "cab",
  trailer_front: "trailer",
  trailer_mid: "mid",
  trailer_rear: "rear",
  passenger_side: "side",
  driver_side: "side",
  unknown: "unknown",
};

const CAB_PATH =
  "M355 152 L355 90 Q358 80 375 72 L430 60 Q468 54 498 66 L518 84 Q526 96 528 112 L528 152 Z";

function ChangeLine({ ago }: { ago: number }) {
  if (ago === 0) {
    return (
      <span className="finding__change is-new">
        <span className="finding__change-dot" />
        New — first detected this inspection
      </span>
    );
  }
  return (
    <span className="finding__change is-old">
      <span className="finding__change-dot" />
      Previously detected — {ago} inspection{ago === 1 ? "" : "s"} ago
    </span>
  );
}

function TruckSilhouette({ findings }: { findings: Finding[] }) {
  const cabSev = silhouetteSeverity(findings, "cab");
  const trailerZones = silhouetteZones.filter((z) => z.zone !== "cab");

  return (
    <svg className="dmap__svg" viewBox="0 0 560 210" role="img" aria-label="Truck damage map">
      {/* Trailer zone tints (under the outline) */}
      {trailerZones.map(({ zone, x, w }) => {
        const sev = silhouetteSeverity(findings, zone);
        return (
          <rect
            key={zone}
            x={x}
            y={58}
            width={w}
            height={94}
            rx={6}
            fill={sev ? severityFill[sev] : "var(--surface-2)"}
            stroke={sev ? severityColor[sev] : "var(--border)"}
            strokeWidth={sev ? 2 : 1}
            opacity={sev ? 1 : 0.55}
          />
        );
      })}

      {/* Trailer outline */}
      <rect
        x={24}
        y={58}
        width={320}
        height={94}
        rx={8}
        fill="none"
        stroke="var(--border-strong)"
        strokeWidth={2}
      />

      {/* Fifth wheel neck */}
      <path
        d="M344 100 Q356 100 358 110 L360 152 L344 152 Z"
        fill="var(--surface-2)"
        stroke="var(--border-strong)"
        strokeWidth={1.5}
        opacity={0.35}
      />

      {/* Exhaust stacks */}
      <rect x={360} y={30} width={5} height={62} rx={2.5} fill="var(--border-strong)" opacity={0.35} />
      <rect x={370} y={24} width={5} height={68} rx={2.5} fill="var(--border-strong)" opacity={0.35} />
      <ellipse cx={362.5} cy={30} rx={5} ry={3} fill="var(--border-strong)" opacity={0.3} />
      <ellipse cx={372.5} cy={24} rx={5} ry={3} fill="var(--border-strong)" opacity={0.3} />

      {/* Cab body — severity fill is on the body itself so it is not painted over */}
      <path
        d={CAB_PATH}
        fill={cabSev ? severityFill[cabSev] : "var(--surface-2)"}
        stroke={cabSev ? severityColor[cabSev] : "var(--border-strong)"}
        strokeWidth={cabSev ? 2.5 : 2}
        strokeLinejoin="round"
      />

      {/* Windshield */}
      <path
        d="M498 68 L522 88 L528 130 L506 130 Z"
        fill="var(--surface)"
        stroke="var(--border)"
        strokeWidth={1.2}
        opacity={0.65}
      />

      {/* Hood crease */}
      <path
        d="M375 90 Q420 80 498 82"
        fill="none"
        stroke="var(--border-strong)"
        strokeWidth={1}
        opacity={0.15}
      />

      {/* Door outline */}
      <path
        d="M355 90 L390 90 L390 148 L355 148"
        fill="none"
        stroke="var(--border-strong)"
        strokeWidth={1}
        opacity={0.15}
      />

      {/* Door handle */}
      <rect x={386} y={118} width={10} height={4} rx={2} fill="var(--border-strong)" opacity={0.2} />

      {/* Side mirror */}
      <line
        x1={395}
        y1={94}
        x2={416}
        y2={88}
        stroke="var(--border-strong)"
        strokeWidth={2}
        strokeLinecap="round"
        opacity={0.4}
      />
      <rect
        x={416}
        y={82}
        width={14}
        height={10}
        rx={3}
        fill="var(--surface-2)"
        stroke="var(--border-strong)"
        strokeWidth={1.5}
        opacity={0.6}
      />

      {/* Headlight */}
      <rect
        x={514}
        y={118}
        width={12}
        height={8}
        rx={2}
        fill="var(--med-bg)"
        stroke="var(--med)"
        strokeWidth={1}
        opacity={0.7}
      />

      {/* Fuel tank */}
      <rect
        x={356}
        y={126}
        width={20}
        height={26}
        rx={4}
        fill="var(--surface-2)"
        stroke="var(--border-strong)"
        strokeWidth={1.2}
        opacity={0.4}
      />

      {/* Wheels */}
      {[88, 132, 250, 294, 408, 452].map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy={156} r={13} fill="var(--surface)" stroke="var(--border-strong)" strokeWidth={2.5} />
          <circle cx={cx} cy={156} r={4} fill="var(--border-strong)" />
        </g>
      ))}

      {/* Severity markers — one per silhouette region */}
      {silhouetteZones.map(({ zone, cx, cy }) => {
        const sev = silhouetteSeverity(findings, zone);
        if (!sev) return null;
        return (
          <g key={`m-${zone}`} aria-label={`${zone} ${sev}`}>
            <circle cx={cx} cy={cy} r={17} fill={severityColor[sev]} opacity={0.15} />
            <circle cx={cx} cy={cy} r={13} fill={severityColor[sev]} />
            <circle
              cx={cx}
              cy={cy}
              r={17}
              fill="none"
              stroke={severityColor[sev]}
              strokeWidth={1.5}
              opacity={0.35}
            />
            <text x={cx} y={cy + 5} textAnchor="middle" fontSize={15} fontWeight={800} fill="white">
              !
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const legend: { sev: Severity }[] = [
  { sev: "critical" },
  { sev: "medium" },
  { sev: "low" },
  { sev: "clear" },
];

export function DamageMap({ inspection }: { inspection: Inspection }) {
  const sorted = [...inspection.findings].sort(
    (a, b) => severityRank[b.severity] - severityRank[a.severity]
  );

  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">
          {inspection.truckLabel} — Damage map
        </h2>
        <div className="panel__spacer" />
        <button className="ghost-btn" disabled title="PDF export is not available yet">
          <IconDownload />
          Export PDF
        </button>
      </div>

      <div className="dmap__sub">
        <span className="dmap__model">
          {[inspection.make, inspection.model].filter(Boolean).join(" ") ||
            inspection.truckLabel}
        </span>
        <span className="dmap__when">
          {inspection.capturedAtLabel} · {inspection.relativeLabel}
        </span>
      </div>

      <InspectionMediaViewer key={inspection.id} media={inspection.media} />

      <div className="dmap__stage">
        <TruckSilhouette findings={inspection.findings} />
        <p className="dmap__hint">Tap a zone to inspect</p>
      </div>

      <div className="legend">
        {legend.map(({ sev }) => (
          <span className="legend__item" key={sev}>
            <span className="legend__dot" style={{ background: severityColor[sev] }} />
            {severityLabel[sev]}
          </span>
        ))}
      </div>

      <div className="findings">
        {sorted.length === 0 ? (
          <div className="empty">
            <div className="empty__title">
              {inspection.status === "review_required"
                ? "Manual review required"
                : "No findings yet"}
            </div>
            {inspection.status === "review_required"
              ? "Automated analysis was unavailable or experimental. This is not a clear result; review the captured media above."
              : "Analysis has not detected damage on this inspection, or processing is still running. Review the captured media above."}
          </div>
        ) : (
          sorted.map((f) => (
            <article className="finding" key={f.id}>
              <div
                className="finding__thumb"
                style={{
                  background: severityFill[f.severity],
                  borderColor: severityColor[f.severity],
                  color: severityColor[f.severity],
                }}
              >
                {zoneCaption[f.zone]}
              </div>
              <div className="finding__body">
                <div className="finding__top">
                  <span className={`sev ${severityClass[f.severity]}`}>
                    <span className="sev__dot" />
                    {severityLabel[f.severity]}
                  </span>
                  <span className="finding__title">{f.title}</span>
                </div>
                <div className="finding__desc">
                  {f.location} ·{" "}
                  <span className="mono">{Math.round(f.confidence * 100)}%</span>{" "}
                  confidence
                </div>
                <ChangeLine ago={f.firstDetectedInspectionsAgo} />
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
