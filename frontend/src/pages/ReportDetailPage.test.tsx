import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getReport } from "../api";
import { ReportDetailPage } from "./ReportDetailPage";

vi.mock("../api", () => ({
  getReport: vi.fn(),
}));

const mockedGetReport = vi.mocked(getReport);

describe("ReportDetailPage", () => {
  beforeEach(() => {
    mockedGetReport.mockReset();
    vi.spyOn(window, "print").mockImplementation(() => {});
  });

  it("renders report findings and supports print", async () => {
    mockedGetReport.mockResolvedValue({
      id: "report-1",
      inspection_id: "inspection-1",
      generated_at: "2026-06-21T12:00:00Z",
      summary: "Inspection complete. 1 finding detected.",
      total_findings: 1,
      critical_findings: 0,
      pdf_path: null,
      raw_json: {
        inspection_id: "inspection-1",
        total_findings: 1,
        critical_findings: 0,
        findings: [
          {
            id: "finding-1",
            title: "Front bumper dent",
            type: "dent",
            severity: "medium",
            confidence: 0.87,
            status: "open",
            zone: "front",
            location: "Front bumper",
            first_seen_inspection_id: "inspection-1",
          },
        ],
      },
    });

    render(
      <MemoryRouter initialEntries={["/reports/inspection-1"]}>
        <Routes>
          <Route path="/reports/:inspectionId" element={<ReportDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("Inspection complete. 1 finding detected.")).toBeInTheDocument();
    expect(screen.getByText("Front bumper dent")).toBeInTheDocument();
  });
});
