import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CvReview } from "../api";
import { renderWithQuery } from "../test/utils";
import { CvReviewPanel } from "./CvReviewPanel";

// La web SOLO lee la revisión que el brain produjo y dispara acciones deterministas; mockeamos
// el módulo api entero (los hooks + IntentConfirmDialog lo consumen). Ningún LLM en juego.
const { api } = vi.hoisted(() => ({
  api: {
    cvReviews: vi.fn(),
    applyCvReviewEdit: vi.fn(),
    resolveCvReviewFlag: vi.fn(),
    enqueueIntent: vi.fn(),
  },
}));
vi.mock("../api", () => ({ api }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const REVIEW: CvReview = {
  id: 7,
  job_id: "j1",
  cv_version_id: null,
  edits: [
    {
      file: "cv",
      old_string: "Data Scientist",
      new_string: "Lead Data Scientist",
      reason: "mirror the posting title",
    },
  ],
  critique: {
    missed_keywords: ["sql: súbelo al summary"],
    company_angles: ["Acme publica su stack — cita dbt"],
    reframing: ["el bullet de ETL puede enmarcarse hacia analytics"],
    tone_register: ["nada que señalar"],
  },
  flags: [
    {
      file: "cv",
      bullet: "Led the ETL redesign",
      classification: "Flag",
      reason: "¿lo lideraste tú o participaste?",
      softened: "Contributed to the ETL redesign",
    },
  ],
  created_at: "2026-07-06T09:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  api.cvReviews.mockResolvedValue({ reviews: [REVIEW] });
  api.applyCvReviewEdit.mockResolvedValue({ ok: true, applied_ref: "cv_version:2" });
  api.resolveCvReviewFlag.mockResolvedValue({ ok: true, resolution: "drop" });
  api.enqueueIntent.mockResolvedValue({ ok: true, id: "in_new" });
});

describe("CvReviewPanel", () => {
  it("renderiza la crítica (4 categorías), los edits y los flags", async () => {
    renderWithQuery(<CvReviewPanel jobId="j1" />);
    // Las cuatro categorías obligatorias de la crítica.
    expect(await screen.findByText("Keywords desaprovechados")).toBeInTheDocument();
    expect(screen.getByText("Ángulos específicos de la empresa")).toBeInTheDocument();
    expect(screen.getByText("Reframing accionable")).toBeInTheDocument();
    expect(screen.getByText("Tono y registro")).toBeInTheDocument();
    // Contenido de la crítica + edit propuesto + flag.
    expect(screen.getByText("sql: súbelo al summary")).toBeInTheDocument();
    expect(screen.getByText("Lead Data Scientist")).toBeInTheDocument();
    expect(screen.getByText("Led the ETL redesign")).toBeInTheDocument();
  });

  it("muestra el mensaje vacío cuando no hay revisiones", async () => {
    api.cvReviews.mockResolvedValue({ reviews: [] });
    renderWithQuery(<CvReviewPanel jobId="j1" />);
    expect(await screen.findByText(/Sin revisiones todavía/)).toBeInTheDocument();
  });

  it("aplicar un edit llama al endpoint con el índice", async () => {
    renderWithQuery(<CvReviewPanel jobId="j1" />);
    const applyBtn = await screen.findByRole("button", { name: /aplicar/i });
    await userEvent.click(applyBtn);
    await waitFor(() => expect(api.applyCvReviewEdit).toHaveBeenCalledWith(7, 0));
  });

  it("resolver un flag como 'eliminar' llama al endpoint con drop", async () => {
    renderWithQuery(<CvReviewPanel jobId="j1" />);
    const dropBtn = await screen.findByRole("button", { name: /eliminar/i });
    await userEvent.click(dropBtn);
    await waitFor(() => expect(api.resolveCvReviewFlag).toHaveBeenCalledWith(7, 0, "drop"));
  });

  it("resolver un flag como 'mantener' llama al endpoint con keep", async () => {
    renderWithQuery(<CvReviewPanel jobId="j1" />);
    const keepBtn = await screen.findByRole("button", { name: /mantener/i });
    await userEvent.click(keepBtn);
    await waitFor(() => expect(api.resolveCvReviewFlag).toHaveBeenCalledWith(7, 0, "keep"));
  });

  it("resolver un flag como 'suavizar' llama al endpoint con soften", async () => {
    renderWithQuery(<CvReviewPanel jobId="j1" />);
    const softenBtn = await screen.findByRole("button", { name: /suavizar/i });
    await userEvent.click(softenBtn);
    await waitFor(() => expect(api.resolveCvReviewFlag).toHaveBeenCalledWith(7, 0, "soften"));
  });

  it("no muestra acciones de flag una vez resuelto", async () => {
    api.cvReviews.mockResolvedValue({
      reviews: [{ ...REVIEW, flags: [{ ...REVIEW.flags[0], resolution: "drop" as const }] }],
    });
    renderWithQuery(<CvReviewPanel jobId="j1" />);
    expect(await screen.findByText(/Resuelto: drop/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^mantener$/i })).not.toBeInTheDocument();
  });
});
