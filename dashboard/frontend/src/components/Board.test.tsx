import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Job } from "../api";
import { Board } from "./Board";

const job: Job = {
  id: "j1",
  title: "Data Scientist",
  company: "Acme",
  state: "shortlisted",
  fit_score: 80,
  is_remote: 1,
};

describe("Board cards", () => {
  it("opens a job when the card is clicked", async () => {
    const onOpen = vi.fn();
    render(
      <Board
        columns={["shortlisted"]}
        jobs={{ shortlisted: [job] }}
        onOpen={onOpen}
        onMove={() => {}}
      />,
    );
    await userEvent.click(screen.getByText("Data Scientist"));
    expect(onOpen).toHaveBeenCalledWith("j1");
  });

  it("the discard button dismisses the card (with its source column)", async () => {
    const onDismiss = vi.fn();
    render(
      <Board
        columns={["shortlisted"]}
        jobs={{ shortlisted: [job] }}
        onOpen={() => {}}
        onMove={() => {}}
        onDismiss={onDismiss}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Descartar" }));
    expect(onDismiss).toHaveBeenCalledWith("j1", "shortlisted");
  });

  it("shows no discard button when onDismiss is not provided", () => {
    render(
      <Board
        columns={["shortlisted"]}
        jobs={{ shortlisted: [job] }}
        onOpen={() => {}}
        onMove={() => {}}
      />,
    );
    expect(screen.queryByRole("button", { name: "Descartar" })).not.toBeInTheDocument();
  });

  it("renders the geo + repost chips on the card when the job is restricted", () => {
    render(
      <Board
        columns={["shortlisted"]}
        jobs={{ shortlisted: [{ ...job, geo_scope: "us", repost_count: 2 }] }}
        onOpen={() => {}}
        onMove={() => {}}
      />,
    );
    expect(screen.getByText("us")).toBeInTheDocument();
    expect(screen.getByText("repost")).toBeInTheDocument();
  });
});
