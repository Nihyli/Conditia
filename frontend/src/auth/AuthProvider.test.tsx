import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthProvider";
import * as session from "./session";

vi.mock("./session", async (importOriginal) => {
  const actual = await importOriginal<typeof session>();
  return {
    ...actual,
    fetchSession: vi.fn(),
    setAccessToken: vi.fn(),
    clearAccessToken: vi.fn(),
  };
});

function AuthProbe() {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="status">{auth.status}</span>
      <span data-testid="needs-sign-in">{String(auth.needsSignIn)}</span>
      <span data-testid="display-name">{auth.displayName}</span>
      <span data-testid="initials">{auth.initials}</span>
      <button
        onClick={() => {
          void auth.signInWithToken("token").catch(() => {});
        }}
      >
        Sign in
      </button>
      <button onClick={auth.signOut}>Sign out</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.mocked(session.fetchSession).mockReset();
    vi.mocked(session.setAccessToken).mockReset();
    vi.mocked(session.clearAccessToken).mockReset();
  });

  it("loads the session on mount", async () => {
    vi.mocked(session.fetchSession).mockResolvedValueOnce({
      auth_mode: "disabled",
      user_id: null,
      fleet_id: null,
      role: "admin",
      available_fleets: [],
    });

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    expect(await screen.findByTestId("status")).toHaveTextContent("ready");
    expect(screen.getByTestId("needs-sign-in")).toHaveTextContent("false");
    expect(screen.getByTestId("display-name")).toHaveTextContent("admin");
    expect(screen.getByTestId("initials")).toHaveTextContent("AD");
  });

  it("marks jwt users without a user id as signed out", async () => {
    vi.mocked(session.fetchSession).mockResolvedValueOnce({
      auth_mode: "jwt",
      user_id: null,
      fleet_id: null,
      role: null,
      available_fleets: [],
    });

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    expect(await screen.findByTestId("needs-sign-in")).toHaveTextContent("true");
    expect(screen.getByTestId("initials")).toHaveTextContent("CO");
  });

  it("signs in with a token and clears it when validation fails", async () => {
    vi.mocked(session.fetchSession)
      .mockResolvedValueOnce({
        auth_mode: "jwt",
        user_id: null,
        fleet_id: null,
        role: null,
      })
      .mockRejectedValueOnce(new Error("invalid"));
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );
    await screen.findByTestId("status");

    await expect(
      user.click(screen.getByRole("button", { name: "Sign in" }))
    ).resolves.toBeUndefined();

    await waitFor(() => {
      expect(session.setAccessToken).toHaveBeenCalledWith("token");
      expect(session.clearAccessToken).toHaveBeenCalled();
      expect(screen.getByTestId("status")).toHaveTextContent("signed_out");
    });
  });

  it("signs out and clears the stored token", async () => {
    const sessionPayload = {
      auth_mode: "jwt" as const,
      user_id: "user-1",
      fleet_id: "fleet-1",
      role: "inspector",
      available_fleets: [{ fleet_id: "fleet-1", role: "inspector" }],
    };
    vi.mocked(session.fetchSession)
      .mockResolvedValueOnce(sessionPayload)
      .mockResolvedValueOnce(sessionPayload);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );
    await screen.findByTestId("status");

    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(session.clearAccessToken).toHaveBeenCalled();
    expect(screen.getByTestId("status")).toHaveTextContent("signed_out");
  });

  it("throws when useAuth is used outside the provider", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    const Broken = () => {
      useAuth();
      return null;
    };

    expect(() => render(<Broken />)).toThrow(/must be used inside AuthProvider/i);
    consoleError.mockRestore();
  });
});
