import type { DamageZone, Finding, Severity } from "../types";
import { severityRank } from "../severity";

/** Regions on the side-profile damage map (cab faces right). */
export type SilhouetteZone = "trailer_rear" | "trailer_mid" | "trailer_front" | "cab";

export const silhouetteZones: {
  zone: SilhouetteZone;
  x: number;
  w: number;
  cx: number;
  cy: number;
}[] = [
  { zone: "trailer_rear", x: 24, w: 72, cx: 60, cy: 105 },
  { zone: "trailer_mid", x: 100, w: 188, cx: 194, cy: 105 },
  { zone: "trailer_front", x: 292, w: 52, cx: 318, cy: 105 },
  { zone: "cab", x: 355, w: 175, cx: 430, cy: 105 },
];

/**
 * Map API finding zones onto the four silhouette regions.
 * On a side profile with the cab on the right, vehicle "front" (bumper/headlight)
 * is the cab — not the trailer nose.
 */
export function resolveSilhouetteZone(zone: DamageZone): SilhouetteZone | null {
  switch (zone) {
    case "cab":
    case "front":
      return "cab";
    case "trailer_rear":
      return "trailer_rear";
    case "trailer_mid":
    case "driver_side":
    case "passenger_side":
      return "trailer_mid";
    case "trailer_front":
      return "trailer_front";
    default:
      return null;
  }
}

export function silhouetteSeverity(
  findings: Finding[],
  silhouetteZone: SilhouetteZone
): Severity | null {
  const inZone = findings.filter(
    (f) => resolveSilhouetteZone(f.zone) === silhouetteZone
  );
  if (inZone.length === 0) return null;
  return inZone.reduce<Severity>(
    (worst, f) =>
      severityRank[f.severity] > severityRank[worst] ? f.severity : worst,
    "clear"
  );
}
