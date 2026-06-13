import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Action } from "../api";
import { NeedsAction } from "./NeedsAction";

const sample: Action = {
  type: "follow_up",
  priority: 1,
  job_id: "job-1",
  title: "Senior Engineer",
  company: "Acme",
  label: "Follow up",
};

describe("NeedsAction", () => {
  it("renders the empty state when there are no actions", () => {
    render(<NeedsAction actions={[]} onOpen={() => {}} />);
    expect(screen.getByText(/Todo al día/)).toBeInTheDocument();
    expect(screen.queryByText("Acciones para hoy")).not.toBeInTheDocument();
  });

  it("renders a card per action with its label, title and company", () => {
    render(<NeedsAction actions={[sample]} onOpen={() => {}} />);
    expect(screen.getByText("Acciones para hoy")).toBeInTheDocument();
    expect(screen.getByText(sample.title)).toBeInTheDocument();
    expect(screen.getByText(sample.company)).toBeInTheDocument();
    expect(screen.getByText(sample.label)).toBeInTheDocument();
  });

  it("calls onOpen(job_id) when a card is clicked", async () => {
    const onOpen = vi.fn();
    render(<NeedsAction actions={[sample]} onOpen={onOpen} />);
    await userEvent.click(screen.getByText(sample.title));
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen).toHaveBeenCalledWith("job-1");
  });
});
