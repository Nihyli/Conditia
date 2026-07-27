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
  setCachedAccessToken,
  setFleetId,
  type AuthSession,
} from "./session";
import { getSupabaseClient, isSupabaseConfigured } from "./supabase";

type AuthStatus = "loading" | "ready" | "signed_out";

interface AuthContextValue {
  status: AuthStatus;
  session: AuthSession | null;
  needsSignIn: boolean;
  needsFleetSelection: boolean;
  usesSupabaseAuth: boolean;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signInWithToken: (token: string) => Promise<void>;
  selectFleet: (fleetId: string) => Promise<void>;
  signOut: () => Promise<void>;
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

function applySupabaseAccessToken(accessToken: string | null | undefined): void {
  if (accessToken) {
    setCachedAccessToken(accessToken);
    return;
  }
  setCachedAccessToken(null);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<AuthSession | null>(null);
  const usesSupabaseAuth = isSupabaseConfigured();

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

  const bootstrap = useCallback(async () => {
    const supabase = getSupabaseClient();
    if (supabase) {
      const { data } = await supabase.auth.getSession();
      applySupabaseAccessToken(data.session?.access_token);
      if (!data.session) {
        setSession(null);
        setStatus("signed_out");
        return;
      }
    }
    await loadSession();
  }, [loadSession]);

  useEffect(() => {
    void bootstrap().catch(() => {
      setSession(null);
      setStatus("signed_out");
    });
  }, [bootstrap]);

  useEffect(() => {
    const supabase = getSupabaseClient();
    if (!supabase) {
      return;
    }

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      applySupabaseAccessToken(nextSession?.access_token);
      if (!nextSession) {
        setSession(null);
        setStatus("signed_out");
        clearFleetId();
        return;
      }
      void loadSession().catch(() => {
        setSession(null);
        setStatus("signed_out");
      });
    });

    return () => {
      subscription.unsubscribe();
    };
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

  const signInWithEmail = useCallback(
    async (email: string, password: string) => {
      const supabase = getSupabaseClient();
      if (!supabase) {
        throw new Error("Supabase auth is not configured");
      }
      clearFleetId();
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (error) {
        throw new Error(error.message);
      }
      applySupabaseAccessToken(data.session?.access_token);
      try {
        await loadSession();
      } catch (loadError) {
        await supabase.auth.signOut();
        clearAccessToken();
        clearFleetId();
        setSession(null);
        setStatus("signed_out");
        throw loadError;
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

  const signOut = useCallback(async () => {
    const supabase = getSupabaseClient();
    if (supabase) {
      await supabase.auth.signOut();
    }
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
      usesSupabaseAuth,
      signInWithEmail,
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
      usesSupabaseAuth,
      signInWithEmail,
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
