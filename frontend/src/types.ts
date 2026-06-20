export type Severity = "critical" | "medium" | "low" | "clear";

export type CaptureSource = "mobile" | "drone" | "fixed_camera";

export type DamageZone =
  | "front"
  | "cab"
  | "trailer_front"
  | "trailer_mid"
  | "trailer_rear"
  | "passenger_side"
  | "driver_side";

export interface Finding {
  id: string;
  title: string;
  type: "dent" | "scratch" | "crack" | "missing_component" | "rust" | "anomaly";
  severity: Severity;
  location: string;
  confidence: number; // 0..1
  zone: DamageZone;
  /**
   * Change-detection summary. inspectionsAgo === 0 means first seen this
   * inspection (i.e. brand new). > 0 means previously detected N inspections ago.
   */
  firstDetectedInspectionsAgo: number;
}

export interface Inspection {
  id: string;
  truckId: string;
  make: string;
  model: string;
  capturedAtLabel: string; // e.g. "Today, 9:14 AM"
  relativeLabel: string; // e.g. "6 min ago"
  source: CaptureSource;
  status: "complete" | "processing" | "pending";
  findings: Finding[];
}

export interface FleetStat {
  id: string;
  label: string;
  value: string;
  icon: string;
  trendLabel: string;
  trendKind: "up" | "down" | "alert" | "neutral";
}
