import { IconBell, IconChevronDown } from "./icons";
import { ORG_NAME, USER_INITIALS } from "../data";

export function Topbar({ title }: { title: string }) {
  return (
    <header className="topbar">
      <div className="topbar__title">{title}</div>
      <div className="topbar__spacer" />

      <button className="org-switcher">
        {ORG_NAME}
        <IconChevronDown />
      </button>

      <button className="icon-btn" aria-label="Notifications">
        <IconBell size={19} />
        <span className="icon-btn__dot" aria-hidden />
      </button>

      <button className="avatar" aria-label="Account">
        {USER_INITIALS}
      </button>
    </header>
  );
}
