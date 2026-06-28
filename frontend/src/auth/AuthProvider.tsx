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
  fetchSession,
  setAccessToken,
  type AuthSession,
} from "./session";

type AuthStatus = "loading" | "ready" | "signed_out";

interface AuthContextValue {
  status: AuthStatus;
  session: AuthSession | null;
  needsSignIn: boolean;
  signInWithToken: (token: string) => Promise<void>;
  signOut: () => void;
  displayName: string;
  initials: string;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function initialsFor(session: AuthSession | null): string {
  if (session?.role) {
    return session.role.slice(0, 2).toUpperCase();
  }
  return "CF";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<AuthSession | null>(null);

  const loadSession = useCallback(async (): Promise<AuthSession> => {
    const next = await fetchSession();
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
      try {
        await loadSession();
      } catch {
        clearAccessToken();
        setSession(null);
        setStatus("signed_out");
        throw new Error("sign-in failed");
      }
    },
    [loadSession]
  );

  const signOut = useCallback(() => {
    clearAccessToken();
    setSession(null);
    setStatus("signed_out");
  }, []);

  const needsSignIn =
    status === "signed_out" ||
    (session?.auth_mode === "jwt" && session.user_id === null);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      session,
      needsSignIn,
      signInWithToken,
      signOut,
      displayName: session?.role ?? "Fleet user",
      initials: initialsFor(session),
    }),
    [status, session, needsSignIn, signInWithToken, signOut]
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
