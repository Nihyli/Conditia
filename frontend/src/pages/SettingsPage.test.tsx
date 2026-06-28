import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthProvider";
import * as session from "../auth/session";
import { SettingsPage } from "./SettingsPage";

vi.mock("../auth/session", async (importOriginal) => {
  const actual = await importOriginal<typeof session>();
  return {
    ...actual,
    fetchSession: vi.fn(),
    setAccessToken: vi.fn(),
    clearAccessToken: vi.fn(),
  };
});

function renderSettings(value: session.AuthSession) {
  vi.mocked(session.fetchSession).mockResolvedValue(value);
  render(
    <AuthProvider>
      <SettingsPage />
    </AuthProvider>
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.mocked(session.fetchSession).mockReset();
    vi.mocked(session.clearAccessToken).mockReset();
  });

  it("shows the signed-in account and lets a JWT user sign out", async () => {
    renderSettings({
      auth_mode: "jwt",
      user_id: "user-123",
      fleet_id: "fleet-9",
      role: "inspector",
    });

    expect(await screen.findByText("user-123")).toBeInTheDocument();
    expect(screen.getByText("fleet-9")).toBeInTheDocument();
    expect(screen.getByText("User session (JWT)")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    await waitFor(() => {
      expect(session.clearAccessToken).toHaveBeenCalled();
    });
  });

  it("explains the disabled dev mode and hides sign out", async () => {
    renderSettings({
      auth_mode: "disabled",
      user_id: null,
      fleet_id: null,
      role: "admin",
    });

    expect(
      await screen.findByText("Disabled (local development)")
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /sign out/i })
    ).not.toBeInTheDocument();
  });
});
