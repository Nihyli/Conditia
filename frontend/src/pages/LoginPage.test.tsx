import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";

const signInWithToken = vi.fn();

vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => ({ signInWithToken }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    signInWithToken.mockReset();
    signInWithToken.mockResolvedValue(undefined);
  });

  it("renders the sign-in form", () => {
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

  it("normalizes export and Bearer prefixes on submit", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByLabelText(/access token/i),
      'export CONDITIA_TOKEN="eyJ.exported"'
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(signInWithToken).toHaveBeenCalledWith("eyJ.exported")
    );
  });

  it("normalizes pasted tokens", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const field = screen.getByLabelText(/access token/i);
    await user.click(field);
    await user.paste("Bearer eyJ.pasted");

    expect(field).toHaveValue("eyJ.pasted");
  });

  it("shows an error when sign-in fails", async () => {
    signInWithToken.mockRejectedValueOnce(new Error("bad token"));
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/access token/i), "bad");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/sign in failed/i);
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  it("clears errors when the token changes", async () => {
    signInWithToken.mockRejectedValueOnce(new Error("bad token"));
    const user = userEvent.setup();
    render(<LoginPage />);

    const field = screen.getByLabelText(/access token/i);
    await user.type(field, "bad");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();

    await user.type(field, "x");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("toggles token visibility", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const field = screen.getByLabelText(/access token/i);
    expect(field).toHaveClass("is-masked");

    await user.click(screen.getByRole("button", { name: "Show token" }));
    expect(field).not.toHaveClass("is-masked");

    await user.click(screen.getByRole("button", { name: "Hide token" }));
    expect(field).toHaveClass("is-masked");
  });

  it("shows a busy label while signing in", async () => {
    let resolveSignIn: () => void = () => {};
    signInWithToken.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveSignIn = resolve;
        })
    );
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/access token/i), "token");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByRole("button", { name: "Signing in…" })).toBeDisabled();
    resolveSignIn();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled()
    );
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
