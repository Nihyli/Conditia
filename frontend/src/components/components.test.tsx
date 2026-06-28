import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { DamageMap } from "./DamageMap";
import { InspectionMediaViewer } from "./InspectionMediaViewer";
import { RecentInspections } from "./RecentInspections";
import { Sidebar } from "./Sidebar";
import { StatCards } from "./StatCards";
import { Topbar } from "./Topbar";
import { CaptureAngleDiagram } from "./capture/CaptureAngleDiagram";
import { finding, inspection, photo, video } from "../test/fixtures";

describe("shared dashboard components", () => {
  it("renders stat trends and falls back to the truck icon", () => {
    render(
      <StatCards
        stats={[
          { id: "a", label: "Active", value: "2", icon: "unknown", trendLabel: "+1", trendKind: "up" },
          { id: "b", label: "Open", value: "1", icon: "alert", trendLabel: "-1", trendKind: "down" },
          { id: "c", label: "Pending", value: "0", icon: "clock", trendLabel: "Stable", trendKind: "neutral" },
        ]}
      />
    );

    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getByText("Stable")).toBeInTheDocument();
  });

  it("navigates the sidebar with router links and displays an active-truck badge", () => {
    render(
      <MemoryRouter>
        <Sidebar trucksBadge={3} />
      </MemoryRouter>
    );

    expect(screen.getByRole("link", { name: /fleet overview/i })).toHaveAttribute(
      "href",
      "/"
    );
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /trucks/i })).toHaveAttribute(
      "href",
      "/trucks"
    );
    expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute(
      "href",
      "/settings"
    );
  });

  it("renders the topbar route and disables unfinished controls", () => {
    render(
      <MemoryRouter>
        <Topbar title="Fleet overview" />
      </MemoryRouter>
    );

    expect(screen.getByRole("link", { name: /new inspection/i })).toHaveAttribute(
      "href",
      "/capture"
    );
    expect(screen.getByRole("button", { name: /notifications/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /account/i })).toBeDisabled();
  });
});

describe("inspection components", () => {
  it("orders media by angle and switches from an image to a video", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <InspectionMediaViewer media={[video, photo]} />
    );

    expect(screen.getByText("2 clips")).toBeInTheDocument();
    expect(container.querySelector(".media-viewer__stage img")).toHaveAttribute(
      "src",
      "/api/inspection-media/media-photo/content"
    );
    await user.click(screen.getByRole("button", { name: /rear/i }));
    expect(container.querySelector(".media-viewer__stage video")).toHaveAttribute(
      "src",
      "/api/inspection-media/media-video/content"
    );
  });

  it("shows a concise empty-media state", () => {
    render(<InspectionMediaViewer media={[]} />);
    expect(
      screen.getByText("No photos or videos are attached to this inspection.")
    ).toBeInTheDocument();
  });

  it("selects recent inspections and marks the worst severity", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const critical = {
      ...finding,
      id: "critical",
      severity: "critical" as const,
    };
    render(
      <RecentInspections
        inspections={[
          inspection({ id: "one", findings: [finding, critical] }),
          inspection({ id: "two", truckLabel: "TRK-002", findings: [] }),
        ]}
        activeId="one"
        onSelect={onSelect}
      />
    );

    expect(screen.getByLabelText("critical")).toBeInTheDocument();
    expect(screen.getByLabelText("clear")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /TRK-002/i }));
    expect(onSelect).toHaveBeenCalledWith("two");
  });

  it("sorts findings, explains change history, and shows review state", () => {
    const previous = {
      ...finding,
      id: "old",
      title: "Old crack",
      severity: "critical" as const,
      firstDetectedInspectionsAgo: 2,
    };
    const { rerender } = render(
      <DamageMap inspection={inspection({ findings: [finding, previous], media: [] })} />
    );

    expect(screen.getByText("Old crack")).toBeInTheDocument();
    expect(screen.getByText(/New — first detected/)).toBeInTheDocument();
    expect(screen.getByText(/2 inspections ago/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /export pdf/i })).toBeDisabled();

    rerender(
      <DamageMap
        inspection={inspection({ findings: [], media: [], status: "review_required" })}
      />
    );
    expect(screen.getByText("Manual review required")).toBeInTheDocument();
    expect(screen.getByText(/not a clear result/i)).toBeInTheDocument();
  });

  it.each(["front", "rear", "driver_side", "passenger_side", "top", "undercarriage"])(
    "renders the %s capture diagram",
    (angle) => {
      render(<CaptureAngleDiagram angle={angle} />);
      expect(screen.getByRole("img", { name: `Filming angle: ${angle}` })).toBeInTheDocument();
    }
  );
});
