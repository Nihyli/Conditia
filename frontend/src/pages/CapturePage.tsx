import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  type ApiTruck,
  API_BASE,
  createTruck,
  getTrucks,
} from "../api";
import { AngleGuide } from "../components/capture/AngleGuide";
import {
  IconArrowLeft,
  IconCheck,
  IconRefresh,
} from "../components/icons";
import {
  CAPTURE_ANGLES,
  useCaptureSession,
} from "../features/capture/useCaptureSession";

export function CapturePage() {
  const { truckId } = useParams();

  const [trucks, setTrucks] = useState<ApiTruck[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedTruckId, setSelectedTruckId] = useState<string>(truckId ?? "");
  const captureSession = useCaptureSession();
  const [registrationError, setRegistrationError] = useState<string | null>(null);
  const [regPlate, setRegPlate] = useState("");
  const [regVin, setRegVin] = useState("");
  const [regMake, setRegMake] = useState("");
  const [regModel, setRegModel] = useState("");
  const [registering, setRegistering] = useState(false);

  useEffect(() => {
    void loadTrucks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadTrucks() {
    setLoadError(null);
    try {
      const t = await getTrucks();
      setTrucks(t);
      setSelectedTruckId((cur) => cur || truckId || (t[0]?.id ?? ""));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to reach the API");
    }
  }

  async function registerTruck() {
    if (!regVin.trim()) {
      setRegistrationError("VIN is required");
      return;
    }
    setRegistering(true);
    setRegistrationError(null);
    try {
      const truck = await createTruck({
        vin: regVin.trim(),
        license_plate: regPlate.trim() || undefined,
        make: regMake.trim() || undefined,
        model: regModel.trim() || undefined,
      });
      await loadTrucks();
      setSelectedTruckId(truck.id);
      setRegPlate("");
      setRegVin("");
      setRegMake("");
      setRegModel("");
    } catch (e) {
      setRegistrationError(
        e instanceof Error ? e.message : "Could not register truck"
      );
    } finally {
      setRegistering(false);
    }
  }

  // ---------- SELECT ----------
  if (captureSession.phase === "select") {
    return (
      <div className="capture">
        <header className="capture__top">
          <Link to="/" className="icon-btn" aria-label="Back to dashboard">
            <IconArrowLeft size={20} />
          </Link>
          <span className="capture__title">New inspection</span>
        </header>

        <div className="capture-panel">
          <div className="select-card">
            <h2 className="select-card__title">Which truck are you inspecting?</h2>
            <p className="muted">
              You’ll film 6 angles. Each clip uploads as you go, then Conditia
              runs the analysis and posts the report to the dashboard.
            </p>

            {loadError ? (
              <div className="api-down">
                <p className="error-note">Can’t reach the Conditia API at {API_BASE}.</p>
                <p className="muted">
                  Start the backend, then retry:{" "}
                  <code>uvicorn main:app --reload --port 8001</code>
                </p>
                <button className="primary-btn" onClick={() => void loadTrucks()}>
                  <IconRefresh size={16} />
                  Retry
                </button>
              </div>
            ) : trucks === null ? (
              <p className="muted" style={{ marginTop: 16 }}>Loading trucks…</p>
            ) : trucks.length === 0 ? (
              <>
                <p className="muted" style={{ marginTop: 8 }}>
                  No trucks in the fleet yet. Register one to start inspecting.
                </p>
                <label className="field-label" htmlFor="plate">
                  License plate / fleet ID
                </label>
                <input
                  id="plate"
                  className="select"
                  placeholder="TRK-041"
                  value={regPlate}
                  onChange={(e) => setRegPlate(e.target.value)}
                />
                <label className="field-label" htmlFor="vin">
                  VIN (required)
                </label>
                <input
                  id="vin"
                  className="select"
                  placeholder="1FUJGLDR0CSBT0041"
                  value={regVin}
                  onChange={(e) => setRegVin(e.target.value)}
                />
                <label className="field-label" htmlFor="make">
                  Make
                </label>
                <input
                  id="make"
                  className="select"
                  placeholder="Freightliner"
                  value={regMake}
                  onChange={(e) => setRegMake(e.target.value)}
                />
                <label className="field-label" htmlFor="model">
                  Model
                </label>
                <input
                  id="model"
                  className="select"
                  placeholder="Cascadia"
                  value={regModel}
                  onChange={(e) => setRegModel(e.target.value)}
                />
                {registrationError && (
                  <p className="error-note">{registrationError}</p>
                )}
                <div className="btn-row">
                  <button
                    className="primary-btn"
                    onClick={() => void registerTruck()}
                    disabled={registering}
                  >
                    {registering ? "Registering…" : "Register truck"}
                  </button>
                  <Link to="/" className="text-btn">
                    Back
                  </Link>
                </div>
              </>
            ) : (
              <>
                <label className="field-label" htmlFor="truck">
                  Truck
                </label>
                <select
                  id="truck"
                  className="select"
                  value={selectedTruckId}
                  onChange={(e) => setSelectedTruckId(e.target.value)}
                >
                  {trucks.map((t) => (
                    <option key={t.id} value={t.id}>
                      {(t.license_plate || t.vin) +
                        (t.make ? ` — ${t.make} ${t.model ?? ""}` : "")}
                    </option>
                  ))}
                </select>

                {captureSession.error && (
                  <p className="error-note">{captureSession.error}</p>
                )}

                <div className="btn-row">
                  <button
                    className="primary-btn"
                    onClick={() => void captureSession.start(selectedTruckId)}
                    disabled={!selectedTruckId || captureSession.starting}
                  >
                    {captureSession.starting ? "Starting…" : "Start inspection"}
                  </button>
                  <Link to="/" className="text-btn">
                    Cancel
                  </Link>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ---------- DONE ----------
  if (captureSession.phase === "done") {
    const captured = CAPTURE_ANGLES.filter(
      (angle) => captureSession.status[angle.key]?.state === "done"
    ).length;
    return (
      <div className="capture">
        <header className="capture__top">
          <Link to="/" className="icon-btn" aria-label="Back to dashboard">
            <IconArrowLeft size={20} />
          </Link>
          <span className="capture__title">Inspection submitted</span>
        </header>

        <div className="capture-panel">
          <div className="done-card">
            <div className="done-icon">
              <IconCheck size={28} />
            </div>
            <h2 className="select-card__title">Analysis queued</h2>
            <p className="muted">
              {captured} of {CAPTURE_ANGLES.length} angles uploaded. Conditia is
              extracting frames, detecting damage, and comparing against this
              truck’s history. The report will appear on the dashboard shortly.
            </p>
            <p className="muted mono" style={{ marginTop: 12 }}>
              Inspection {captureSession.inspectionId}
            </p>
            <div className="btn-row">
              <Link to="/" className="primary-btn">
                View on dashboard
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---------- CAPTURE ----------
  const { angle, angleIndex, status, finalizing } = captureSession;
  const current = status[angle.key];
  const uploading = current?.state === "uploading";

  return (
    <div className="capture">
      <header className="capture__top">
        <Link to="/" className="icon-btn" aria-label="Back to dashboard">
          <IconArrowLeft size={20} />
        </Link>
        <span className="capture__title">{angle.label}</span>
        <span className="capture__step mono">
          {angleIndex + 1}/{CAPTURE_ANGLES.length}
        </span>
      </header>

      <div className="stepper">
        {CAPTURE_ANGLES.map((a, i) => {
          const st = status[a.key]?.state;
          const cls =
            st === "done"
              ? "is-done"
              : i === angleIndex
                ? "is-active"
                : "";
          return <span key={a.key} className={`stepper__seg ${cls}`} />;
        })}
      </div>

      <AngleGuide
        key={angle.key}
        angle={angle}
        onCaptured={(blob, ext) => void captureSession.capture(blob, ext)}
        disabled={uploading || finalizing}
      />

      <div className="upload-bar">
        {captureSession.error ? (
          <div className="upload-bar__label">
            <span className="error-note">{captureSession.error}</span>
            <button
              className="text-btn"
              onClick={() => void captureSession.finalize()}
            >
              Retry submit
            </button>
          </div>
        ) : uploading || finalizing ? (
          <>
            <div className="upload-bar__label">
              <span>
                {finalizing
                  ? "Submitting inspection…"
                  : `Uploading ${angle.label.toLowerCase()}…`}
              </span>
              {!finalizing && (
                <span className="mono">
                  {Math.round((current?.progress ?? 0) * 100)}%
                </span>
              )}
            </div>
            <div className="upload-bar__track">
              <div
                className="upload-bar__fill"
                style={{
                  width: finalizing
                    ? "100%"
                    : `${Math.round((current?.progress ?? 0) * 100)}%`,
                }}
              />
            </div>
          </>
        ) : current?.state === "error" ? (
          <div className="upload-bar__label">
            <span className="error-note">{current.error}</span>
            <button className="text-btn" onClick={captureSession.skip}>
              Skip
            </button>
          </div>
        ) : (
          <div className="upload-bar__label">
            <span className="muted">Film this angle, or</span>
            <button className="text-btn" onClick={captureSession.skip}>
              Skip angle
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
