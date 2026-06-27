import { navIconMap, type NavIconName } from "./icons";

interface NavItem {
  id: string;
  label: string;
  icon: NavIconName;
  badge?: number;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const baseGroups: NavGroup[] = [
  {
    label: "Monitor",
    items: [
      { id: "overview", label: "Fleet overview", icon: "overview" },
      { id: "trucks", label: "Trucks", icon: "truck" },
      { id: "inspections", label: "Inspections", icon: "clipboard" },
      { id: "findings", label: "Findings", icon: "alert" },
    ],
  },
  {
    label: "Reports",
    items: [
      { id: "reports", label: "Reports", icon: "report" },
      { id: "history", label: "History", icon: "history" },
    ],
  },
  {
    label: "Integrations",
    items: [{ id: "samsara", label: "Samsara", icon: "plug" }],
  },
];

function buildGroups(trucksBadge?: number): NavGroup[] {
  return baseGroups.map((group) => ({
    ...group,
    items: group.items.map((item) =>
      item.id === "trucks" && trucksBadge != null && trucksBadge > 0
        ? { ...item, badge: trucksBadge }
        : item
    ),
  }));
}

export function Sidebar({
  active,
  onSelect,
  trucksBadge,
  locked = false,
}: {
  active: string;
  onSelect: (id: string) => void;
  trucksBadge?: number;
  locked?: boolean;
}) {
  const groups = buildGroups(trucksBadge);
  return (
    <aside className={`sidebar${locked ? " is-locked" : ""}`}>
      <div className="brand">
        <span className="brand__mark" aria-hidden>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 3.5c-3.9 0-6.8 2.8-6.8 6.8 0 3.4 2.7 6.2 6.8 9.2 4.1-3 6.8-5.8 6.8-9.2 0-4-2.9-6.8-6.8-6.8Z"
              stroke="currentColor"
              strokeWidth="1.8"
            />
            <circle cx="12" cy="10" r="2.6" fill="currentColor" />
          </svg>
        </span>
        <span className="brand__name">Conditia</span>
      </div>

      <nav className="nav">
        {groups.map((group) => (
          <div className="nav__group" key={group.label}>
            <div className="nav__label">{group.label}</div>
            {group.items.map((item) => {
              const Icon = navIconMap[item.icon];
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`nav__item${active === item.id ? " is-active" : ""}`}
                  onClick={() => onSelect(item.id)}
                  aria-current={active === item.id ? "page" : undefined}
                  disabled={locked}
                  tabIndex={locked ? -1 : undefined}
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                  {item.badge != null && item.badge > 0 ? (
                    <span className="nav__badge">{item.badge}</span>
                  ) : null}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="sidebar__foot">
        <button
          type="button"
          className={`nav__item${active === "settings" ? " is-active" : ""}`}
          onClick={() => onSelect("settings")}
          disabled={locked}
          tabIndex={locked ? -1 : undefined}
        >
          {(() => {
            const Icon = navIconMap.settings;
            return <Icon size={18} />;
          })()}
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}
