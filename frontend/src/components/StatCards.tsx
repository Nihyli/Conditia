import type { FleetStat } from "../types";
import { fleetStats } from "../data";
import {
  IconArrowUp,
  IconArrowDown,
  IconTruck,
  IconClipboard,
  IconAlert,
  IconClock,
} from "./icons";

const headIcon = {
  truck: IconTruck,
  clipboard: IconClipboard,
  alert: IconAlert,
  clock: IconClock,
} as const;

function TrendMark({ kind }: { kind: FleetStat["trendKind"] }) {
  if (kind === "up") return <IconArrowUp />;
  if (kind === "down") return <IconArrowDown />;
  return null;
}

export function StatCards() {
  return (
    <section className="stats">
      {fleetStats.map((stat) => {
        const Icon = headIcon[stat.icon as keyof typeof headIcon] ?? IconTruck;
        return (
          <article className="stat" key={stat.id}>
            <div className="stat__head">
              <Icon size={16} />
              {stat.label}
            </div>
            <div className="stat__value">{stat.value}</div>
            <div className={`stat__trend is-${stat.trendKind}`}>
              <TrendMark kind={stat.trendKind} />
              {stat.trendLabel}
            </div>
          </article>
        );
      })}
    </section>
  );
}
