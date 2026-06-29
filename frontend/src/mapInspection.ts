import type {
  ApiFinding,
  ApiFleetStats,
  ApiInspectionSummary,
  ApiMedia,
} from "./api";
import { formatCapturedAt } from "./formatTime";
import { parseSeverity } from "./severity";
import type {
  CaptureSource,
  DamageZone,
  Finding,
  FindingDetail,
  FleetStat,
  Inspection,
} from "./types";

const ZONE_ALIASES: Record<string, DamageZone> = {
  rear: "trailer_rear",
};

const VALID_ZONES = new Set<string>([
  "front",
  "cab",
  "trailer_front",
  "trailer_mid",
  "trailer_rear",
  "passenger_side",
  "driver_side",
  ...Object.keys(ZONE_ALIASES),
]);

const VALID_FINDING_TYPES = new Set<Finding["type"]>([
  "dent",
  "scratch",
  "crack",
  "missing_component",
  "rust",
  "anomaly",
]);

const VALID_SOURCES = new Set<CaptureSource>([
  "mobile",
  "drone",
  "fixed_camera",
]);

const VALID_STATUSES = new Set<Inspection["status"]>([
  "uploading",
  "submitted",
  "processing",
  "complete",
  "review_required",
  "failed",
]);

function normalizeZone(zone: string | null): DamageZone {
  if (!zone) return "unknown";
  if (zone in ZONE_ALIASES) return ZONE_ALIASES[zone];
  if (VALID_ZONES.has(zone)) return zone as DamageZone;
  return "unknown";
}

function normalizeFindingType(raw: string): Finding["type"] {
  return VALID_FINDING_TYPES.has(raw as Finding["type"])
    ? (raw as Finding["type"])
    : "anomaly";
}

function parseSource(raw: string): CaptureSource {
  if (VALID_SOURCES.has(raw as CaptureSource)) return raw as CaptureSource;
  throw new Error(`Unsupported capture source: ${raw}`);
}

function parseStatus(raw: string): Inspection["status"] {
  if (VALID_STATUSES.has(raw as Inspection["status"])) {
    return raw as Inspection["status"];
  }
  throw new Error(`Unsupported inspection status: ${raw}`);
}

function mapFinding(f: ApiFinding): Finding {
  return {
    id: f.id,
    title: f.title ?? f.finding_type,
    type: normalizeFindingType(f.finding_type),
    severity: parseSeverity(f.severity),
    location: f.location ?? "Unknown location",
    confidence: f.confidence,
    zone: normalizeZone(f.zone),
    firstDetectedInspectionsAgo: f.first_detected_inspections_ago,
  };
}

function mapMedia(m: ApiMedia) {
  return {
    id: m.id,
    mediaType: m.media_type,
    captureAngle: m.capture_angle,
    capturedAt: m.captured_at,
  };
}

export function mapFindingDetail(f: ApiFinding): FindingDetail {
  return {
    ...mapFinding(f),
    inspectionId: f.inspection_id,
    status: f.status,
    firstSeenInspectionId: f.first_seen_inspection_id,
    resolutionNotes: f.resolution_notes,
  };
}

export function mapInspectionSummary(row: ApiInspectionSummary): Inspection {
  const { capturedAtLabel, relativeLabel } = formatCapturedAt(row.started_at);
  return {
    id: row.id,
    truckId: row.truck_id,
    truckLabel: row.truck_label,
    make: row.make ?? "",
    model: row.model ?? "",
    capturedAtLabel,
    relativeLabel,
    source: parseSource(row.capture_source),
    status: parseStatus(row.status),
    findings: row.findings.map(mapFinding),
    media: (row.media ?? []).map(mapMedia),
    startedAt: row.started_at,
  };
}

export function mapFleetStats(stats: ApiFleetStats): FleetStat[] {
  return [
    {
      id: "active",
      label: "Active trucks",
      value: String(stats.active_trucks),
      icon: "truck",
      trendLabel:
        stats.active_trucks === 0 ? "Register trucks to begin" : "In fleet",
      trendKind: stats.active_trucks > 0 ? "up" : "neutral",
    },
    {
      id: "today",
      label: "Inspections today",
      value: String(stats.inspections_today),
      icon: "clipboard",
      trendLabel:
        stats.inspections_pending > 0
          ? `${stats.inspections_pending} pending · ${stats.inspections_complete_today} complete`
          : `${stats.inspections_complete_today} complete today`,
      trendKind: "neutral",
    },
    {
      id: "findings",
      label: "Open findings",
      value: String(stats.open_findings),
      icon: "alert",
      trendLabel:
        stats.open_findings === 0 ? "No findings recorded" : "Across all inspections",
      trendKind: stats.open_findings > 0 ? "alert" : "neutral",
    },
    {
      id: "pending",
      label: "Awaiting analysis",
      value: String(stats.inspections_pending),
      icon: "clock",
      trendLabel:
        stats.inspections_pending === 0
          ? "All caught up"
          : "Processing in background",
      trendKind: stats.inspections_pending > 0 ? "neutral" : "down",
    },
  ];
}
