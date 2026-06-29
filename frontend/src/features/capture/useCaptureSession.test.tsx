import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiInspection } from "../../api";
import {
  CAPTURE_ANGLES,
  type CaptureSessionApi,
  initialCaptureStatus,
  useCaptureSession,
} from "./useCaptureSession";

const inspection: ApiInspection = {
  id: "inspection-1",
  truck_id: "truck-1",
  status: "uploading",
  capture_source: "mobile",
};

function fakeApi(): CaptureSessionApi {
  return {
    createInspection: vi.fn(),
    finalizeInspection: vi.fn(),
    uploadMedia: vi.fn(),
  };
}

describe("useCaptureSession", () => {
  let api: CaptureSessionApi;

  beforeEach(() => {
    api = fakeApi();
  });

  it("creates independent initial state for every configured angle", () => {
    const first = initialCaptureStatus();
    const second = initialCaptureStatus();

    expect(Object.keys(first)).toEqual(CAPTURE_ANGLES.map((angle) => angle.key));
    expect(first.front).toEqual({ state: "pending", progress: 0 });
    expect(first).not.toBe(second);
  });

  it("starts, uploads with progress, and advances to the next angle", async () => {
    vi.mocked(api.createInspection).mockResolvedValue(inspection);
    vi.mocked(api.uploadMedia).mockImplementation(async ({ onProgress }) => {
      onProgress?.(0.5);
    });
    const { result } = renderHook(() => useCaptureSession(api));

    await act(() => result.current.start("truck-1"));
    expect(result.current.phase).toBe("capture");
    expect(result.current.inspectionId).toBe("inspection-1");

    await act(() => result.current.capture(new Blob(["clip"]), "webm"));
    expect(result.current.status.front).toEqual({ state: "done", progress: 1 });
    expect(result.current.angle.key).toBe("driver_side");
    expect(api.uploadMedia).toHaveBeenCalledWith(
      expect.objectContaining({
        inspectionId: "inspection-1",
        angle: "front",
        filename: "front.webm",
      })
    );
  });

  it("keeps actionable errors for start, upload, and finalization failures", async () => {
    vi.mocked(api.createInspection)
      .mockRejectedValueOnce(new Error("start failed"))
      .mockResolvedValueOnce(inspection);
    vi.mocked(api.uploadMedia).mockRejectedValue(new Error("upload failed"));
    vi.mocked(api.finalizeInspection).mockRejectedValue(new Error("submit failed"));
    const { result } = renderHook(() => useCaptureSession(api));

    await act(() => result.current.start("truck-1"));
    expect(result.current.error).toBe("start failed");
    await act(() => result.current.start("truck-1"));
    await act(() => result.current.capture(new Blob(["clip"]), "webm"));
    expect(result.current.status.front.error).toBe("upload failed");

    vi.mocked(api.uploadMedia).mockResolvedValue(undefined);
    for (let i = 0; i < 4; i += 1) {
      await act(() => result.current.capture(new Blob(["clip"]), "webm"));
    }
    await act(() => result.current.finalize());
    expect(result.current.error).toBe("submit failed");
    expect(result.current.phase).toBe("capture");
  });

  it("blocks skipping required angles", () => {
    const { result } = renderHook(() => useCaptureSession(api));
    act(() => result.current.skip());
    expect(result.current.angle.key).toBe("front");
    expect(result.current.error).toMatch(/required/i);
    expect(api.uploadMedia).not.toHaveBeenCalled();
  });

  it("allows skipping optional angles without touching the API", async () => {
    vi.mocked(api.createInspection).mockResolvedValue(inspection);
    const { result } = renderHook(() => useCaptureSession(api));

    await act(() => result.current.start("truck-1"));
    for (let i = 0; i < 4; i += 1) {
      await act(() => result.current.capture(new Blob(["clip"]), "webm"));
    }
    expect(result.current.angle.key).toBe("top");

    act(() => result.current.skip());
    expect(result.current.angle.key).toBe("undercarriage");
    expect(api.uploadMedia).toHaveBeenCalledTimes(4);
  });

  it("blocks finalize when required angles are missing", async () => {
    vi.mocked(api.createInspection).mockResolvedValue(inspection);
    const { result } = renderHook(() => useCaptureSession(api));

    await act(() => result.current.start("truck-1"));
    await act(() => result.current.finalize());
    expect(result.current.error).toMatch(/Missing required angles/i);
    expect(api.finalizeInspection).not.toHaveBeenCalled();
  });

  it("ignores start when truck id is missing", async () => {
    const { result } = renderHook(() => useCaptureSession(api));
    await act(() => result.current.start(""));
    expect(api.createInspection).not.toHaveBeenCalled();
  });

  it("auto-finalizes after the last angle is captured", async () => {
    vi.mocked(api.createInspection).mockResolvedValue(inspection);
    vi.mocked(api.uploadMedia).mockResolvedValue(undefined);
    vi.mocked(api.finalizeInspection).mockResolvedValue({
      ...inspection,
      status: "submitted",
    });
    const { result } = renderHook(() => useCaptureSession(api));

    await act(() => result.current.start("truck-1"));
    for (let i = 0; i < CAPTURE_ANGLES.length; i += 1) {
      await act(() => result.current.capture(new Blob(["clip"]), "webm"));
    }

    expect(api.finalizeInspection).toHaveBeenCalledWith("inspection-1");
    expect(result.current.phase).toBe("done");
  });

  it("finalizes when skipping optional angles after required coverage", async () => {
    vi.mocked(api.createInspection).mockResolvedValue(inspection);
    vi.mocked(api.uploadMedia).mockResolvedValue(undefined);
    vi.mocked(api.finalizeInspection).mockResolvedValue({
      ...inspection,
      status: "submitted",
    });
    const { result } = renderHook(() => useCaptureSession(api));

    await act(() => result.current.start("truck-1"));
    for (let i = 0; i < 4; i += 1) {
      await act(() => result.current.capture(new Blob(["clip"]), "webm"));
    }
    act(() => result.current.skip());
    await act(async () => {
      result.current.skip();
    });

    expect(api.finalizeInspection).toHaveBeenCalledWith("inspection-1");
    expect(result.current.phase).toBe("done");
  });

  it("uses fallback messages for non-error failures", async () => {
    vi.mocked(api.createInspection)
      .mockRejectedValueOnce("nope")
      .mockResolvedValueOnce(inspection);
    vi.mocked(api.uploadMedia).mockRejectedValueOnce("nope");
    vi.mocked(api.finalizeInspection).mockRejectedValueOnce("nope");
    const { result } = renderHook(() => useCaptureSession(api));

    await act(() => result.current.start("truck-1"));
    expect(result.current.error).toBe("Could not start inspection");

    await act(() => result.current.start("truck-1"));
    await act(() => result.current.capture(new Blob(["clip"]), "webm"));
    expect(result.current.status.front.error).toBe("Upload failed");

    vi.mocked(api.uploadMedia).mockResolvedValue(undefined);
    for (let i = 0; i < 4; i += 1) {
      await act(() => result.current.capture(new Blob(["clip"]), "webm"));
    }
    await act(() => result.current.finalize());
    expect(result.current.error).toBe("Could not finalize inspection");
  });

  it("ignores capture and finalize when prerequisites are missing", async () => {
    const { result } = renderHook(() => useCaptureSession(api));

    await act(() => result.current.capture(new Blob(["clip"]), "webm"));
    await act(() => result.current.finalize());

    expect(api.uploadMedia).not.toHaveBeenCalled();
    expect(api.finalizeInspection).not.toHaveBeenCalled();
  });
});
