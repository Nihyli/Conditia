import type { Severity } from "./types";

export const severityRank: Record<Severity, number> = {
  critical: 3,
  medium: 2,
  low: 1,
  clear: 0,
};

export const severityColor: Record<Severity, string> = {
  critical: "var(--crit)",
  medium: "var(--med)",
  low: "var(--low)",
  clear: "var(--clear)",
};

export const severityFill: Record<Severity, string> = {
  critical: "var(--crit-bg)",
  medium: "var(--med-bg)",
  low: "var(--low-bg)",
  clear: "var(--clear-bg)",
};

export const severityLabel: Record<Severity, string> = {
  critical: "Critical",
  medium: "Medium",
  low: "Low",
  clear: "Clear",
};

export const severityClass: Record<Severity, string> = {
  critical: "crit",
  medium: "medium",
  low: "low",
  clear: "clear",
};

export function parseSeverity(raw: string): Severity {
  if (raw === "high") return "critical";
  if (raw === "critical" || raw === "medium" || raw === "low" || raw === "clear") {
    return raw;
  }
  throw new Error(`Unsupported severity: ${raw}`);
}
