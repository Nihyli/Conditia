const TOKEN_KEY = "conditia.access_token";
const FLEET_ID_KEY = "conditia.fleet_id";

/** In-memory bearer from Supabase session refresh (preferred over sessionStorage). */
let cachedAccessToken: string | null = null;

export function setCachedAccessToken(token: string | null): void {
  cachedAccessToken = token;
}

export function getAccessToken(): string | null {
  return cachedAccessToken ?? sessionStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  const trimmed = token.trim();
  cachedAccessToken = trimmed;
  sessionStorage.setItem(TOKEN_KEY, trimmed);
}

export function clearAccessToken(): void {
  cachedAccessToken = null;
  sessionStorage.removeItem(TOKEN_KEY);
}

export function getFleetId(): string | null {
  return sessionStorage.getItem(FLEET_ID_KEY);
}

export function setFleetId(fleetId: string): void {
  sessionStorage.setItem(FLEET_ID_KEY, fleetId);
}

export function clearFleetId(): void {
  sessionStorage.removeItem(FLEET_ID_KEY);
}

export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const fleetId = getFleetId();
  if (fleetId) {
    headers["X-Fleet-ID"] = fleetId;
  }
  return headers;
}

export interface AuthFleet {
  fleet_id: string;
  role: string;
}

export interface AuthSession {
  auth_mode: "disabled" | "api_key" | "jwt";
  user_id: string | null;
  fleet_id: string | null;
  role: string | null;
  available_fleets: AuthFleet[];
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
  const session = (await response.json()) as AuthSession;
  return {
    ...session,
    available_fleets: session.available_fleets ?? [],
  };
}
