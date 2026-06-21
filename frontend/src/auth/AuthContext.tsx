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
  getAuthConfig,
  getMe,
  loginLocal,
  setAuthToken,
  setAuthTokenGetter,
  syncSupabaseUser,
} from "../api";
import { getSupabaseClient } from "../lib/supabase";
import type { AuthConfig, AuthUser, UserRole } from "./types";

const TOKEN_KEY = "conditia_token";

const DEFAULT_CONFIG: AuthConfig = {
  auth_enabled: true,
  provider: "local",
  supabase_url: null,
  supabase_anon_key: null,
};

interface AuthContextValue {
  user: AuthUser | null;
  config: AuthConfig | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  getAccessToken: () => string | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function toAuthUser(raw: {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  fleet_id?: string | null;
  auth_provider: string;
}): AuthUser {
  return {
    id: raw.id,
    email: raw.email,
    full_name: raw.full_name,
    role: raw.role as UserRole,
    fleet_id: raw.fleet_id ?? null,
    auth_provider: raw.auth_provider,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const saved = localStorage.getItem(TOKEN_KEY);
  if (saved) setAuthToken(saved);

  const [user, setUser] = useState<AuthUser | null>(null);
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [token, setToken] = useState<string | null>(saved);
  const [loading, setLoading] = useState(true);

  const getAccessToken = useCallback(() => token, [token]);

  useEffect(() => {
    setAuthTokenGetter(getAccessToken);
  }, [getAccessToken]);

  const persistToken = useCallback((value: string | null) => {
    setAuthToken(value);
    setToken(value);
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  }, []);

  const loadProfile = useCallback(
    async (accessToken: string, provider: AuthConfig["provider"]) => {
      persistToken(accessToken);
      if (provider === "supabase") {
        setUser(toAuthUser(await syncSupabaseUser()));
      } else {
        setUser(toAuthUser(await getMe()));
      }
    },
    [persistToken]
  );

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      let cfg = DEFAULT_CONFIG;
      try {
        cfg = await getAuthConfig();
      } catch {
        /* backend unreachable — fall back to local auth */
      }
      if (cancelled) return;
      setConfig(cfg);

      try {
        if (!cfg.auth_enabled) {
          setUser(toAuthUser(await getMe()));
          return;
        }

        if (
          cfg.provider === "supabase" &&
          cfg.supabase_url &&
          cfg.supabase_anon_key
        ) {
          const supabase = getSupabaseClient(
            cfg.supabase_url,
            cfg.supabase_anon_key
          );
          const { data } = await supabase.auth.getSession();
          if (data.session?.access_token) {
            await loadProfile(data.session.access_token, "supabase");
            return;
          }
          persistToken(null);
          setUser(null);
          return;
        }

        const stored = localStorage.getItem(TOKEN_KEY);
        if (stored) {
          await loadProfile(stored, "local");
        }
      } catch {
        persistToken(null);
        setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [loadProfile, persistToken]);

  const login = useCallback(
    async (email: string, password: string) => {
      let cfg = config;
      if (!cfg) {
        try {
          cfg = await getAuthConfig();
          setConfig(cfg);
        } catch {
          cfg = DEFAULT_CONFIG;
        }
      }

      if (
        cfg.provider === "supabase" &&
        cfg.supabase_url &&
        cfg.supabase_anon_key
      ) {
        const supabase = getSupabaseClient(cfg.supabase_url, cfg.supabase_anon_key);
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw new Error(error.message);
        if (!data.session?.access_token) throw new Error("No session returned");
        await loadProfile(data.session.access_token, "supabase");
        return;
      }

      const result = await loginLocal(email, password);
      persistToken(result.access_token);
      setUser(toAuthUser(result.user));
    },
    [config, loadProfile, persistToken]
  );

  const logout = useCallback(async () => {
    const cfg = config ?? DEFAULT_CONFIG;
    if (
      cfg.provider === "supabase" &&
      cfg.supabase_url &&
      cfg.supabase_anon_key
    ) {
      const supabase = getSupabaseClient(cfg.supabase_url, cfg.supabase_anon_key);
      await supabase.auth.signOut();
    }
    persistToken(null);
    setUser(null);
  }, [config, persistToken]);

  const value = useMemo(
    () => ({ user, config, loading, login, logout, getAccessToken }),
    [user, config, loading, login, logout, getAccessToken]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
