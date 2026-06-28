import { describe, expect, it } from "vitest";
import { finding } from "../test/fixtures";
import {
  resolveSilhouetteZone,
  silhouetteSeverity,
} from "./truckSilhouetteZones";

describe("truckSilhouetteZones", () => {
  it("maps vehicle front and cab findings onto the cab region", () => {
    expect(resolveSilhouetteZone("front")).toBe("cab");
    expect(resolveSilhouetteZone("cab")).toBe("cab");
  });

  it("maps trailer and side findings onto trailer regions", () => {
    expect(resolveSilhouetteZone("trailer_rear")).toBe("trailer_rear");
    expect(resolveSilhouetteZone("trailer_mid")).toBe("trailer_mid");
    expect(resolveSilhouetteZone("trailer_front")).toBe("trailer_front");
    expect(resolveSilhouetteZone("driver_side")).toBe("trailer_mid");
    expect(resolveSilhouetteZone("passenger_side")).toBe("trailer_mid");
  });

  it("ignores unknown zones on the map", () => {
    expect(resolveSilhouetteZone("unknown")).toBeNull();
  });

  it("picks the worst severity per silhouette region", () => {
    const findings = [
      { ...finding, zone: "front" as const, severity: "medium" as const },
      {
        ...finding,
        id: "cab-low",
        zone: "cab" as const,
        severity: "low" as const,
      },
      {
        ...finding,
        id: "rear-crit",
        zone: "trailer_rear" as const,
        severity: "critical" as const,
      },
    ];

    expect(silhouetteSeverity(findings, "cab")).toBe("medium");
    expect(silhouetteSeverity(findings, "trailer_rear")).toBe("critical");
    expect(silhouetteSeverity(findings, "trailer_mid")).toBeNull();
  });
});
