import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiInspection } from "../test/fixtures";
import { OverviewPage } from "./OverviewPage";
import { getFleetStats, getInspections } from "../api";

vi.mock("../api", () => ({
  getInspections: vi.fn(),
  getFleetStats: vi.fn(),
  mediaUrl: (id: string) => `/media/${id}`,
}));

vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => ({
    initials: "IN",
    displayName: "inspector",
    session: { auth_mode: "disabled", user_id: null, fleet_id: null, role: "admin" },
    signOut: vi.fn(),
  }),
}));

const mockedInspections = vi.mocked(getInspections);
const mockedStats = vi.mocked(getFleetStats);

function renderOverview() {
  return render(
    <MemoryRouter>
      <OverviewPage />
    </MemoryRouter>
  );
}

describe("OverviewPage", () => {
  beforeEach(() => {
    mockedInspections.mockReset();
    mockedStats.mockReset();
  });

  it("loads stats, inspections, findings, and media", async () => {
    mockedInspections.mockResolvedValue([apiInspection()]);
    mockedStats.mockResolvedValue({
      active_trucks: 1,
      inspections_today: 1,
      inspections_pending: 0,
      inspections_complete_today: 1,
      open_findings: 1,
    });
    renderOverview();

    expect(screen.getByText("Loading fleet data…")).toBeInTheDocument();
    expect(await screen.findByText("TRK-001 — Damage map")).toBeInTheDocument();
    expect(screen.getByText("Front bumper dent")).toBeInTheDocument();
    expect(screen.getByText("Active trucks")).toBeInTheDocument();
  });

  it("derives fallback statistics when the stats endpoint is unavailable", async () => {
    mockedInspections.mockResolvedValue([
      apiInspection({ status: "processing", finding_count: 2 }),
    ]);
    mockedStats.mockRejectedValue(new Error("not supported"));
    renderOverview();

    expect(await screen.findByText("Awaiting analysis")).toBeInTheDocument();
    expect(screen.getByText("Processing in background")).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    mockedInspections.mockResolvedValue([]);
    mockedStats.mockResolvedValue({
      active_trucks: 0,
      inspections_today: 0,
      inspections_pending: 0,
      inspections_complete_today: 0,
      open_findings: 0,
    });
    renderOverview();

    expect(await screen.findByText("No inspections yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /start first inspection/i })).toHaveAttribute(
      "href",
      "/capture"
    );
  });

  it("reports load errors and retries", async () => {
    const user = userEvent.setup();
    mockedInspections
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce([]);
    mockedStats.mockResolvedValue({
      active_trucks: 0,
      inspections_today: 0,
      inspections_pending: 0,
      inspections_complete_today: 0,
      open_findings: 0,
    });
    renderOverview();

    expect(await screen.findByText("Could not load fleet data.")).toBeInTheDocument();
    expect(screen.getByText("offline")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(mockedInspections).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("No inspections yet")).toBeInTheDocument();
  });
});
