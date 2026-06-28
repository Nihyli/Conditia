import { describe, expect, it } from "vitest";
import { pageTitle } from "./nav";

describe("nav", () => {
  it("maps paths to page titles", () => {
    expect(pageTitle("/")).toBe("Fleet overview");
    expect(pageTitle("/trucks")).toBe("Trucks");
    expect(pageTitle("/trucks/abc")).toBe("Truck detail");
    expect(pageTitle("/findings")).toBe("Findings");
    expect(pageTitle("/integrations/samsara")).toBe("Samsara integration");
  });
});
