import type { ApiInspectionSummary } from "../api";
import type { Finding, Inspection, InspectionMedia } from "../types";

export const finding: Finding = {
  id: "finding-1",
  title: "Front bumper dent",
  type: "dent",
  severity: "medium",
  location: "Front bumper",
  confidence: 0.87,
  zone: "front",
  firstDetectedInspectionsAgo: 0,
};

export const photo: InspectionMedia = {
  id: "media-photo",
  mediaType: "photo",
  captureAngle: "front",
  storagePath: "inspection/front/photo.png",
  capturedAt: "2026-06-21T12:00:00Z",
};

export const video: InspectionMedia = {
  id: "media-video",
  mediaType: "video",
  captureAngle: "rear",
  storagePath: "inspection/rear/video.webm",
  capturedAt: "2026-06-21T12:01:00Z",
};

export function inspection(overrides: Partial<Inspection> = {}): Inspection {
  return {
    id: "inspection-1",
    truckId: "truck-1",
    truckLabel: "TRK-001",
    make: "Volvo",
    model: "VNL",
    capturedAtLabel: "Today, 12:00 PM",
    relativeLabel: "5 min ago",
    source: "mobile",
    status: "complete",
    findings: [finding],
    media: [photo, video],
    ...overrides,
  };
}

export function apiInspection(
  overrides: Partial<ApiInspectionSummary> = {}
): ApiInspectionSummary {
  return {
    id: "inspection-1",
    truck_id: "truck-1",
    truck_label: "TRK-001",
    make: "Volvo",
    model: "VNL",
    started_at: "2026-06-21T12:00:00Z",
    status: "complete",
    capture_source: "mobile",
    finding_count: 1,
    worst_severity: "medium",
    findings: [
      {
        id: "finding-1",
        inspection_id: "inspection-1",
        title: "Front bumper dent",
        finding_type: "dent",
        severity: "medium",
        confidence: 0.87,
        status: "open",
        zone: "front",
        location: "Front bumper",
        first_seen_inspection_id: "inspection-1",
        first_detected_inspections_ago: 0,
      },
    ],
    media: [
      {
        id: "media-photo",
        inspection_id: "inspection-1",
        media_type: "photo",
        capture_angle: "front",
        capture_source: "mobile",
        storage_path: "inspection/front/photo.png",
        captured_at: "2026-06-21T12:00:00Z",
      },
    ],
    ...overrides,
  };
}
