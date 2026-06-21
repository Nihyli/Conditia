/**
 * Conditia API client.
 * In dev, requests go through Vite's /api proxy (see vite.config.ts).
 * Override with VITE_API_URL if needed.
 */
import type { AuthConfig, AuthUser, LoginResult } from "./auth/types";

export const API_BASE: string =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.DEV ? "/api" : "http://localhost:8000");

let authTokenGetter: (() => string | null) | null = null;
/** Synchronous token store — updated immediately on login (React state lags). */
let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

export function setAuthTokenGetter(getter: () => string | null) {
  authTokenGetter = getter;
}

function getToken(): string | null {
  return authToken ?? authTokenGetter?.() ?? null;
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const headers = new Headers(extra);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

async function parseApiError(res: Response, fallback: string): Promise<string> {
  const text = await res.text();
  try {
    const json = JSON.parse(text) as { detail?: string | { msg: string }[] };
    if (typeof json.detail === "string") return json.detail;
    if (Array.isArray(json.detail) && json.detail[0]?.msg) {
      return json.detail[0].msg;
    }
  } catch {
    /* plain text */
  }
  return text || fallback;
}

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

export interface ApiDataStatus {
  fleets: number;
  trucks: number;
  inspections: number;
  findings: number;
  media: number;
  reports: number;
  storage_files: number;
  has_data: boolean;
  demo_fleet_name: string | null;
}

export interface ApiSeedResult {
  seeded: boolean;
  message: string;
  counts?: ApiDataStatus;
}

export interface ApiUnseedResult {
  cleared: boolean;
  message: string;
  cleared_counts: {
    fleets: number;
    trucks: number;
    inspections: number;
    findings: number;
    media: number;
    reports: number;
    storage_files: number;
  };
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

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) {
    throw new Error(await parseApiError(res, `GET ${path} failed: ${res.status}`));
  }
  return res.json() as Promise<T>;
}

async function postJson<T>(
  path: string,
  query?: Record<string, boolean>,
  body?: unknown
): Promise<T> {
  const qs =
    query && Object.keys(query).length > 0
      ? `?${new URLSearchParams(
          Object.fromEntries(
            Object.entries(query).map(([k, v]) => [k, String(v)])
          )
        )}`
      : "";
  const headers = authHeaders(
    body !== undefined ? { "Content-Type": "application/json" } : undefined
  );
  const res = await fetch(`${API_BASE}${path}${qs}`, {
    method: "POST",
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(await parseApiError(res, `POST ${path} failed: ${res.status}`));
  }
  return res.json() as Promise<T>;
}

export function getAuthConfig(): Promise<AuthConfig> {
  return getJson<AuthConfig>("/auth/config");
}

export function getMe(): Promise<AuthUser> {
  return getJson<AuthUser>("/auth/me");
}

export function syncSupabaseUser(): Promise<AuthUser> {
  return postJson<AuthUser>("/auth/sync");
}

export function loginLocal(email: string, password: string): Promise<LoginResult> {
  return postJson<LoginResult>("/auth/login", undefined, { email, password });
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

/** Public URL for a file stored on the backend (works through Vite /api proxy). */
export function mediaUrl(storagePath: string): string {
  const encoded = storagePath
    .split("/")
    .map((seg) => encodeURIComponent(seg))
    .join("/");
  return `${API_BASE}/media/${encoded}`;
}

export function getFleetStats(): Promise<ApiFleetStats> {
  return getJson<ApiFleetStats>("/fleet/stats");
}

export function getDataStatus(): Promise<ApiDataStatus> {
  return getJson<ApiDataStatus>("/admin/data-status");
}

export function seedDemoData(force = false): Promise<ApiSeedResult> {
  return postJson<ApiSeedResult>("/admin/seed", { force });
}

export function unseedAllData(clearStorage = true): Promise<ApiUnseedResult> {
  return postJson<ApiUnseedResult>("/admin/unseed", {
    clear_storage: clearStorage,
  });
}

export async function createTruck(payload: TruckCreatePayload): Promise<ApiTruck> {
  const res = await fetch(`${API_BASE}/trucks`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Create truck failed: ${res.status}`);
  return res.json() as Promise<ApiTruck>;
}

export async function createInspection(
  truckId: string
): Promise<ApiInspection> {
  const res = await fetch(`${API_BASE}/inspections`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ truck_id: truckId, capture_source: "mobile" }),
  });
  if (!res.ok) throw new Error(`Create inspection failed: ${res.status}`);
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
  const token = getToken();
  return new Promise<void>((resolve, reject) => {
    const form = new FormData();
    form.append("files", blob, filename);
    form.append("capture_angle", angle);
    form.append("capture_source", "mobile");

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/inspections/${inspectionId}/upload`);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
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
