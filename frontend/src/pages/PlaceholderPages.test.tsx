import { render, screen } from "@testing-library/react";
import { SettingsPage } from "./SettingsPage";
import { SamsaraPage } from "./SamsaraPage";

describe("placeholder pages", () => {
  it("explains settings are not configured", () => {
    render(<SettingsPage />);
    expect(screen.getByText("Not configured yet")).toBeInTheDocument();
    expect(screen.getByText(/user accounts, roles/i)).toBeInTheDocument();
  });

  it("explains samsara is not configured", () => {
    render(<SamsaraPage />);
    expect(screen.getByText("Not configured yet")).toBeInTheDocument();
    expect(screen.getByText(/telematics integration with samsara/i)).toBeInTheDocument();
  });
});
