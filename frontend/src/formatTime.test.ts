import { afterEach, describe, expect, it, vi } from "vitest";
import { formatCapturedAt } from "./formatTime";

describe("formatCapturedAt", () => {
  afterEach(() => vi.useRealTimers());

  it.each([
    [30_000, "just now"],
    [15 * 60_000, "15 min ago"],
    [2 * 60 * 60_000 + 5 * 60_000, "2h 5m ago"],
  ])("formats a timestamp %i milliseconds ago", (elapsed, expected) => {
    const now = new Date("2026-06-21T18:00:00Z");
    vi.useFakeTimers();
    vi.setSystemTime(now);

    const result = formatCapturedAt(
      new Date(now.getTime() - elapsed).toISOString()
    );

    expect(result.relativeLabel).toBe(expected);
    expect(result.capturedAtLabel).toContain("Today");
  });

  it("labels yesterday and older dates", () => {
    const now = new Date("2026-06-21T18:00:00Z");
    vi.useFakeTimers();
    vi.setSystemTime(now);

    const yesterday = formatCapturedAt(
      new Date(now.getTime() - 26 * 60 * 60_000).toISOString()
    );
    const older = formatCapturedAt("2026-06-01T12:00:00Z");

    expect(yesterday.relativeLabel).toBe("yesterday");
    expect(yesterday.capturedAtLabel).toContain("Yesterday");
    expect(older.relativeLabel).not.toContain("ago");
    expect(older.capturedAtLabel).toBeTruthy();
  });
});
