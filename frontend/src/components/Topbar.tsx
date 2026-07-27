import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { IconBell, IconChevronDown, IconLogOut, IconPlus } from "./icons";
import { ORG_NAME } from "../data";

export function Topbar({ title }: { title: string }) {
  const { initials, displayName, session, signOut, selectFleet } = useAuth();
  const fleets = session?.available_fleets ?? [];
  const canSwitchFleet = fleets.length > 1;
  const canSignOut = session?.auth_mode === "jwt";

  return (
    <header className="topbar">
      <div className="topbar__title">{title}</div>
      <div className="topbar__spacer" />

      <Link to="/capture" className="primary-btn">
        <IconPlus />
        New inspection
      </Link>

      {canSwitchFleet ? (
        <label className="org-switcher">
          <span className="sr-only">Fleet</span>
          <select
            className="org-switcher__select"
            value={session?.fleet_id ?? ""}
            onChange={(event) => {
              void selectFleet(event.target.value);
            }}
          >
            <option value="" disabled>
              Select fleet
            </option>
            {fleets.map((fleet) => (
              <option key={fleet.fleet_id} value={fleet.fleet_id}>
                Fleet {fleet.fleet_id.slice(0, 8)}… ({fleet.role})
              </option>
            ))}
          </select>
          <IconChevronDown />
        </label>
      ) : (
        <button
          className="org-switcher"
          disabled
          title="Organization switching is not available yet"
        >
          {ORG_NAME}
          <IconChevronDown />
        </button>
      )}

      <button className="icon-btn" aria-label="Notifications" disabled>
        <IconBell size={19} />
        <span className="icon-btn__dot" aria-hidden />
      </button>

      {canSignOut ? (
        <button
          type="button"
          className="ghost-btn topbar__logout"
          onClick={() => {
            void signOut();
          }}
        >
          <IconLogOut />
          Log out
        </button>
      ) : null}

      <span
        className="avatar"
        aria-label={canSignOut ? `Signed in as ${displayName}` : "Account"}
        title={canSignOut ? displayName : undefined}
      >
        {initials}
      </span>
    </header>
  );
}
