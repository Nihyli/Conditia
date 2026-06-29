/**
 * Conditia API client.
 * In dev, requests go through Vite's /api proxy (see vite.config.ts).
 * Override with VITE_API_URL if needed.
 */
import { authHeaders } from "./auth/session";

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
  resolution_notes: string | null;
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

export interface ApiFleetMember {
  fleet_id: string;
  user_id: string;
  role: "viewer" | "inspector" | "admin";
}

export interface ApiInspectionCoverage {
  required: string[];
  optional: string[];
  present: string[];
  missing_required: string[];
  complete: boolean;
}

export interface ApiMedia {
  id: string;
  inspection_id: string;
  media_type: "photo" | "video";
  capture_angle: string | null;
  capture_source: string;
  captured_at: string;
}

export interface TruckCreatePayload {
  vin: string;
  make?: string;
  model?: string;
  year?: number;
  license_plate?: string;
}

export interface ApiInspectionRecord {
  id: string;
  truck_id: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  capture_source: string;
}

export interface ApiReport {
  id: string;
  inspection_id: string;
  generated_at: string;
  summary: string | null;
  total_findings: number;
  critical_findings: number;
  pdf_path: string | null;
  raw_json: {
    inspection_id: string;
    total_findings: number;
    critical_findings: number;
    requires_human_review?: boolean;
    findings: Array<{
      id: string;
      title: string | null;
      type: string;
      severity: string;
      confidence: number;
      status: string;
      zone: string | null;
      location: string | null;
      first_seen_inspection_id: string | null;
    }>;
  } | null;
}

export type FindingStatusFilter =
  | "open"
  | "acknowledged"
  | "resolved"
  | "false_positive";

export interface FindingUpdatePayload {
  status: FindingStatusFilter;
  resolution_notes?: string;
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

async function errorMessage(res: Response, fallback: string): Promise<string> {
  try {
    return detailMessage(await res.json(), fallback);
  } catch {
    return fallback;
  }
}

function detailMessage(payload: unknown, fallback: string): string {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }
  return fallback;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = {
    ...authHeaders(),
    ...(init?.headers as Record<string, string> | undefined),
  };
  const response = await fetchWithTimeout(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const method = init?.method ?? "GET";
    throw new Error(
      await errorMessage(
        response,
        `${method} ${path} failed: ${response.status}`
      )
    );
  }
  return response.json() as Promise<T>;
}

function buildQuery(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function getTrucks(): Promise<ApiTruck[]> {
  return requestJson<ApiTruck[]>("/trucks");
}

export function getTruck(truckId: string): Promise<ApiTruck> {
  return requestJson<ApiTruck>(`/trucks/${encodeURIComponent(truckId)}`);
}

export function getTruckInspections(
  truckId: string
): Promise<ApiInspectionRecord[]> {
  return requestJson<ApiInspectionRecord[]>(
    `/trucks/${encodeURIComponent(truckId)}/inspections`
  );
}

export function getInspections(): Promise<ApiInspectionSummary[]> {
  return requestJson<ApiInspectionSummary[]>("/inspections");
}

export function getInspection(
  inspectionId: string
): Promise<ApiInspectionSummary> {
  return requestJson<ApiInspectionSummary>(
    `/inspections/${encodeURIComponent(inspectionId)}`
  );
}

export function getFindings(params?: {
  severity?: string;
  status?: FindingStatusFilter;
}): Promise<ApiFinding[]> {
  const query = buildQuery({
    severity: params?.severity,
    status: params?.status,
  });
  return requestJson<ApiFinding[]>(`/findings${query}`);
}

export function updateFinding(
  findingId: string,
  payload: FindingUpdatePayload
): Promise<ApiFinding> {
  return requestJson<ApiFinding>(`/findings/${encodeURIComponent(findingId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getReports(): Promise<ApiReport[]> {
  return requestJson<ApiReport[]>("/reports");
}

export function getReport(inspectionId: string): Promise<ApiReport> {
  return requestJson<ApiReport>(
    `/reports/${encodeURIComponent(inspectionId)}`
  );
}

export function getInspectionMedia(
  inspectionId: string
): Promise<ApiMedia[]> {
  return requestJson<ApiMedia[]>(`/inspections/${inspectionId}/media`);
}

/** Authorized media-delivery endpoint (local file or short-lived redirect). */
export function mediaUrl(mediaId: string): string {
  return `${API_BASE}/inspection-media/${encodeURIComponent(mediaId)}/content`;
}

export function getFleetStats(): Promise<ApiFleetStats> {
  return requestJson<ApiFleetStats>("/fleet/stats");
}

export function getFleetMembers(): Promise<ApiFleetMember[]> {
  return requestJson<ApiFleetMember[]>("/fleet/members");
}

export function addFleetMember(payload: {
  user_id: string;
  role: ApiFleetMember["role"];
}): Promise<ApiFleetMember> {
  return requestJson<ApiFleetMember>("/fleet/members", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateFleetMember(
  userId: string,
  role: ApiFleetMember["role"]
): Promise<ApiFleetMember> {
  return requestJson<ApiFleetMember>(
    `/fleet/members/${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    }
  );
}

export async function removeFleetMember(userId: string): Promise<void> {
  const response = await fetchWithTimeout(
    `${API_BASE}/fleet/members/${encodeURIComponent(userId)}`,
    {
      method: "DELETE",
      headers: authHeaders(),
    }
  );
  if (!response.ok) {
    throw new Error(
      await errorMessage(response, `DELETE /fleet/members/${userId} failed`)
    );
  }
}

export function getInspectionCoverage(
  inspectionId: string
): Promise<ApiInspectionCoverage> {
  return requestJson<ApiInspectionCoverage>(
    `/inspections/${encodeURIComponent(inspectionId)}/coverage`
  );
}

export function createTruck(payload: TruckCreatePayload): Promise<ApiTruck> {
  return requestJson<ApiTruck>("/trucks", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
}

export function createInspection(truckId: string): Promise<ApiInspection> {
  return requestJson<ApiInspection>("/inspections", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ truck_id: truckId, capture_source: "mobile" }),
  });
}

export function finalizeInspection(
  inspectionId: string
): Promise<ApiInspection> {
  return requestJson<ApiInspection>(
    `/inspections/${inspectionId}/finalize`,
    { method: "POST" }
  );
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
    const headers = authHeaders();
    for (const [name, value] of Object.entries(headers)) {
      xhr.setRequestHeader(name, value);
    }
    xhr.timeout = 60_000;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(1);
        resolve();
      } else {
        let payload: unknown;
        try {
          payload = JSON.parse(xhr.responseText);
        } catch {
          payload = null;
        }
        reject(
          new Error(detailMessage(payload, `Upload failed: ${xhr.status}`))
        );
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.ontimeout = () => reject(new Error("Upload timed out"));
    xhr.send(form);
  });
}
