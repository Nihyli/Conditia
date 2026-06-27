import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

vi.mock("./pages/DashboardPage", () => ({
  DashboardPage: () => <div>Dashboard route</div>,
}));
vi.mock("./pages/CapturePage", () => ({
  CapturePage: () => <div>Capture route</div>,
}));

vi.mock("./auth/session", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./auth/session")>();
  return {
    ...actual,
    fetchSession: vi.fn().mockResolvedValue({
      auth_mode: "disabled",
      user_id: null,
      fleet_id: null,
      role: "admin",
    }),
  };
});

describe("App routes", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    ["/", "Dashboard route"],
    ["/capture", "Capture route"],
    ["/capture/truck-1", "Capture route"],
    ["/unknown", "Dashboard route"],
  ])("routes %s", async (path, expected) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });
});
