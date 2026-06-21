import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  type ApiTruck,
  API_BASE,
  createInspection,
  createTruck,
  finalizeInspection,
  getTrucks,
  uploadMedia,
} from "../api";
import { AngleGuide, type AngleSpec } from "../components/capture/AngleGuide";
import {
  IconArrowLeft,
  IconCheck,
  IconRefresh,
} from "../components/icons";

const ANGLES: AngleSpec[] = [
  { key: "front", label: "Front", hint: "Stand at the front. Film the grille, bumper, and windshield." },
  { key: "driver_side", label: "Driver side", hint: "Walk the driver side, keeping the full length in frame." },
  { key: "rear", label: "Rear", hint: "Film the rear doors, lights, and bumper." },
  { key: "passenger_side", label: "Passenger side", hint: "Walk the passenger side end to end." },
  { key: "top", label: "Top", hint: "Hold the phone high. Capture the roof and trailer top." },
  { key: "undercarriage", label: "Undercarriage", hint: "Low angle near the rear axle. Mind your footing." },
];

type AngleState = {
  state: "pending" | "uploading" | "done" | "error";
  progress: number;
  error?: string;
};

type Phase = "select" | "capture" | "done";

function initialStatus(): Record<string, AngleState> {
  return Object.fromEntries(
    ANGLES.map(
      (a) => [a.key, { state: "pending", progress: 0 }] as [string, AngleState]
    )
  );
}

export function CapturePage() {
  const { truckId } = useParams();

  const [trucks, setTrucks] = useState<ApiTruck[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedTruckId, setSelectedTruckId] = useState<string>(truckId ?? "");
  const [phase, setPhase] = useState<Phase>("select");
  const [inspectionId, setInspectionId] = useState<string | null>(null);
  const [angleIndex, setAngleIndex] = useState(0);
  const [starting, setStarting] = useState(false);
  const [status, setStatus] = useState<Record<string, AngleState>>(initialStatus);
  const [actionError, setActionError] = useState<string | null>(null);
  const [regPlate, setRegPlate] = useState("");
  const [regVin, setRegVin] = useState("");
  const [regMake, setRegMake] = useState("");
  const [regModel, setRegModel] = useState("");
  const [registering, setRegistering] = useState(false);
  const [finalizing, setFinalizing] = useState(false);

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
      setActionError("VIN is required");
      return;
    }
    setRegistering(true);
    setActionError(null);
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
      setActionError(e instanceof Error ? e.message : "Could not register truck");
    } finally {
      setRegistering(false);
    }
  }

  async function startInspection() {
    if (!selectedTruckId) return;
    setStarting(true);
    setActionError(null);
    try {
      const insp = await createInspection(selectedTruckId);
      setInspectionId(insp.id);
      setStatus(initialStatus());
      setAngleIndex(0);
      setPhase("capture");
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Could not start inspection");
    } finally {
      setStarting(false);
    }
  }

  async function handleCaptured(blob: Blob, ext: string) {
    if (!inspectionId) return;
    const angle = ANGLES[angleIndex];
    setStatus((s) => ({ ...s, [angle.key]: { state: "uploading", progress: 0 } }));
    try {
      await uploadMedia({
        inspectionId,
        blob,
        angle: angle.key,
        filename: `${angle.key}.${ext}`,
        onProgress: (f) =>
          setStatus((s) => ({
            ...s,
            [angle.key]: { state: "uploading", progress: f },
          })),
      });
      setStatus((s) => ({ ...s, [angle.key]: { state: "done", progress: 1 } }));
      if (angleIndex < ANGLES.length - 1) setAngleIndex((i) => i + 1);
      else await submitInspection();
    } catch (e) {
      setStatus((s) => ({
        ...s,
        [angle.key]: {
          state: "error",
          progress: 0,
          error: e instanceof Error ? e.message : "Upload failed",
        },
      }));
    }
  }

  async function submitInspection() {
    if (!inspectionId || finalizing) return;
    setFinalizing(true);
    setActionError(null);
    try {
      await finalizeInspection(inspectionId);
      setPhase("done");
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "Could not finalize inspection"
      );
    } finally {
      setFinalizing(false);
    }
  }

  function skipAngle() {
    if (angleIndex < ANGLES.length - 1) setAngleIndex((i) => i + 1);
    else void submitInspection();
  }

  // ---------- SELECT ----------
  if (phase === "select") {
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
                {actionError && <p className="error-note">{actionError}</p>}
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

                {actionError && <p className="error-note">{actionError}</p>}

                <div className="btn-row">
                  <button
                    className="primary-btn"
                    onClick={() => void startInspection()}
                    disabled={!selectedTruckId || starting}
                  >
                    {starting ? "Starting…" : "Start inspection"}
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
  if (phase === "done") {
    const captured = ANGLES.filter((a) => status[a.key]?.state === "done").length;
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
              {captured} of {ANGLES.length} angles uploaded. Conditia is
              extracting frames, detecting damage, and comparing against this
              truck’s history. The report will appear on the dashboard shortly.
            </p>
            <p className="muted mono" style={{ marginTop: 12 }}>
              Inspection {inspectionId}
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
  const angle = ANGLES[angleIndex];
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
          {angleIndex + 1}/{ANGLES.length}
        </span>
      </header>

      <div className="stepper">
        {ANGLES.map((a, i) => {
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
        onCaptured={(blob, ext) => void handleCaptured(blob, ext)}
        disabled={uploading || finalizing}
      />

      <div className="upload-bar">
        {actionError ? (
          <div className="upload-bar__label">
            <span className="error-note">{actionError}</span>
            <button className="text-btn" onClick={() => void submitInspection()}>
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
            <button className="text-btn" onClick={skipAngle}>
              Skip
            </button>
          </div>
        ) : (
          <div className="upload-bar__label">
            <span className="muted">Film this angle, or</span>
            <button className="text-btn" onClick={skipAngle}>
              Skip angle
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
