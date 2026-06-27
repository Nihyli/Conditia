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
