import { describe, expect, it } from "vitest";
import type { ApiInspectionSummary } from "./api";
import { mapInspectionSummary } from "./mapInspection";

function inspection(
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
    worst_severity: "high",
    findings: [
      {
        id: "finding-1",
        inspection_id: "inspection-1",
        title: "Dent",
        finding_type: "dent",
        severity: "high",
        confidence: 0.9,
        status: "open",
        zone: null,
        location: null,
        first_seen_inspection_id: "inspection-1",
        first_detected_inspections_ago: 0,
      },
    ],
    media: [],
    ...overrides,
  };
}

describe("mapInspectionSummary", () => {
  it("normalizes documented aliases without inventing a damage zone", () => {
    const result = mapInspectionSummary(inspection());

    expect(result.findings[0].severity).toBe("critical");
    expect(result.findings[0].zone).toBe("unknown");
    expect(result.findings[0].location).toBe("Unknown location");
  });

  it("rejects unknown status, source, and severity contract values", () => {
    expect(() =>
      mapInspectionSummary(inspection({ status: "mystery" }))
    ).toThrow("Unsupported inspection status");
    expect(() =>
      mapInspectionSummary(inspection({ capture_source: "spaceship" }))
    ).toThrow("Unsupported capture source");
    expect(() =>
      mapInspectionSummary(
        inspection({
          findings: [{ ...inspection().findings[0], severity: "unknown" }],
        })
      )
    ).toThrow("Unsupported severity");
  });

  it("accepts the review-required terminal state", () => {
    expect(
      mapInspectionSummary(inspection({ status: "review_required" })).status
    ).toBe("review_required");
  });
});
