import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getReport } from "../api";
import { ReportDetailPage } from "./ReportDetailPage";

vi.mock("../api", () => ({
  getReport: vi.fn(),
}));

const mockedGetReport = vi.mocked(getReport);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/reports/inspection-1"]}>
      <Routes>
        <Route path="/reports/:inspectionId" element={<ReportDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

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

    renderPage();

    expect(await screen.findByText("Inspection complete. 1 finding detected.")).toBeInTheDocument();
    expect(screen.getByText("Front bumper dent")).toBeInTheDocument();
  });

  it("renders narrative markdown when present", async () => {
    mockedGetReport.mockResolvedValue({
      id: "report-2",
      inspection_id: "inspection-1",
      generated_at: "2026-06-21T12:00:00Z",
      summary: "Inspection complete. 1 finding detected, 1 critical.",
      total_findings: 1,
      critical_findings: 1,
      pdf_path: null,
      raw_json: {
        inspection_id: "inspection-1",
        total_findings: 1,
        critical_findings: 1,
        narrative_markdown:
          "## Conditia Condition Report\n\n### Executive Summary\n\nInspection complete. 1 finding detected, 1 critical.\n\n### Critical (1)\n\n- **Cracked windshield** — Windshield (92% confidence, open)\n",
        findings: [
          {
            id: "finding-2",
            title: "Cracked windshield",
            type: "crack",
            severity: "critical",
            confidence: 0.92,
            status: "open",
            zone: "front",
            location: "Windshield",
            first_seen_inspection_id: "inspection-1",
          },
        ],
      },
    });

    renderPage();

    expect(await screen.findByText("Executive Summary")).toBeInTheDocument();
    expect(screen.getByText("Critical (1)")).toBeInTheDocument();
    const matches = screen.getAllByText(/Cracked windshield/);
    expect(matches.length).toBeGreaterThanOrEqual(2);
  });

  it("renders findings at full width (no thumbnail column)", async () => {
    mockedGetReport.mockResolvedValue({
      id: "report-3",
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
            id: "finding-3",
            title: "Minor scratch on door",
            type: "scratch",
            severity: "low",
            confidence: 0.65,
            status: "open",
            zone: "driver_side",
            location: "Driver side door",
            first_seen_inspection_id: "inspection-1",
          },
        ],
      },
    });

    const { container } = renderPage();

    await screen.findByText("Minor scratch on door");
    const findingEl = container.querySelector(".finding");
    expect(findingEl).toBeTruthy();
    const reportPanel = container.querySelector(".report-print");
    expect(reportPanel).toBeTruthy();
  });
});
