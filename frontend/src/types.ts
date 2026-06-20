export interface Inspection {
  id: string;
  truckId: string;
  /** Human-readable truck id (license plate or VIN). */
  truckLabel: string;
  make: string;
  model: string;
  capturedAtLabel: string;
  relativeLabel: string;
  source: CaptureSource;
  status: "complete" | "processing" | "pending" | "failed";
  findings: Finding[];
}

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
  confidence: number;
  zone: DamageZone;
  firstDetectedInspectionsAgo: number;
}

export interface FleetStat {
  id: string;
  label: string;
  value: string;
  icon: string;
  trendLabel: string;
  trendKind: "up" | "down" | "alert" | "neutral";
}
