import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createTruck, getTrucks } from "../api";
import { TrucksPage } from "./TrucksPage";

vi.mock("../api", () => ({
  getTrucks: vi.fn(),
  createTruck: vi.fn(),
}));

const mockedGetTrucks = vi.mocked(getTrucks);
const mockedCreateTruck = vi.mocked(createTruck);

describe("TrucksPage", () => {
  beforeEach(() => {
    mockedGetTrucks.mockReset();
    mockedCreateTruck.mockReset();
  });

  it("lists trucks and links to detail and capture", async () => {
    mockedGetTrucks.mockResolvedValue([
      {
        id: "truck-1",
        vin: "1FUJGLDR0CSBT0041",
        make: "Volvo",
        model: "VNL",
        year: 2022,
        license_plate: "ABC123",
      },
    ]);
    render(
      <MemoryRouter>
        <TrucksPage />
      </MemoryRouter>
    );

    expect(await screen.findByText("1FUJGLDR0CSBT0041")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view/i })).toHaveAttribute(
      "href",
      "/trucks/truck-1"
    );
    expect(screen.getByRole("link", { name: /inspect/i })).toHaveAttribute(
      "href",
      "/capture/truck-1"
    );
  });

  it("registers a truck", async () => {
    const user = userEvent.setup();
    mockedGetTrucks.mockResolvedValue([]);
    mockedCreateTruck.mockResolvedValue({
      id: "truck-2",
      vin: "1FUJGLDR0CSBT0042",
      make: null,
      model: null,
      year: null,
      license_plate: null,
    });
    render(
      <MemoryRouter>
        <TrucksPage />
      </MemoryRouter>
    );

    await user.click(await screen.findByRole("button", { name: /register truck/i }));
    await user.type(screen.getByPlaceholderText("1FUJGLDR0CSBT0041"), "1FUJGLDR0CSBT0042");
    await user.click(screen.getByRole("button", { name: /save truck/i }));

    expect(mockedCreateTruck).toHaveBeenCalledWith({
      vin: "1FUJGLDR0CSBT0042",
    });
  });
});
