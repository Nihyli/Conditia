const TOKEN_KEY = "conditia.access_token";

export function getAccessToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token.trim());
}

export function clearAccessToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export interface AuthSession {
  auth_mode: "disabled" | "api_key" | "jwt";
  user_id: string | null;
  fleet_id: string | null;
  role: string | null;
}

export async function fetchSession(): Promise<AuthSession> {
  const response = await fetch("/api/auth/me", {
    headers: {
      Accept: "application/json",
      ...authHeaders(),
    },
  });
  if (response.status === 404) {
    throw new Error(
      "Auth endpoint missing — restart the backend (uvicorn) so it picks up the latest code."
    );
  }
  if (!response.ok) {
    let detail = `Sign-in failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<AuthSession>;
}
