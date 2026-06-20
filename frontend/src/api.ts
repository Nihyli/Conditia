/**
 * Conditia API client. Talks to the FastAPI backend.
 * Base URL is configurable via VITE_API_URL (defaults to local dev backend).
 */

export const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  "http://localhost:8000";

export interface ApiTruck {
  id: string;
  vin: string;
  make: string | null;
  model: string | null;
  year: number | null;
  license_plate: string | null;
}

export interface ApiInspection {
  id: string;
  truck_id: string;
  status: string;
  capture_source: string;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export function getTrucks(): Promise<ApiTruck[]> {
  return getJson<ApiTruck[]>("/trucks");
}

export async function createInspection(
  truckId: string
): Promise<ApiInspection> {
  const res = await fetch(`${API_BASE}/inspections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ truck_id: truckId, capture_source: "mobile" }),
  });
  if (!res.ok) throw new Error(`Create inspection failed: ${res.status}`);
  return res.json() as Promise<ApiInspection>;
}

/**
 * Upload one captured clip for a given angle, reporting upload progress (0..1).
 * Uses XHR so we can surface per-angle progress in the UI.
 */
export function uploadMedia(params: {
  inspectionId: string;
  blob: Blob;
  angle: string;
  filename: string;
  onProgress?: (fraction: number) => void;
}): Promise<void> {
  const { inspectionId, blob, angle, filename, onProgress } = params;
  return new Promise<void>((resolve, reject) => {
    const form = new FormData();
    form.append("files", blob, filename);
    form.append("capture_angle", angle);
    form.append("capture_source", "mobile");

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/inspections/${inspectionId}/upload`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(1);
        resolve();
      } else {
        reject(new Error(xhr.responseText || `Upload failed: ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(form);
  });
}
