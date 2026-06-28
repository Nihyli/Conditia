import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createInspection,
  createTruck,
  finalizeInspection,
  getTrucks,
  uploadMedia,
} from "../api";
import { CapturePage } from "./CapturePage";

vi.mock("../api", () => ({
  API_BASE: "/api",
  createInspection: vi.fn(),
  createTruck: vi.fn(),
  finalizeInspection: vi.fn(),
  getTrucks: vi.fn(),
  uploadMedia: vi.fn(),
}));

vi.mock("../components/capture/AngleGuide", () => ({
  AngleGuide: ({ angle, onCaptured, disabled }: {
    angle: { label: string };
    onCaptured: (blob: Blob, ext: string) => void;
    disabled?: boolean;
  }) => (
    <button
      disabled={disabled}
      onClick={() => onCaptured(new Blob(["clip"]), "webm")}
    >
      Capture {angle.label}
    </button>
  ),
}));

const mockedGetTrucks = vi.mocked(getTrucks);
const mockedCreateTruck = vi.mocked(createTruck);
const mockedCreateInspection = vi.mocked(createInspection);
const mockedUpload = vi.mocked(uploadMedia);
const mockedFinalize = vi.mocked(finalizeInspection);

function renderCapture(path = "/capture") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/capture" element={<CapturePage />} />
        <Route path="/capture/:truckId" element={<CapturePage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("CapturePage", () => {
  beforeEach(() => {
    mockedGetTrucks.mockReset();
    mockedCreateTruck.mockReset();
    mockedCreateInspection.mockReset();
    mockedUpload.mockReset();
    mockedFinalize.mockReset();
    mockedUpload.mockResolvedValue(undefined);
  });

  it("registers the first truck", async () => {
    const user = userEvent.setup();
    mockedGetTrucks.mockResolvedValueOnce([]).mockResolvedValueOnce([
      {
        id: "truck-1",
        vin: "1FUJGLDR0CSBT0041",
        make: "Volvo",
        model: "VNL",
        year: 2024,
        license_plate: "TRK-001",
      },
    ]);
    mockedCreateTruck.mockResolvedValue({
      id: "truck-1",
      vin: "1FUJGLDR0CSBT0041",
      make: "Volvo",
      model: "VNL",
      year: 2024,
      license_plate: "TRK-001",
    });
    renderCapture();

    await screen.findByText(/No trucks in the fleet/);
    await user.type(screen.getByLabelText(/VIN \(required\)/i), "1FUJGLDR0CSBT0041");
    await user.type(screen.getByLabelText("Make"), "Volvo");
    await user.click(screen.getByRole("button", { name: "Register truck" }));

    await waitFor(() => expect(mockedCreateTruck).toHaveBeenCalled());
    expect(mockedCreateTruck.mock.calls[0][0].vin).toBe("1FUJGLDR0CSBT0041");
  });

  it("captures all angles and finalizes exactly once", async () => {
    const user = userEvent.setup();
    mockedGetTrucks.mockResolvedValue([
      {
        id: "truck-1",
        vin: "1FUJGLDR0CSBT0041",
        make: "Volvo",
        model: "VNL",
        year: 2024,
        license_plate: "TRK-001",
      },
    ]);
    mockedCreateInspection.mockResolvedValue({
      id: "inspection-1",
      truck_id: "truck-1",
      status: "uploading",
      capture_source: "mobile",
    });
    mockedFinalize.mockResolvedValue({
      id: "inspection-1",
      truck_id: "truck-1",
      status: "submitted",
      capture_source: "mobile",
    });
    renderCapture("/capture/truck-1");

    await user.click(await screen.findByRole("button", { name: "Start inspection" }));
    for (const label of [
      "Front",
      "Driver side",
      "Rear",
      "Passenger side",
      "Top",
      "Undercarriage",
    ]) {
      await user.click(await screen.findByRole("button", { name: `Capture ${label}` }));
    }

    expect(await screen.findByText("Analysis queued")).toBeInTheDocument();
    expect(mockedUpload).toHaveBeenCalledTimes(6);
    expect(mockedFinalize).toHaveBeenCalledOnce();
  });

  it("shows truck-loading failures and retries", async () => {
    const user = userEvent.setup();
    mockedGetTrucks
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce([]);
    renderCapture();

    expect(await screen.findByText(/Can’t reach the Conditia API/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/No trucks in the fleet/)).toBeInTheDocument();
  });

  it("shows a loading state while trucks are fetched", () => {
    mockedGetTrucks.mockReturnValue(new Promise(() => {}));
    renderCapture();

    expect(screen.getByText(/loading trucks/i)).toBeInTheDocument();
  });

  it("starts an inspection for an existing truck", async () => {
    const user = userEvent.setup();
    mockedGetTrucks.mockResolvedValue([
      {
        id: "truck-1",
        vin: "1FUJGLDR0CSBT0041",
        make: "Volvo",
        model: "VNL",
        year: 2024,
        license_plate: "TRK-001",
      },
      {
        id: "truck-2",
        vin: "2FUJGLDR0CSBT0042",
        make: null,
        model: null,
        year: null,
        license_plate: null,
      },
    ]);
    mockedCreateInspection.mockResolvedValue({
      id: "inspection-1",
      truck_id: "truck-2",
      status: "uploading",
      capture_source: "mobile",
    });
    renderCapture();

    await user.selectOptions(await screen.findByLabelText(/truck/i), "truck-2");
    await user.click(screen.getByRole("button", { name: "Start inspection" }));

    expect(mockedCreateInspection).toHaveBeenCalledWith("truck-2");
    expect(await screen.findByText("Front")).toBeInTheDocument();
  });

  it("requires a VIN before registering a truck", async () => {
    const user = userEvent.setup();
    mockedGetTrucks.mockResolvedValue([]);
    renderCapture();

    await screen.findByText(/No trucks in the fleet/);
    await user.click(screen.getByRole("button", { name: "Register truck" }));

    expect(await screen.findByText("VIN is required")).toBeInTheDocument();
    expect(mockedCreateTruck).not.toHaveBeenCalled();
  });

  it("shows registration failures from the API", async () => {
    const user = userEvent.setup();
    mockedGetTrucks.mockResolvedValue([]);
    mockedCreateTruck.mockRejectedValue(new Error("duplicate VIN"));
    renderCapture();

    await screen.findByText(/No trucks in the fleet/);
    await user.type(screen.getByLabelText(/VIN \(required\)/i), "1FUJGLDR0CSBT0041");
    await user.click(screen.getByRole("button", { name: "Register truck" }));

    expect(await screen.findByText("duplicate VIN")).toBeInTheDocument();
  });

  it("allows skipping an angle after an upload error", async () => {
    const user = userEvent.setup();
    mockedGetTrucks.mockResolvedValue([
      {
        id: "truck-1",
        vin: "1FUJGLDR0CSBT0041",
        make: "Volvo",
        model: "VNL",
        year: 2024,
        license_plate: "TRK-001",
      },
    ]);
    mockedCreateInspection.mockResolvedValue({
      id: "inspection-1",
      truck_id: "truck-1",
      status: "uploading",
      capture_source: "mobile",
    });
    mockedUpload
      .mockRejectedValueOnce(new Error("upload failed"))
      .mockResolvedValue(undefined);
    renderCapture("/capture/truck-1");

    await user.click(await screen.findByRole("button", { name: "Start inspection" }));
    await user.click(await screen.findByRole("button", { name: "Capture Front" }));

    expect(await screen.findByText("upload failed")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Skip" }));
    expect(await screen.findByText("Driver side")).toBeInTheDocument();
  });
});
