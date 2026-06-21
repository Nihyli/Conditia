/**
 * Conditia API client.
 * In dev, requests go through Vite's /api proxy (see vite.config.ts).
 * Override with VITE_API_URL if needed.
 */
export const API_BASE: string =
  import.meta.env.VITE_API_URL ?? "/api";

export interface ApiTruck {
  id: string;
  vin: string;
  make: string | null;
  model: string | null;
  year: number | null;
  license_plate: string | null;
}

export interface ApiFinding {
  id: string;
  inspection_id: string;
  title: string | null;
  finding_type: string;
  severity: string;
  confidence: number;
  status: "open" | "acknowledged" | "resolved" | "false_positive";
  zone: string | null;
  location: string | null;
  first_seen_inspection_id: string | null;
  first_detected_inspections_ago: number;
}

export interface ApiInspectionSummary {
  id: string;
  truck_id: string;
  truck_label: string;
  make: string | null;
  model: string | null;
  started_at: string;
  status: string;
  capture_source: string;
  finding_count: number;
  worst_severity: string;
  findings: ApiFinding[];
  media?: ApiMedia[];
}

export interface ApiFleetStats {
  active_trucks: number;
  inspections_today: number;
  inspections_pending: number;
  inspections_complete_today: number;
  open_findings: number;
}

export interface ApiInspection {
  id: string;
  truck_id: string;
  status: string;
  capture_source: string;
}

export interface ApiMedia {
  id: string;
  inspection_id: string;
  media_type: "photo" | "video";
  capture_angle: string | null;
  capture_source: string;
  storage_path: string;
  captured_at: string;
}

export interface TruckCreatePayload {
  vin: string;
  make?: string;
  model?: string;
  year?: number;
  license_plate?: string;
}

const REQUEST_TIMEOUT_MS = 15_000;

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(await errorMessage(res, `GET ${path} failed: ${res.status}`));
  }
  return res.json() as Promise<T>;
}

async function errorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const payload = (await res.json()) as { detail?: unknown };
    return typeof payload.detail === "string" ? payload.detail : fallback;
  } catch {
    return fallback;
  }
}

export function getTrucks(): Promise<ApiTruck[]> {
  return getJson<ApiTruck[]>("/trucks");
}

export function getInspections(): Promise<ApiInspectionSummary[]> {
  return getJson<ApiInspectionSummary[]>("/inspections");
}

export function getInspectionMedia(
  inspectionId: string
): Promise<ApiMedia[]> {
  return getJson<ApiMedia[]>(`/inspections/${inspectionId}/media`);
}

/** Authorized media-delivery endpoint (local file or short-lived redirect). */
export function mediaUrl(mediaId: string): string {
  return `${API_BASE}/inspection-media/${encodeURIComponent(mediaId)}/content`;
}

export function getFleetStats(): Promise<ApiFleetStats> {
  return getJson<ApiFleetStats>("/fleet/stats");
}

export async function createTruck(payload: TruckCreatePayload): Promise<ApiTruck> {
  const res = await fetchWithTimeout(`${API_BASE}/trucks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await errorMessage(res, `Create truck failed: ${res.status}`));
  }
  return res.json() as Promise<ApiTruck>;
}

export async function createInspection(
  truckId: string
): Promise<ApiInspection> {
  const res = await fetchWithTimeout(`${API_BASE}/inspections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ truck_id: truckId, capture_source: "mobile" }),
  });
  if (!res.ok) {
    throw new Error(
      await errorMessage(res, `Create inspection failed: ${res.status}`)
    );
  }
  return res.json() as Promise<ApiInspection>;
}

export async function finalizeInspection(
  inspectionId: string
): Promise<ApiInspection> {
  const res = await fetchWithTimeout(
    `${API_BASE}/inspections/${inspectionId}/finalize`,
    { method: "POST" }
  );
  if (!res.ok) {
    throw new Error(
      await errorMessage(res, `Finalize inspection failed: ${res.status}`)
    );
  }
  return res.json() as Promise<ApiInspection>;
}

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
    xhr.timeout = 60_000;
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
    xhr.ontimeout = () => reject(new Error("Upload timed out"));
    xhr.send(form);
  });
}
