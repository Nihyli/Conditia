import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthProvider";
import * as session from "../auth/session";
import * as api from "../api";
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

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return {
    ...actual,
    getFleetMembers: vi.fn(),
    addFleetMember: vi.fn(),
    updateFleetMember: vi.fn(),
    removeFleetMember: vi.fn(),
  };
});

function renderSettings(value: session.AuthSession) {
  const payload = {
    available_fleets: [] as session.AuthFleet[],
    ...value,
  };
  if (payload.auth_mode === "jwt" && payload.user_id) {
    const fleets =
      payload.available_fleets.length > 0
        ? payload.available_fleets
        : payload.fleet_id
          ? [{ fleet_id: payload.fleet_id, role: payload.role ?? "viewer" }]
          : [];
    payload.available_fleets = fleets;
    vi.mocked(session.fetchSession)
      .mockResolvedValueOnce(payload)
      .mockResolvedValueOnce(payload);
  } else {
    vi.mocked(session.fetchSession).mockResolvedValue(payload);
  }
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
    vi.mocked(api.getFleetMembers).mockReset();
    vi.mocked(api.getFleetMembers).mockResolvedValue([]);
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
      available_fleets: [],
    });

    expect(
      await screen.findByText("Disabled (local development)")
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /sign out/i })
    ).not.toBeInTheDocument();
  });

  it("loads fleet members and lets admins add one", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getFleetMembers).mockResolvedValue([
      { fleet_id: "fleet-9", user_id: "user-123", role: "inspector" },
    ]);
    vi.mocked(api.addFleetMember).mockResolvedValue({
      fleet_id: "fleet-9",
      user_id: "user-456",
      role: "viewer",
    });

    renderSettings({
      auth_mode: "jwt",
      user_id: "user-123",
      fleet_id: "fleet-9",
      role: "admin",
    });

    expect(await screen.findByRole("heading", { name: /fleet members/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Role for user-123")).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText(/uuid or auth subject/i),
      "user-456"
    );
    await user.click(screen.getByRole("button", { name: /add member/i }));

    await waitFor(() =>
      expect(api.addFleetMember).toHaveBeenCalledWith({
        user_id: "user-456",
        role: "viewer",
      })
    );
  });
});
