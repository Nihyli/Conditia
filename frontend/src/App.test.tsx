import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

vi.mock("./api", () => ({
  getFleetStats: vi.fn().mockResolvedValue({ active_trucks: 2 }),
  mediaUrl: (id: string) => `/media/${id}`,
}));

vi.mock("./pages/OverviewPage", () => ({
  OverviewPage: () => <div>Overview route</div>,
}));
vi.mock("./pages/TrucksPage", () => ({
  TrucksPage: () => <div>Trucks route</div>,
}));
vi.mock("./pages/TruckDetailPage", () => ({
  TruckDetailPage: () => <div>Truck detail route</div>,
}));
vi.mock("./pages/InspectionsPage", () => ({
  InspectionsPage: () => <div>Inspections route</div>,
}));
vi.mock("./pages/InspectionDetailPage", () => ({
  InspectionDetailPage: () => <div>Inspection detail route</div>,
}));
vi.mock("./pages/FindingsPage", () => ({
  FindingsPage: () => <div>Findings route</div>,
}));
vi.mock("./pages/ReportsPage", () => ({
  ReportsPage: () => <div>Reports route</div>,
}));
vi.mock("./pages/ReportDetailPage", () => ({
  ReportDetailPage: () => <div>Report detail route</div>,
}));
vi.mock("./pages/HistoryPage", () => ({
  HistoryPage: () => <div>History route</div>,
}));
vi.mock("./pages/SettingsPage", () => ({
  SettingsPage: () => <div>Settings route</div>,
}));
vi.mock("./pages/SamsaraPage", () => ({
  SamsaraPage: () => <div>Samsara route</div>,
}));
vi.mock("./pages/CapturePage", () => ({
  CapturePage: () => <div>Capture route</div>,
}));

const fetchSession = vi.hoisted(() => vi.fn());

vi.mock("./auth/session", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./auth/session")>();
  return {
    ...actual,
    fetchSession,
  };
});

describe("App routes", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchSession.mockResolvedValue({
      auth_mode: "disabled",
      user_id: null,
      fleet_id: null,
      role: "admin",
    });
  });

  it.each([
    ["/", "Overview route"],
    ["/trucks", "Trucks route"],
    ["/trucks/truck-1", "Truck detail route"],
    ["/inspections", "Inspections route"],
    ["/inspections/insp-1", "Inspection detail route"],
    ["/findings", "Findings route"],
    ["/reports", "Reports route"],
    ["/reports/insp-1", "Report detail route"],
    ["/history", "History route"],
    ["/settings", "Settings route"],
    ["/integrations/samsara", "Samsara route"],
    ["/capture", "Capture route"],
    ["/capture/truck-1", "Capture route"],
    ["/unknown", "Overview route"],
  ])("routes %s", async (path, expected) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });

  it("shows the login page when jwt auth requires sign-in", async () => {
    fetchSession.mockResolvedValue({
      auth_mode: "jwt",
      user_id: null,
      fleet_id: null,
      role: null,
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: /fleet sign in/i })).toBeInTheDocument();
  });
});
