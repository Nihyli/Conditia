import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AngleGuide } from "./AngleGuide";

const angle = { key: "front", label: "Front", hint: "Film the front" };

function setCamera(result: Promise<MediaStream>) {
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn().mockReturnValue(result) },
  });
}

describe("AngleGuide", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("offers file upload when camera permission fails", async () => {
    setCamera(Promise.reject(new Error("Permission denied")));
    const onCaptured = vi.fn();
    const user = userEvent.setup();
    const { container } = render(
      <AngleGuide angle={angle} onCaptured={onCaptured} />
    );

    expect(await screen.findByText("Camera unavailable on this device.")).toBeInTheDocument();
    expect(screen.getByText("Permission denied")).toBeInTheDocument();
    const input = container.querySelector("input[type='file']") as HTMLInputElement;
    const file = new File(["image"], "front.jpg", { type: "image/jpeg" });
    await user.upload(input, file);
    expect(onCaptured).toHaveBeenCalledWith(file, "jpg");
  });

  it("records supported media and stops camera tracks on unmount", async () => {
    const stopTrack = vi.fn();
    const stream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
    setCamera(Promise.resolve(stream));

    class Recorder {
      static isTypeSupported = vi.fn(() => true);
      state: RecordingState = "inactive";
      mimeType: string;
      ondataavailable?: (event: { data: Blob }) => void;
      onstop?: () => void;

      constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
        this.mimeType = options?.mimeType ?? "video/webm";
      }

      start() {
        this.state = "recording";
      }

      stop() {
        this.state = "inactive";
        this.ondataavailable?.({ data: new Blob(["clip"], { type: this.mimeType }) });
        this.onstop?.();
      }
    }
    vi.stubGlobal("MediaRecorder", Recorder);
    const onCaptured = vi.fn();
    const user = userEvent.setup();
    const { unmount } = render(
      <AngleGuide angle={angle} onCaptured={onCaptured} />
    );

    const record = await screen.findByRole("button", { name: "Record Front" });
    await waitFor(() => expect(record).toBeEnabled());
    await user.click(record);
    expect(screen.getByText("Recording — tap to stop")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Stop recording" }));

    expect(onCaptured).toHaveBeenCalledTimes(1);
    expect(onCaptured.mock.calls[0][1]).toBe("mp4");
    expect(onCaptured.mock.calls[0][0]).toBeInstanceOf(Blob);
    unmount();
    expect(stopTrack).toHaveBeenCalled();
  });

  it("disables recording while its parent is uploading", async () => {
    const stream = { getTracks: () => [] } as unknown as MediaStream;
    setCamera(Promise.resolve(stream));
    vi.stubGlobal(
      "MediaRecorder",
      class {
        static isTypeSupported() {
          return false;
        }
      }
    );

    render(<AngleGuide angle={angle} onCaptured={vi.fn()} disabled />);
    const button = await screen.findByRole("button", { name: "Record Front" });
    await waitFor(() => expect(button).toBeDisabled());
    expect(screen.getByText("Uploading…")).toBeInTheDocument();
  });
});
