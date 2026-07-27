import { FormEvent, useId, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { isSupabaseConfigured } from "../auth/supabase";

function normalizeToken(raw: string): string {
  const trimmed = raw.trim();
  const exportMatch = trimmed.match(
    /^export\s+CONDITIA_TOKEN=["']?(.+?)["']?\s*$/
  );
  if (exportMatch) return exportMatch[1].trim();
  return trimmed.replace(/^Bearer\s+/i, "");
}

function ConditiaLogo({ light = false }: { light?: boolean }) {
  return (
    <div className={`signin-logo${light ? " signin-logo--light" : ""}`}>
      <span className="signin-logo__mark" aria-hidden>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 3.5c-3.9 0-6.8 2.8-6.8 6.8 0 3.4 2.7 6.2 6.8 9.2 4.1-3 6.8-5.8 6.8-9.2 0-4-2.9-6.8-6.8-6.8Z"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <circle cx="12" cy="10" r="2.6" fill="currentColor" />
        </svg>
      </span>
      <span className="signin-logo__name">Conditia</span>
    </div>
  );
}

function DevTokenSignIn({
  signInWithToken,
}: {
  signInWithToken: (token: string) => Promise<void>;
}) {
  const fieldId = useId();
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signInWithToken(normalizeToken(token));
    } catch {
      setError(
        "Token sign-in failed. Mint a fresh token with scripts/mint_dev_token.py."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="signin-advanced">
      <button
        type="button"
        className="signin-advanced__toggle"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        {open ? "Hide developer token sign-in" : "Developer token sign-in"}
      </button>
      {open ? (
        <form className="signin-form signin-form--advanced" onSubmit={onSubmit}>
          <div className="signin-field">
            <label className="signin-field__label" htmlFor={fieldId}>
              Access token
            </label>
            <textarea
              id={fieldId}
              className={`signin-field__input mono${error ? " is-error" : ""}${visible ? "" : " is-masked"}`}
              rows={3}
              value={token}
              onChange={(event) => {
                setToken(event.target.value);
                if (error) setError(null);
              }}
              onPaste={(event) => {
                event.preventDefault();
                setToken(normalizeToken(event.clipboardData.getData("text")));
                if (error) setError(null);
              }}
              placeholder="Paste token from mint_dev_token.py"
              autoComplete="off"
              spellCheck={false}
            />
          </div>
          <button
            type="button"
            className="signin-field__toggle"
            onClick={() => setVisible((value) => !value)}
          >
            {visible ? "Hide token" : "Show token"}
          </button>
          {error ? (
            <p className="signin-error" role="alert">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            className="signin-submit signin-submit--secondary"
            disabled={busy || !token.trim()}
          >
            {busy ? "Signing in…" : "Sign in with token"}
          </button>
        </form>
      ) : null}
    </div>
  );
}

export function LoginPage() {
  const { signInWithEmail, signInWithToken, usesSupabaseAuth } = useAuth();
  const emailId = useId();
  const passwordId = useId();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const supabaseMode = usesSupabaseAuth || isSupabaseConfigured();
  const showDevToken = import.meta.env.DEV || !supabaseMode;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (supabaseMode) {
        await signInWithEmail(email, password);
      } else {
        await signInWithToken(normalizeToken(password));
      }
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Sign in failed";
      setError(
        supabaseMode
          ? message
          : "Sign in failed. Confirm AUTH_MODE=jwt in backend/.env and mint a fresh token."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="signin">
      <aside className="signin-promo">
        <ConditiaLogo light />
        <h1 className="signin-promo__title">
          All-in-one platform for fleet condition management
        </h1>
        <p className="signin-promo__text">
          Capture inspections, track damage over time, and review findings
          across your fleet from one console.
        </p>
        <p className="signin-promo__legal">
          © {new Date().getFullYear()} Conditia Inc. All rights reserved.
        </p>
      </aside>

      <main className="signin-main">
        <div className="signin-main__inner">
          <div className="signin-main__logo-mobile">
            <ConditiaLogo />
          </div>

          <h2 className="signin-main__title">Fleet Sign In</h2>

          {supabaseMode ? (
            <form className="signin-form" onSubmit={onSubmit} noValidate>
              <div className="signin-field">
                <label className="signin-field__label" htmlFor={emailId}>
                  Email
                </label>
                <input
                  id={emailId}
                  className={`signin-field__input${error ? " is-error" : ""}`}
                  type="email"
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value);
                    if (error) setError(null);
                  }}
                  placeholder="you@fleet.example"
                  autoComplete="email"
                  required
                />
              </div>

              <div className="signin-field">
                <label className="signin-field__label" htmlFor={passwordId}>
                  Password
                </label>
                <input
                  id={passwordId}
                  className={`signin-field__input${error ? " is-error" : ""}`}
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    if (error) setError(null);
                  }}
                  placeholder="Your password"
                  autoComplete="current-password"
                  required
                />
              </div>

              <button
                type="button"
                className="signin-field__toggle"
                onClick={() => setShowPassword((value) => !value)}
              >
                {showPassword ? "Hide password" : "Show password"}
              </button>

              {error ? (
                <p className="signin-error" role="alert">
                  {error}
                </p>
              ) : null}

              <button
                type="submit"
                className="signin-submit"
                disabled={busy || !email.trim() || !password}
              >
                {busy ? "Signing in…" : "Sign in"}
              </button>
            </form>
          ) : (
            <form className="signin-form" onSubmit={onSubmit} noValidate>
              <div className="signin-field">
                <label className="signin-field__label" htmlFor={passwordId}>
                  Access token
                </label>
                <textarea
                  id={passwordId}
                  className={`signin-field__input mono${error ? " is-error" : ""}${showPassword ? "" : " is-masked"}`}
                  rows={3}
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    if (error) setError(null);
                  }}
                  onPaste={(event) => {
                    event.preventDefault();
                    setPassword(
                      normalizeToken(event.clipboardData.getData("text"))
                    );
                    if (error) setError(null);
                  }}
                  placeholder="Paste token from your administrator"
                  autoComplete="off"
                  spellCheck={false}
                />
              </div>

              <button
                type="button"
                className="signin-field__toggle"
                onClick={() => setShowPassword((value) => !value)}
              >
                {showPassword ? "Hide token" : "Show token"}
              </button>

              {error ? (
                <p className="signin-error" role="alert">
                  {error}
                </p>
              ) : null}

              <button
                type="submit"
                className="signin-submit"
                disabled={busy || !password.trim()}
              >
                {busy ? "Signing in…" : "Sign in"}
              </button>
            </form>
          )}

          <div className="signin-links">
            {supabaseMode ? (
              <p className="signin-links__hint">
                Trouble signing in? Contact your fleet administrator.
              </p>
            ) : import.meta.env.DEV ? (
              <p className="signin-links__hint">
                Local dev: run{" "}
                <code>python scripts/mint_dev_token.py</code> in{" "}
                <code>backend/</code>. See README.
              </p>
            ) : (
              <p className="signin-links__hint">
                Trouble signing in? Contact your fleet administrator.
              </p>
            )}
          </div>

          {showDevToken && supabaseMode ? (
            <DevTokenSignIn signInWithToken={signInWithToken} />
          ) : null}
        </div>
      </main>
    </div>
  );
}
