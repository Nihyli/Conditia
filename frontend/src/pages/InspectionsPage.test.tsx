import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getInspections } from "../api";
import { apiInspection } from "../test/fixtures";
import { InspectionsPage } from "./InspectionsPage";

vi.mock("../api", () => ({
  getInspections: vi.fn(),
}));

const mockedGetInspections = vi.mocked(getInspections);

describe("InspectionsPage", () => {
  beforeEach(() => {
    mockedGetInspections.mockReset();
  });

  it("lists inspections with links to detail", async () => {
    mockedGetInspections.mockResolvedValue([apiInspection()]);
    render(
      <MemoryRouter>
        <InspectionsPage />
      </MemoryRouter>
    );

    expect(await screen.findByText("TRK-001")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /TRK-001/i })).toHaveAttribute(
      "href",
      "/inspections/inspection-1"
    );
  });
});
