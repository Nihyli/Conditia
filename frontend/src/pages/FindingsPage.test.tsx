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

const { authState } = vi.hoisted(() => ({
  authState: { role: "admin" as string | null },
}));

vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => ({
    session: { auth_mode: "jwt", user_id: "u", fleet_id: "f", role: authState.role },
  }),
}));

const mockedGetFindings = vi.mocked(getFindings);
const mockedUpdateFinding = vi.mocked(updateFinding);

const OPEN_FINDING = {
  id: "finding-1",
  inspection_id: "inspection-1",
  title: "Front bumper dent",
  finding_type: "dent",
  severity: "medium",
  confidence: 0.87,
  status: "open" as const,
  zone: "front",
  location: "Front bumper",
  first_seen_inspection_id: "inspection-1",
  first_detected_inspections_ago: 0,
  resolution_notes: null,
};

describe("FindingsPage", () => {
  beforeEach(() => {
    mockedGetFindings.mockReset();
    mockedUpdateFinding.mockReset();
    authState.role = "admin";
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
          resolution_notes: null,
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
          resolution_notes: "Panel replaced",
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
      resolution_notes: "Panel replaced",
    });

    render(
      <MemoryRouter>
        <FindingsPage />
      </MemoryRouter>
    );

    expect(await screen.findByText("Front bumper dent")).toBeInTheDocument();
    await user.type(
      screen.getByPlaceholderText(/resolution notes/i),
      "Panel replaced"
    );
    await user.click(screen.getByRole("button", { name: /resolve/i }));
    await waitFor(() =>
      expect(mockedUpdateFinding).toHaveBeenCalledWith("finding-1", {
        status: "resolved",
        resolution_notes: "Panel replaced",
      })
    );
    expect(await screen.findByText(/Resolution: Panel replaced/)).toBeInTheDocument();
  });

  it("shows stored resolution notes on closed findings", async () => {
    mockedGetFindings.mockResolvedValue([
      {
        id: "finding-2",
        inspection_id: "inspection-1",
        title: "Old scratch",
        finding_type: "scratch",
        severity: "low",
        confidence: 0.75,
        status: "resolved",
        zone: "driver_side",
        location: "Door",
        first_seen_inspection_id: "inspection-0",
        first_detected_inspections_ago: 2,
        resolution_notes: "Cosmetic only — documented",
      },
    ]);

    render(
      <MemoryRouter>
        <FindingsPage />
      </MemoryRouter>
    );

    expect(
      await screen.findByText(/Resolution: Cosmetic only — documented/)
    ).toBeInTheDocument();
  });

  it("hides mutation controls from viewers", async () => {
    authState.role = "viewer";
    mockedGetFindings.mockResolvedValue([OPEN_FINDING]);

    render(
      <MemoryRouter>
        <FindingsPage />
      </MemoryRouter>
    );

    expect(await screen.findByText("Front bumper dent")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /resolve/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /false positive/i })).toBeNull();
  });
});
