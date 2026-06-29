import { useState } from "react";
import {
  createInspection,
  finalizeInspection,
  uploadMedia,
} from "../../api";
import type { AngleSpec } from "../../components/capture/AngleGuide";

export const CAPTURE_ANGLES: AngleSpec[] = [
  {
    key: "front",
    label: "Front",
    hint: "Stand at the front. Film the grille, bumper, and windshield.",
    required: true,
  },
  {
    key: "driver_side",
    label: "Driver side",
    hint: "Walk the driver side, keeping the full length in frame.",
    required: true,
  },
  {
    key: "rear",
    label: "Rear",
    hint: "Film the rear doors, lights, and bumper.",
    required: true,
  },
  {
    key: "passenger_side",
    label: "Passenger side",
    hint: "Walk the passenger side end to end.",
    required: true,
  },
  {
    key: "top",
    label: "Top",
    hint: "Hold the phone high. Capture the roof and trailer top.",
    required: false,
  },
  {
    key: "undercarriage",
    label: "Undercarriage",
    hint: "Low angle near the rear axle. Mind your footing.",
    required: false,
  },
];

export const REQUIRED_CAPTURE_ANGLES = CAPTURE_ANGLES.filter((a) => a.required).map(
  (a) => a.key
);

export function missingRequiredAngles(
  status: Record<string, AngleState>
): string[] {
  return REQUIRED_CAPTURE_ANGLES.filter((key) => status[key]?.state !== "done");
}

export type AngleState = {
  state: "pending" | "uploading" | "done" | "error";
  progress: number;
  error?: string;
};

export type CapturePhase = "select" | "capture" | "done";

export interface CaptureSessionApi {
  createInspection: typeof createInspection;
  finalizeInspection: typeof finalizeInspection;
  uploadMedia: typeof uploadMedia;
}

const defaultApi: CaptureSessionApi = {
  createInspection,
  finalizeInspection,
  uploadMedia,
};

export function initialCaptureStatus(): Record<string, AngleState> {
  return Object.fromEntries(
    CAPTURE_ANGLES.map(
      (angle) => [angle.key, { state: "pending", progress: 0 }] as const
    )
  );
}

export function useCaptureSession(api: CaptureSessionApi = defaultApi) {
  const [phase, setPhase] = useState<CapturePhase>("select");
  const [inspectionId, setInspectionId] = useState<string | null>(null);
  const [angleIndex, setAngleIndex] = useState(0);
  const [status, setStatus] = useState<Record<string, AngleState>>(
    initialCaptureStatus
  );
  const [starting, setStarting] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const angle = CAPTURE_ANGLES[angleIndex];

  async function start(truckId: string) {
    if (!truckId) return;
    setStarting(true);
    setError(null);
    try {
      const inspection = await api.createInspection(truckId);
      setInspectionId(inspection.id);
      setStatus(initialCaptureStatus());
      setAngleIndex(0);
      setPhase("capture");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not start inspection");
    } finally {
      setStarting(false);
    }
  }

  async function finalize() {
    if (!inspectionId || finalizing) return;
    const missing = missingRequiredAngles(status);
    if (missing.length > 0) {
      setError(
        `Missing required angles: ${missing.join(", ")}. Capture each required angle before submitting.`
      );
      return;
    }
    setFinalizing(true);
    setError(null);
    try {
      await api.finalizeInspection(inspectionId);
      setPhase("done");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not finalize inspection"
      );
    } finally {
      setFinalizing(false);
    }
  }

  async function capture(blob: Blob, extension: string) {
    if (!inspectionId) return;
    setStatus((current) => ({
      ...current,
      [angle.key]: { state: "uploading", progress: 0 },
    }));
    try {
      await api.uploadMedia({
        inspectionId,
        blob,
        angle: angle.key,
        filename: `${angle.key}.${extension}`,
        onProgress: (progress) =>
          setStatus((current) => ({
            ...current,
            [angle.key]: { state: "uploading", progress },
          })),
      });
      setStatus((current) => ({
        ...current,
        [angle.key]: { state: "done", progress: 1 },
      }));
      if (angleIndex < CAPTURE_ANGLES.length - 1) {
        setAngleIndex((current) => current + 1);
      } else {
        await finalize();
      }
    } catch (cause) {
      setStatus((current) => ({
        ...current,
        [angle.key]: {
          state: "error",
          progress: 0,
          error: cause instanceof Error ? cause.message : "Upload failed",
        },
      }));
    }
  }

  function skip() {
    if (angle.required) {
      setError(`${angle.label} is required and cannot be skipped.`);
      return;
    }
    setError(null);
    if (angleIndex < CAPTURE_ANGLES.length - 1) {
      setAngleIndex((current) => current + 1);
    } else {
      void finalize();
    }
  }

  return {
    phase,
    inspectionId,
    angle,
    angleIndex,
    status,
    starting,
    finalizing,
    error,
    missingRequired: missingRequiredAngles(status),
    start,
    capture,
    finalize,
    skip,
  };
}
