import type { DamageZone, Finding, Inspection, Severity } from "../types";
import { IconDownload } from "./icons";

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
  trailer_mid: "mid",
  trailer_rear: "rear",
  passenger_side: "side",
  driver_side: "side",
};

// Clickable/paintable regions over the truck silhouette (side profile, cab right).
const zoneBoxes: { zone: DamageZone; x: number; w: number; cx: number }[] = [
  { zone: "trailer_rear", x: 34, w: 104, cx: 86 },
  { zone: "trailer_mid", x: 138, w: 104, cx: 190 },
  { zone: "trailer_front", x: 242, w: 104, cx: 294 },
  { zone: "cab", x: 384, w: 132, cx: 446 },
];

function zoneSeverity(findings: Finding[], zone: DamageZone): Severity | null {
  const inZone = findings.filter((f) => f.zone === zone);
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
  return (
    <svg className="dmap__svg" viewBox="0 0 560 200" role="img" aria-label="Truck damage map">
      {/* zone tints */}
      {zoneBoxes.map(({ zone, x, w }) => {
        const sev = zoneSeverity(findings, zone);
        return (
          <rect
            key={zone}
            x={x}
            y={62}
            width={w}
            height={86}
            rx={6}
            fill={sev ? sevFill[sev] : "var(--surface-2)"}
            stroke={sev ? sevColor[sev] : "var(--border)"}
            strokeWidth={sev ? 1.5 : 1}
            opacity={sev ? 1 : 0.6}
          />
        );
      })}

      {/* trailer outline */}
      <rect x={30} y={58} width={320} height={94} rx={8} fill="none" stroke="var(--border-strong)" strokeWidth={2} />

      {/* cab body */}
      <path
        d="M384 152 V96 q0-10 10-10 h44 l30 34 v32 z"
        fill="none"
        stroke="var(--border-strong)"
        strokeWidth={2}
        strokeLinejoin="round"
      />
      {/* windshield */}
      <path d="M452 92 l24 28 h-24 z" fill="var(--surface-2)" stroke="var(--border)" strokeWidth={1.4} />
      {/* exhaust stacks */}
      <line x1={392} y1={58} x2={392} y2={86} stroke="var(--border-strong)" strokeWidth={3} strokeLinecap="round" />
      <line x1={400} y1={54} x2={400} y2={86} stroke="var(--border-strong)" strokeWidth={3} strokeLinecap="round" />

      {/* wheels */}
      {[88, 132, 250, 294, 456, 498].map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy={156} r={13} fill="var(--surface)" stroke="var(--border-strong)" strokeWidth={2.5} />
          <circle cx={cx} cy={156} r={4} fill="var(--border-strong)" />
        </g>
      ))}

      {/* severity markers per zone */}
      {zoneBoxes.map(({ zone, cx }) => {
        const sev = zoneSeverity(findings, zone);
        if (!sev) return null;
        return (
          <g key={`m-${zone}`}>
            <circle cx={cx} cy={105} r={13} fill={sevColor[sev]} />
            <circle cx={cx} cy={105} r={17} fill="none" stroke={sevColor[sev]} strokeWidth={1.5} opacity={0.35} />
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
          {inspection.truckId} — Damage map
        </h2>
        <div className="panel__spacer" />
        <button className="ghost-btn">
          <IconDownload />
          Export PDF
        </button>
      </div>

      <div className="dmap__sub">
        <span className="dmap__model">
          {inspection.make} {inspection.model}
        </span>
        <span className="dmap__when">Inspected {inspection.capturedAtLabel.replace(/^.*,\s*/, "")}</span>
      </div>

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
            <div className="empty__title">No findings</div>
            This inspection came back clear.
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
