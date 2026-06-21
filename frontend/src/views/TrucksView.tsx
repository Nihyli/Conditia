import type { ApiTruck } from "../api";
import type { Inspection } from "../types";

export function TrucksView({
  trucks,
  inspections,
  onSelectInspection,
}: {
  trucks: ApiTruck[];
  inspections: Inspection[];
  onSelectInspection: (id: string) => void;
}) {
  if (trucks.length === 0) {
    return (
      <section className="panel">
        <div className="empty">
          <div className="empty__title">No trucks registered</div>
          <p className="muted">
            Register a truck from the capture flow to start inspecting.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Fleet trucks</h2>
        <span className="muted">{trucks.length} registered</span>
      </div>
      <div className="data-table">
        {trucks.map((truck) => {
          const truckInspections = inspections.filter(
            (i) => i.truckId === truck.id
          );
          const latest = truckInspections[0];
          return (
            <div className="data-row" key={truck.id}>
              <div className="data-row__primary">
                <span className="data-row__label mono">
                  {truck.license_plate || truck.vin}
                </span>
                <span className="data-row__sub">
                  {[truck.make, truck.model].filter(Boolean).join(" ") ||
                    "Unnamed truck"}
                </span>
              </div>
              <div className="data-row__meta">
                <span>{truckInspections.length} inspection(s)</span>
                {latest && (
                  <button
                    type="button"
                    className="text-btn"
                    onClick={() => onSelectInspection(latest.id)}
                  >
                    View latest
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
