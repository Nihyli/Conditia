import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getFindings, updateFinding } from "../api";
import { FindingsPage } from "./FindingsPage";

vi.mock("../api", () => ({
  getFindings: vi.fn(),
  updateFinding: vi.fn(),
}));

const mockedGetFindings = vi.mocked(getFindings);
const mockedUpdateFinding = vi.mocked(updateFinding);

describe("FindingsPage", () => {
  beforeEach(() => {
    mockedGetFindings.mockReset();
    mockedUpdateFinding.mockReset();
  });

  it("lists findings and resolves one", async () => {
    const user = userEvent.setup();
    mockedGetFindings
      .mockResolvedValueOnce([
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
      ])
      .mockResolvedValueOnce([
        {
          id: "finding-1",
          inspection_id: "inspection-1",
          title: "Front bumper dent",
          finding_type: "dent",
          severity: "medium",
          confidence: 0.87,
          status: "resolved",
          zone: "front",
          location: "Front bumper",
          first_seen_inspection_id: "inspection-1",
          first_detected_inspections_ago: 0,
        },
      ]);
    mockedUpdateFinding.mockResolvedValue({
      id: "finding-1",
      inspection_id: "inspection-1",
      title: "Front bumper dent",
      finding_type: "dent",
      severity: "medium",
      confidence: 0.87,
      status: "resolved",
      zone: "front",
      location: "Front bumper",
      first_seen_inspection_id: "inspection-1",
      first_detected_inspections_ago: 0,
    });

    render(
      <MemoryRouter>
        <FindingsPage />
      </MemoryRouter>
    );

    expect(await screen.findByText("Front bumper dent")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /resolve/i }));
    await waitFor(() =>
      expect(mockedUpdateFinding).toHaveBeenCalledWith("finding-1", {
        status: "resolved",
        resolution_notes: undefined,
      })
    );
  });
});
