import { FormEvent, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ROLE_LABELS, type UserRole } from "../auth/types";

const DEMO_ACCOUNTS: { email: string; role: UserRole; password: string }[] = [
  { email: "admin@conditia.ai", role: "admin", password: "demo1234" },
  { email: "manager@conditia.ai", role: "fleet_manager", password: "demo1234" },
  { email: "inspector@conditia.ai", role: "inspector", password: "demo1234" },
  { email: "viewer@conditia.ai", role: "viewer", password: "demo1234" },
];

export function LoginPage() {
  const { user, loading, login, config } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setSubmitting(false);
    }
  }

  function fillDemo(account: (typeof DEMO_ACCOUNTS)[number]) {
    setEmail(account.email);
    setPassword(account.password);
    setError(null);
  }

  const isLocal = config?.provider !== "supabase";

  return (
    <div className="login">
      <div className="login__card">
        <div className="login__brand">
          <span className="brand__mark" aria-hidden>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 3.5c-3.9 0-6.8 2.8-6.8 6.8 0 3.4 2.7 6.2 6.8 9.2 4.1-3 6.8-5.8 6.8-9.2 0-4-2.9-6.8-6.8-6.8Z"
                stroke="currentColor"
                strokeWidth="1.8"
              />
              <circle cx="12" cy="10" r="2.6" fill="currentColor" />
            </svg>
          </span>
          <div>
            <h1 className="login__title">Conditia</h1>
            <p className="login__subtitle">Asset condition intelligence</p>
          </div>
        </div>

        <form className="login__form" onSubmit={(e) => void handleSubmit(e)}>
          <label className="field">
            <span className="field__label">Email</span>
            <input
              className="field__input"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          <label className="field">
            <span className="field__label">Password</span>
            <input
              className="field__input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>

          {error ? <p className="error-note">{error}</p> : null}

          <button
            type="submit"
            className="primary-btn login__submit"
            disabled={submitting || loading}
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {isLocal ? (
          <div className="login__demo">
            <p className="login__demo-title">Demo accounts (local dev)</p>
            <ul className="login__demo-list">
              {DEMO_ACCOUNTS.map((account) => (
                <li key={account.email}>
                  <button
                    type="button"
                    className="login__demo-btn"
                    onClick={() => fillDemo(account)}
                  >
                    <span className="login__demo-role">
                      {ROLE_LABELS[account.role]}
                    </span>
                    <span className="mono">{account.email}</span>
                  </button>
                </li>
              ))}
            </ul>
            <p className="muted login__demo-hint">Password for all: demo1234</p>
          </div>
        ) : (
          <p className="muted login__demo-hint">
            Sign in with your Supabase account. Demo accounts only work in local
            auth mode — set <code>AUTH_PROVIDER=local</code> in backend{" "}
            <code>.env</code> for development.
          </p>
        )}
      </div>
    </div>
  );
}
