import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SamsaraPage } from "./SamsaraPage";

describe("placeholder pages", () => {
  it("explains samsara is not configured", () => {
    render(<SamsaraPage />);
    expect(screen.getByText("Not configured yet")).toBeInTheDocument();
    expect(screen.getByText(/telematics integration with samsara/i)).toBeInTheDocument();
  });
});
