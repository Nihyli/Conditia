import type { DamageZone, Finding, Inspection, Severity } from "../types";
import { IconDownload } from "./icons";
import { InspectionMediaViewer } from "./InspectionMediaViewer";

const sevColor: Record<Severity, string> = {
  critical: "var(--crit)",
  medium: "var(--med)",
  low: "var(--low)",
  clear: "var(--clear)",
};

const sevFill: Record<Severity, string> = {
  critical: "var(--crit-bg)",
  medium: "var(--med-bg)",
  low: "var(--low-bg)",
  clear: "var(--clear-bg)",
};

const sevLabel: Record<Severity, string> = {
  critical: "Critical",
  medium: "Medium",
  low: "Low",
  clear: "Clear",
};

const sevClass: Record<Severity, string> = {
  critical: "crit",
  medium: "medium",
  low: "low",
  clear: "clear",
};

const sevRank: Record<Severity, number> = {
  critical: 3,
  medium: 2,
  low: 1,
  clear: 0,
};

const zoneCaption: Record<DamageZone, string> = {
  front: "front",
  cab: "cab",
  trailer_front: "front",
  trailer_mid: "side",
  trailer_rear: "rear",
  passenger_side: "side",
  driver_side: "side",
};

/** Simplified damage-map regions (side profile). */
type DisplayZone = "rear" | "side" | "front" | "cab";

const API_ZONE_TO_DISPLAY: Record<DamageZone, DisplayZone> = {
  trailer_rear: "rear",
  trailer_mid: "side",
  trailer_front: "front",
  front: "front",
  cab: "cab",
  passenger_side: "side",
  driver_side: "side",
};

const zoneBoxes: { zone: DisplayZone; x: number; w: number; cx: number }[] = [
  { zone: "rear", x: 24, w: 72, cx: 60 },
  { zone: "side", x: 100, w: 188, cx: 194 },
  { zone: "front", x: 292, w: 52, cx: 318 },
  { zone: "cab", x: 355, w: 175, cx: 430 },
];

const CAB_PATH =
  "M355 152 L355 90 Q358 80 375 72 L430 60 Q468 54 498 66 L518 84 Q526 96 528 112 L528 152 Z";

function zoneSeverity(findings: Finding[], zone: DisplayZone): Severity | null {
  const inZone = findings.filter((f) => API_ZONE_TO_DISPLAY[f.zone] === zone);
  if (inZone.length === 0) return null;
  return inZone.reduce<Severity>(
    (worst, f) => (sevRank[f.severity] > sevRank[worst] ? f.severity : worst),
    "clear"
  );
}

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
  const cabSev = zoneSeverity(findings, "cab");

  return (
    <svg className="dmap__svg" viewBox="0 0 560 210" role="img" aria-label="Truck damage map">
      <defs>
        <clipPath id="cab-clip">
          <path d={CAB_PATH} />
        </clipPath>
      </defs>

      {/* Zone tints — trailer regions */}
      {zoneBoxes
        .filter((z) => z.zone !== "cab")
        .map(({ zone, x, w }) => {
          const sev = zoneSeverity(findings, zone);
          return (
            <rect
              key={zone}
              x={x}
              y={58}
              width={w}
              height={94}
              rx={6}
              fill={sev ? sevFill[sev] : "var(--surface-2)"}
              stroke={sev ? sevColor[sev] : "var(--border)"}
              strokeWidth={sev ? 1.5 : 1}
              opacity={sev ? 1 : 0.6}
            />
          );
        })}

      {/* Cab zone tint — clipped to cab shape */}
      <rect
        x={355}
        y={54}
        width={180}
        height={100}
        fill={cabSev ? sevFill[cabSev] : "var(--surface-2)"}
        clipPath="url(#cab-clip)"
        opacity={cabSev ? 0.7 : 0.4}
      />
      <path
        d={CAB_PATH}
        fill="none"
        stroke={cabSev ? sevColor[cabSev] : "var(--border)"}
        strokeWidth={cabSev ? 1.5 : 1}
        opacity={cabSev ? 0.6 : 0.4}
      />

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

      {/* Cab body */}
      <path
        d={CAB_PATH}
        fill="var(--surface-2)"
        stroke="var(--border-strong)"
        strokeWidth={2}
        strokeLinejoin="round"
      />

      {/* Windshield */}
      <path
        d="M498 68 L522 88 L528 130 L506 130 Z"
        fill="var(--surface-2)"
        stroke="var(--border)"
        strokeWidth={1.2}
        opacity={0.5}
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
          <circle
            cx={cx}
            cy={156}
            r={13}
            fill="var(--surface)"
            stroke="var(--border-strong)"
            strokeWidth={2.5}
          />
          <circle cx={cx} cy={156} r={4} fill="var(--border-strong)" />
        </g>
      ))}

      {/* Severity markers */}
      {zoneBoxes.map(({ zone, cx }) => {
        const sev = zoneSeverity(findings, zone);
        if (!sev) return null;
        return (
          <g key={`m-${zone}`}>
            <circle cx={cx} cy={105} r={17} fill={sevColor[sev]} opacity={0.15} />
            <circle cx={cx} cy={105} r={13} fill={sevColor[sev]} />
            <circle
              cx={cx}
              cy={105}
              r={17}
              fill="none"
              stroke={sevColor[sev]}
              strokeWidth={1.5}
              opacity={0.35}
            />
            <text x={cx} y={110} textAnchor="middle" fontSize={15} fontWeight={800} fill="white">
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
    (a, b) => sevRank[b.severity] - sevRank[a.severity]
  );

  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">
          {inspection.truckLabel} — Damage map
        </h2>
        <div className="panel__spacer" />
        <button className="ghost-btn">
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
            <span className="legend__dot" style={{ background: sevColor[sev] }} />
            {sevLabel[sev]}
          </span>
        ))}
      </div>

      <div className="findings">
        {sorted.length === 0 ? (
          <div className="empty">
            <div className="empty__title">No findings yet</div>
            Analysis has not detected damage on this inspection, or processing
            is still running. Review the captured media above.
          </div>
        ) : (
          sorted.map((f) => (
            <article className="finding" key={f.id}>
              <div
                className="finding__thumb"
                style={{
                  background: sevFill[f.severity],
                  borderColor: sevColor[f.severity],
                  color: sevColor[f.severity],
                }}
              >
                {zoneCaption[f.zone]}
              </div>
              <div className="finding__body">
                <div className="finding__top">
                  <span className={`sev ${sevClass[f.severity]}`}>
                    <span className="sev__dot" />
                    {sevLabel[f.severity]}
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
