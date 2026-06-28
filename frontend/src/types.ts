export interface Inspection {
  id: string;
  truckId: string;
  truckLabel: string;
  make: string;
  model: string;
  capturedAtLabel: string;
  relativeLabel: string;
  source: CaptureSource;
  status:
    | "uploading"
    | "submitted"
    | "processing"
    | "complete"
    | "review_required"
    | "failed";
  findings: Finding[];
  media: InspectionMedia[];
  startedAt: string;
}

export interface InspectionMedia {
  id: string;
  mediaType: "photo" | "video";
  captureAngle: string | null;
  storagePath: string;
  capturedAt: string;
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
  | "driver_side"
  | "unknown";

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

export type FindingStatus =
  | "open"
  | "acknowledged"
  | "resolved"
  | "false_positive";

export interface FindingDetail extends Finding {
  inspectionId: string;
  status: FindingStatus;
  firstSeenInspectionId: string | null;
}

export interface FleetStat {
  id: string;
  label: string;
  value: string;
  icon: string;
  trendLabel: string;
  trendKind: "up" | "down" | "alert" | "neutral";
}
