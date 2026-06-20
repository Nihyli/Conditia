import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { CaptureAngleDiagram } from "./CaptureAngleDiagram";

const RECORD_SECONDS = 12;

export interface AngleSpec {
  key: string;
  label: string;
  hint: string;
}

function pickMime(): string {
  const candidates = [
    "video/mp4",
    "video/webm;codecs=vp9",
    "video/webm;codecs=vp8",
    "video/webm",
  ];
  if (typeof MediaRecorder === "undefined") return "";
  for (const c of candidates) {
    if (MediaRecorder.isTypeSupported(c)) return c;
  }
  return "";
}

export function AngleGuide({
  angle,
  onCaptured,
  disabled,
}: {
  angle: AngleSpec;
  onCaptured: (blob: Blob, ext: string) => void;
  disabled?: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<number | null>(null);

  const [camReady, setCamReady] = useState(false);
  const [camError, setCamError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [remaining, setRemaining] = useState(RECORD_SECONDS);

  function clearTimer() {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  function stopRecording() {
    const r = recorderRef.current;
    if (r && r.state !== "inactive") {
      try {
        r.stop();
      } catch {
        /* ignore */
      }
    }
  }

  // Acquire camera on mount / when the angle changes.
  useEffect(() => {
    let cancelled = false;
    setCamReady(false);
    setRecording(false);
    setRemaining(RECORD_SECONDS);

    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          try {
            await videoRef.current.play();
          } catch {
            /* autoplay may require muted; element is muted */
          }
        }
        setCamReady(true);
        setCamError(null);
      } catch (err) {
        setCamError(err instanceof Error ? err.message : "Camera unavailable");
      }
    }
    start();

    return () => {
      cancelled = true;
      clearTimer();
      stopRecording();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [angle.key]);

  // Auto-stop when the countdown hits zero.
  useEffect(() => {
    if (recording && remaining <= 0) stopRecording();
  }, [recording, remaining]);

  function startRecording() {
    const stream = streamRef.current;
    if (!stream) return;
    const mime = pickMime();
    const recorder = mime
      ? new MediaRecorder(stream, { mimeType: mime })
      : new MediaRecorder(stream);
    chunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.onstop = () => {
      clearTimer();
      setRecording(false);
      const type = recorder.mimeType || "video/webm";
      const ext = type.includes("mp4") ? "mp4" : "webm";
      const blob = new Blob(chunksRef.current, { type });
      onCaptured(blob, ext);
    };

    recorderRef.current = recorder;
    recorder.start();
    setRecording(true);
    setRemaining(RECORD_SECONDS);
    timerRef.current = window.setInterval(() => {
      setRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);
  }

  function onFilePicked(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const ext = file.name.split(".").pop() || "webm";
    onCaptured(file, ext);
  }

  return (
    <div className="capture__stage">
      {camError ? (
        <div className="cam-fallback">
          <p>Camera unavailable on this device.</p>
          <p className="muted">{camError}</p>
          <label className="primary-btn" style={{ marginTop: 16 }}>
            Upload a clip instead
            <input
              type="file"
              accept="video/*,image/*"
              capture="environment"
              onChange={onFilePicked}
              hidden
            />
          </label>
        </div>
      ) : (
        <video
          ref={videoRef}
          className="capture__video"
          autoPlay
          muted
          playsInline
        />
      )}

      <div className="capture__overlay">
        <CaptureAngleDiagram angle={angle.key} />
        <p className="capture__hint">{angle.hint}</p>
      </div>

      {!camError && (
        <div className="capture__controls">
          {recording ? (
            <button
              className="record-btn is-recording"
              onClick={stopRecording}
              aria-label="Stop recording"
            >
              <span className="record-btn__count">{remaining}</span>
            </button>
          ) : (
            <button
              className="record-btn"
              onClick={startRecording}
              disabled={!camReady || disabled}
              aria-label={`Record ${angle.label}`}
            />
          )}
          <p className="capture__controls-label">
            {recording
              ? "Recording — tap to stop"
              : disabled
                ? "Uploading…"
                : `Tap to film the ${angle.label.toLowerCase()} (12s)`}
          </p>
        </div>
      )}
    </div>
  );
}
