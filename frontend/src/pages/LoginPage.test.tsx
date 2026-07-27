import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";

const signInWithEmail = vi.fn();
const signInWithToken = vi.fn();
const mockUsesSupabase = vi.hoisted(() => ({ value: false }));

vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => ({
    signInWithEmail,
    signInWithToken,
    usesSupabaseAuth: mockUsesSupabase.value,
  }),
}));

vi.mock("../auth/supabase", () => ({
  isSupabaseConfigured: () => mockUsesSupabase.value,
}));

describe("LoginPage", () => {
  beforeEach(() => {
    mockUsesSupabase.value = false;
    signInWithEmail.mockReset();
    signInWithToken.mockReset();
    signInWithEmail.mockResolvedValue(undefined);
    signInWithToken.mockResolvedValue(undefined);
  });

  it("renders the token sign-in form when Supabase is not configured", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: /fleet sign in/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/access token/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled();
  });

  it("signs in with a trimmed token", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/access token/i), "  eyJ.test.token  ");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(signInWithToken).toHaveBeenCalledWith("eyJ.test.token")
    );
  });

  it("shows an error when sign-in fails", async () => {
    signInWithToken.mockRejectedValueOnce(new Error("bad token"));
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/access token/i), "bad");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/sign in failed/i);
  });

  it("shows the production help text outside dev", () => {
    vi.stubEnv("DEV", false);
    render(<LoginPage />);

    expect(
      screen.getByText(/trouble signing in\? contact your fleet administrator/i)
    ).toBeInTheDocument();
    vi.unstubAllEnvs();
  });
});

describe("LoginPage with Supabase", () => {
  beforeEach(() => {
    mockUsesSupabase.value = true;
    signInWithEmail.mockReset();
    signInWithToken.mockReset();
    signInWithEmail.mockResolvedValue(undefined);
    signInWithToken.mockResolvedValue(undefined);
  });

  it("renders email and password fields", () => {
    render(<LoginPage />);

    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
  });

  it("signs in with email and password", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/^email$/i), "driver@fleet.example");
    await user.type(screen.getByLabelText(/^password$/i), "secret-pass");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(signInWithEmail).toHaveBeenCalledWith(
        "driver@fleet.example",
        "secret-pass"
      )
    );
  });
});
