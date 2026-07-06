import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { UpskillReport } from "../api";
import { renderWithQuery } from "../test/utils";
import { UpskillView } from "./UpskillView";

// La vista SOLO lee el reporte que el brain produjo; IntentConfirmDialog consume el módulo api,
// así que lo mockeamos entero. Ningún LLM en juego ($0) — la web solo renderiza + encola.
const { api } = vi.hoisted(() => ({ api: { enqueueIntent: vi.fn() } }));
vi.mock("../api", () => ({ api }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const REPORT: UpskillReport = {
  id: 3,
  report_md:
    "# Plan de upskilling\n\n## Tooling\n### Kubernetes (Crítico)\n- Empieza por los conceptos\nUn párrafo suelto.",
  heatmap: [
    { skill: "Kubernetes", severity: "Critical", note: "gate en 4 vacantes" },
    { skill: "Go", severity: "Medium", note: "adyacente a tu Python" },
  ],
  hard_gaps: { skills: [{ skill: "kubernetes", score: 0.7, occurrences: 1 }] },
  created_at: "2026-07-06T10:30:00",
};

describe("UpskillView", () => {
  it("muestra el estado vacío cuando no hay reporte", () => {
    renderWithQuery(<UpskillView report={null} />);
    expect(screen.getByText(/Aún no hay reporte/)).toBeInTheDocument();
    // el botón de recalcular sigue disponible en el header para pedir el primero
    expect(screen.getByRole("button", { name: /Recalcular gaps/ })).toBeInTheDocument();
  });

  it("renderiza el heatmap con chips por severidad (etiquetas en español)", () => {
    renderWithQuery(<UpskillView report={REPORT} />);
    expect(screen.getByText(/Kubernetes · Crítico/)).toBeInTheDocument();
    expect(screen.getByText(/Go · Medio/)).toBeInTheDocument();
    expect(screen.getByText("Heatmap")).toBeInTheDocument();
  });

  it("renderiza el markdown del plan (títulos, listas, párrafos)", () => {
    renderWithQuery(<UpskillView report={REPORT} />);
    expect(screen.getByRole("heading", { name: "Plan de upskilling" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tooling" })).toBeInTheDocument();
    expect(screen.getByText(/Empieza por los conceptos/)).toBeInTheDocument();
    expect(screen.getByText("Un párrafo suelto.")).toBeInTheDocument();
  });

  it("muestra un vacío del heatmap cuando el reporte no marcó skills", () => {
    renderWithQuery(<UpskillView report={{ ...REPORT, heatmap: [] }} />);
    expect(screen.getByText("Sin skills marcadas.")).toBeInTheDocument();
  });
});
