import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

vi.mock("./pages/DashboardPage", () => ({
  DashboardPage: () => <div>Dashboard route</div>,
}));
vi.mock("./pages/CapturePage", () => ({
  CapturePage: () => <div>Capture route</div>,
}));

describe("App routes", () => {
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
