import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Job } from "../../api";
import { ScoreBreakdown } from "./ScoreBreakdown";

const base: Job = { id: "j1", title: "DS", company: "Acme", state: "shortlisted" };

describe("ScoreBreakdown", () => {
  it("muestra 'Por qué N' con razones y knockouts", () => {
    render(
      <ScoreBreakdown
        job={{
          ...base,
          fit_score: 74,
          fit_reasons: ["seniority match: senior", "remoto: sí"],
          knockout_flags: ["pide autorización de trabajo en US"],
        }}
      />,
    );
    expect(screen.getByText(/Por qué 74/)).toBeInTheDocument();
    expect(screen.getByText("seniority match: senior")).toBeInTheDocument();
    expect(screen.getByText("pide autorización de trabajo en US")).toBeInTheDocument();
  });

  it("sin score ni factores no renderiza nada", () => {
    const { container } = render(<ScoreBreakdown job={base} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("con score pero sin factores explica cómo recalcular", () => {
    render(<ScoreBreakdown job={{ ...base, fit_score: 60 }} />);
    expect(screen.getByText(/Por qué 60/)).toBeInTheDocument();
    expect(screen.getByText(/vuelve a correr “Buscar”/)).toBeInTheDocument();
  });
});
