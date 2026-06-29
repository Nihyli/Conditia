import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiInspection } from "../test/fixtures";
import { getInspections, getTrucks } from "../api";
import { HistoryPage } from "./HistoryPage";

vi.mock("../api", () => ({
  getTrucks: vi.fn(),
  getInspections: vi.fn(),
}));

const mockedGetTrucks = vi.mocked(getTrucks);
const mockedGetInspections = vi.mocked(getInspections);

describe("HistoryPage", () => {
  beforeEach(() => {
    mockedGetTrucks.mockReset();
    mockedGetInspections.mockReset();
  });

  it("shows new vs previously detected findings", async () => {
    mockedGetTrucks.mockResolvedValue([
      {
        id: "truck-1",
        vin: "1FUJGLDR0CSBT0041",
        make: "Volvo",
        model: "VNL",
        year: 2022,
        license_plate: null,
      },
    ]);
    mockedGetInspections.mockResolvedValue([
      apiInspection({
        findings: [
          {
            id: "new-finding",
            inspection_id: "inspection-1",
            title: "New scratch",
            finding_type: "scratch",
            severity: "low",
            confidence: 0.7,
            status: "open",
            zone: "driver_side",
            location: "Driver door",
            first_seen_inspection_id: "inspection-1",
            first_detected_inspections_ago: 0,
            resolution_notes: null,
          },
          {
            id: "old-finding",
            inspection_id: "inspection-1",
            title: "Old dent",
            finding_type: "dent",
            severity: "medium",
            confidence: 0.8,
            status: "open",
            zone: "front",
            location: "Front bumper",
            first_seen_inspection_id: "inspection-0",
            first_detected_inspections_ago: 2,
            resolution_notes: null,
          },
        ],
        finding_count: 2,
      }),
    ]);

    render(
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>
    );

    expect(await screen.findByText(/New this inspection \(1\)/)).toBeInTheDocument();
    expect(screen.getByText("New scratch")).toBeInTheDocument();
    expect(screen.getByText(/Previously detected \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/Old dent/)).toBeInTheDocument();
  });
});
