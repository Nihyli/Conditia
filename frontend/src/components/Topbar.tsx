import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { IconBell, IconChevronDown, IconPlus } from "./icons";
import { ORG_NAME } from "../data";

export function Topbar({ title }: { title: string }) {
  const { initials, displayName, session, signOut } = useAuth();

  return (
    <header className="topbar">
      <div className="topbar__title">{title}</div>
      <div className="topbar__spacer" />

      <Link to="/capture" className="primary-btn">
        <IconPlus />
        New inspection
      </Link>

      <button className="org-switcher" disabled title="Organization switching is not available yet">
        {ORG_NAME}
        <IconChevronDown />
      </button>

      <button className="icon-btn" aria-label="Notifications" disabled>
        <IconBell size={19} />
        <span className="icon-btn__dot" aria-hidden />
      </button>

      <button
        className="avatar"
        aria-label={session?.auth_mode === "jwt" ? `Signed in as ${displayName}` : "Account"}
        title={session?.auth_mode === "jwt" ? `${displayName} — click to sign out` : undefined}
        onClick={session?.auth_mode === "jwt" ? signOut : undefined}
        type="button"
      >
        {initials}
      </button>
    </header>
  );
}
