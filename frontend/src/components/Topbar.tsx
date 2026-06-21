import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { canCapture, ROLE_LABELS, type UserRole } from "../auth/types";
import { ORG_NAME } from "../data";
import { IconBell, IconChevronDown, IconPlus } from "./icons";

function initials(name: string | null | undefined, email: string): string {
  if (name) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }
  return email.slice(0, 2).toUpperCase();
}

export function Topbar({
  title,
  userRole,
}: {
  title: string;
  userRole: UserRole;
}) {
  const { user, logout } = useAuth();

  return (
    <header className="topbar">
      <div className="topbar__title">{title}</div>
      <div className="topbar__spacer" />

      {canCapture(userRole) ? (
        <Link to="/capture" className="primary-btn">
          <IconPlus />
          New inspection
        </Link>
      ) : null}

      <button className="org-switcher" type="button">
        {ORG_NAME}
        <IconChevronDown />
      </button>

      <button className="icon-btn" type="button" aria-label="Notifications">
        <IconBell size={19} />
        <span className="icon-btn__dot" aria-hidden />
      </button>

      <div className="topbar__account">
        {user ? (
          <>
            <span className="topbar__role">{ROLE_LABELS[userRole]}</span>
            <button
              className="avatar"
              type="button"
              aria-label="Account menu"
              title={user.email}
              onClick={() => void logout()}
            >
              {initials(user.full_name, user.email)}
            </button>
          </>
        ) : null}
      </div>
    </header>
  );
}
