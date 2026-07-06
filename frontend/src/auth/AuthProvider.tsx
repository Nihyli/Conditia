import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  authHeaders,
  clearAccessToken,
  clearFleetId,
  fetchSession,
  getFleetId,
  setAccessToken,
  setFleetId,
  type AuthSession,
} from "./session";

type AuthStatus = "loading" | "ready" | "signed_out";

interface AuthContextValue {
  status: AuthStatus;
  session: AuthSession | null;
  needsSignIn: boolean;
  needsFleetSelection: boolean;
  signInWithToken: (token: string) => Promise<void>;
  selectFleet: (fleetId: string) => Promise<void>;
  signOut: () => void;
  displayName: string;
  initials: string;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function initialsFor(session: AuthSession | null): string {
  if (session?.role) {
    return session.role.slice(0, 2).toUpperCase();
  }
  return "CO";
}

function syncFleetSelection(session: AuthSession): void {
  const fleets = session.available_fleets;
  if (fleets.length === 1) {
    setFleetId(fleets[0].fleet_id);
    return;
  }
  const current = getFleetId();
  if (current && fleets.some((fleet) => fleet.fleet_id === current)) {
    return;
  }
  if (fleets.length > 1) {
    clearFleetId();
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<AuthSession | null>(null);

  const loadSession = useCallback(async (): Promise<AuthSession> => {
    let next = await fetchSession();
    if (next.auth_mode === "jwt" && next.user_id) {
      const before = getFleetId();
      syncFleetSelection(next);
      if (getFleetId() !== before) {
        next = await fetchSession();
      }
    }
    setSession(next);
    setStatus("ready");
    return next;
  }, []);

  useEffect(() => {
    void loadSession().catch(() => {
      setSession(null);
      setStatus("signed_out");
    });
  }, [loadSession]);

  const signInWithToken = useCallback(
    async (token: string) => {
      setAccessToken(token);
      clearFleetId();
      try {
        await loadSession();
      } catch {
        clearAccessToken();
        clearFleetId();
        setSession(null);
        setStatus("signed_out");
        throw new Error("sign-in failed");
      }
    },
    [loadSession]
  );

  const selectFleet = useCallback(
    async (fleetId: string) => {
      setFleetId(fleetId);
      await loadSession();
    },
    [loadSession]
  );

  const signOut = useCallback(() => {
    clearAccessToken();
    clearFleetId();
    setSession(null);
    setStatus("signed_out");
  }, []);

  const needsSignIn =
    status === "signed_out" ||
    (session?.auth_mode === "jwt" && session.user_id === null);

  const needsFleetSelection =
    !needsSignIn &&
    session?.auth_mode === "jwt" &&
    (session.available_fleets.length ?? 0) > 1 &&
    session.fleet_id === null;

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      session,
      needsSignIn,
      needsFleetSelection,
      signInWithToken,
      selectFleet,
      signOut,
      displayName: session?.role ?? "Fleet user",
      initials: initialsFor(session),
    }),
    [
      status,
      session,
      needsSignIn,
      needsFleetSelection,
      signInWithToken,
      selectFleet,
      signOut,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}

export { authHeaders };
