import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  authHeaders,
  clearAccessToken,
  fetchSession,
  getAccessToken,
  setAccessToken,
} from "./session";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("session storage helpers", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it("stores, reads, and clears the access token", () => {
    expect(getAccessToken()).toBeNull();
    setAccessToken("  eyJ.token  ");
    expect(getAccessToken()).toBe("eyJ.token");
    clearAccessToken();
    expect(getAccessToken()).toBeNull();
  });

  it("builds auth headers only when a token exists", () => {
    expect(authHeaders()).toEqual({});
    setAccessToken("eyJ.token");
    expect(authHeaders()).toEqual({ Authorization: "Bearer eyJ.token" });
  });
});

describe("fetchSession", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the session payload on success", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        auth_mode: "jwt",
        user_id: "user-1",
        fleet_id: "fleet-1",
        role: "admin",
      })
    );

    await expect(fetchSession()).resolves.toEqual({
      auth_mode: "jwt",
      user_id: "user-1",
      fleet_id: "fleet-1",
      role: "admin",
    });
  });

  it("throws when the auth endpoint is missing", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 404 }));

    await expect(fetchSession()).rejects.toThrow(/auth endpoint missing/i);
  });

  it("uses API error detail when sign-in fails", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ detail: "Invalid token" }, 401)
    );

    await expect(fetchSession()).rejects.toThrow("Invalid token");
  });

  it("falls back to a status message when error bodies are unreadable", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response("not json", { status: 500 }));

    await expect(fetchSession()).rejects.toThrow("Sign-in failed (500)");
  });
});
