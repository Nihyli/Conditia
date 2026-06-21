import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createInspection,
  createTruck,
  finalizeInspection,
  getFleetStats,
  getInspectionMedia,
  getInspections,
  getTrucks,
  mediaUrl,
  uploadMedia,
} from "./api";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("loads all read models from their documented endpoints", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(response([{ id: "truck-1" }]))
      .mockResolvedValueOnce(response([{ id: "inspection-1" }]))
      .mockResolvedValueOnce(response([{ id: "media-1" }]))
      .mockResolvedValueOnce(response({ active_trucks: 1 }));

    expect(await getTrucks()).toEqual([{ id: "truck-1" }]);
    expect(await getInspections()).toEqual([{ id: "inspection-1" }]);
    expect(await getInspectionMedia("inspection-1")).toEqual([
      { id: "media-1" },
    ]);
    expect(await getFleetStats()).toEqual({ active_trucks: 1 });
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/trucks",
      "/api/inspections",
      "/api/inspections/inspection-1/media",
      "/api/fleet/stats",
    ]);
  });

  it("sends create/finalize payloads and returns safe API errors", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(response({ id: "truck-1" }, 201))
      .mockResolvedValueOnce(response({ id: "inspection-1" }, 201))
      .mockResolvedValueOnce(response({ id: "inspection-1", status: "submitted" }))
      .mockResolvedValueOnce(response({ detail: "VIN already exists" }, 409));

    await createTruck({ vin: "1FUJGLDR0CSBT0041" });
    await createInspection("truck-1");
    await finalizeInspection("inspection-1");
    await expect(
      createTruck({ vin: "1FUJGLDR0CSBT0041" })
    ).rejects.toThrow("VIN already exists");

    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[1][1]?.body).toContain("truck-1");
    expect(fetchMock.mock.calls[2][1]?.method).toBe("POST");
  });

  it("uses fallback errors for non-JSON failures and encodes media IDs", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("gateway failed", { status: 502 })
    );

    await expect(getTrucks()).rejects.toThrow("GET /trucks failed: 502");
    expect(mediaUrl("media/id")).toBe(
      "/api/inspection-media/media%2Fid/content"
    );
  });
});

class FakeXMLHttpRequest {
  static status = 200;
  static responseText = "";
  method = "";
  url = "";
  status = 0;
  responseText = "";
  timeout = 0;
  upload: {
    onprogress?: (event: { lengthComputable: boolean; loaded: number; total: number }) => void;
  } = {};
  onload?: () => void;
  onerror?: () => void;
  ontimeout?: () => void;

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  send(body: FormData) {
    expect(body.get("capture_angle")).toBe("front");
    this.status = FakeXMLHttpRequest.status;
    this.responseText = FakeXMLHttpRequest.responseText;
    this.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 });
    this.onload?.();
  }
}

describe("uploadMedia", () => {
  beforeEach(() => {
    FakeXMLHttpRequest.status = 200;
    FakeXMLHttpRequest.responseText = "";
    vi.stubGlobal(
      "XMLHttpRequest",
      FakeXMLHttpRequest as unknown as typeof XMLHttpRequest
    );
  });

  it("reports progress and resolves a successful multipart upload", async () => {
    const onProgress = vi.fn();
    await uploadMedia({
      inspectionId: "inspection-1",
      blob: new Blob(["video"]),
      angle: "front",
      filename: "front.webm",
      onProgress,
    });

    expect(onProgress).toHaveBeenNthCalledWith(1, 0.5);
    expect(onProgress).toHaveBeenLastCalledWith(1);
  });

  it("rejects unsuccessful uploads", async () => {
    FakeXMLHttpRequest.status = 413;
    FakeXMLHttpRequest.responseText = JSON.stringify({ detail: "too large" });

    await expect(
      uploadMedia({
        inspectionId: "inspection-1",
        blob: new Blob(["video"]),
        angle: "front",
        filename: "front.webm",
      })
    ).rejects.toThrow("too large");
  });
});
