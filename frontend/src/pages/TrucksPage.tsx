import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createTruck, getTrucks } from "../api";
import { PageAlert } from "../components/PageAlert";
import { ROUTES } from "../nav";
import type { ApiTruck } from "../api";

export function TrucksPage() {
  const [trucks, setTrucks] = useState<ApiTruck[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [vin, setVin] = useState("");
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [year, setYear] = useState("");
  const [licensePlate, setLicensePlate] = useState("");

  const load = useCallback(async () => {
    try {
      setTrucks(await getTrucks());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load trucks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await createTruck({
        vin: vin.trim().toUpperCase(),
        make: make.trim() || undefined,
        model: model.trim() || undefined,
        year: year ? Number(year) : undefined,
        license_plate: licensePlate.trim() || undefined,
      });
      setVin("");
      setMake("");
      setModel("");
      setYear("");
      setLicensePlate("");
      setShowForm(false);
      await load();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Failed to register truck");
    } finally {
      setSubmitting(false);
    }
  }

  if (error) {
    return (
      <PageAlert message="Could not load trucks." detail={error} onRetry={() => void load()} />
    );
  }

  if (loading) {
    return <p className="muted">Loading trucks…</p>;
  }

  return (
    <>
      <section className="panel">
        <div className="panel__head">
          <h2 className="panel__title">Fleet assets</h2>
          <div className="panel__spacer" />
          <button
            className="primary-btn"
            type="button"
            onClick={() => setShowForm((v) => !v)}
          >
            {showForm ? "Cancel" : "Register truck"}
          </button>
        </div>

        {showForm ? (
          <form className="form-grid" onSubmit={(e) => void handleSubmit(e)}>
            <label className="form-field">
              <span>VIN</span>
              <input
                required
                minLength={17}
                maxLength={17}
                value={vin}
                onChange={(e) => setVin(e.target.value)}
                placeholder="1FUJGLDR0CSBT0041"
              />
            </label>
            <label className="form-field">
              <span>Make</span>
              <input value={make} onChange={(e) => setMake(e.target.value)} />
            </label>
            <label className="form-field">
              <span>Model</span>
              <input value={model} onChange={(e) => setModel(e.target.value)} />
            </label>
            <label className="form-field">
              <span>Year</span>
              <input
                type="number"
                min={1900}
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </label>
            <label className="form-field">
              <span>License plate</span>
              <input
                value={licensePlate}
                onChange={(e) => setLicensePlate(e.target.value)}
              />
            </label>
            {formError ? <p className="error-note">{formError}</p> : null}
            <div className="form-actions">
              <button className="primary-btn" type="submit" disabled={submitting}>
                {submitting ? "Saving…" : "Save truck"}
              </button>
            </div>
          </form>
        ) : null}
      </section>

      <section className="panel">
        {trucks.length === 0 ? (
          <div className="empty">
            <div className="empty__title">No trucks registered</div>
            <p className="muted">Add your first asset to begin inspections.</p>
          </div>
        ) : (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>VIN</th>
                  <th>Make / model</th>
                  <th>Year</th>
                  <th>Plate</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {trucks.map((truck) => (
                  <tr key={truck.id}>
                    <td className="mono">{truck.vin}</td>
                    <td>
                      {[truck.make, truck.model].filter(Boolean).join(" ") || "—"}
                    </td>
                    <td className="mono">{truck.year ?? "—"}</td>
                    <td>{truck.license_plate ?? "—"}</td>
                    <td className="data-table__actions">
                      <Link to={ROUTES.truckDetail(truck.id)} className="text-link">
                        View
                      </Link>
                      <Link to={`/capture/${truck.id}`} className="text-link">
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
