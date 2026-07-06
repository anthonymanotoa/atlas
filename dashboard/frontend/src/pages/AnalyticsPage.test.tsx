import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api, toast } = vi.hoisted(() => ({
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
    analytics: vi.fn(),
    applyRec: vi.fn(),
  },
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock("../api", () => ({ api }));
vi.mock("sonner", async (importOriginal) => ({
  ...(await importOriginal<typeof import("sonner")>()),
  toast,
}));

import { renderRoutes } from "../test/utils";

function analytics(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    funnel: [
      { stage: "discovered", count: 20, rate: null },
      { stage: "applied", count: 10, rate: 0.5 },
      { stage: "responded", count: 3, rate: 0.3 },
    ],
    score_floor: 62,
    by_source: [
      {
        key: "greenhouse",
        applied: 8,
        responded: 2,
        interviews: 1,
        offers: 0,
        response_rate: 0.25,
      },
    ],
    by_ats: [
      {
        key: "greenhouse",
        applied: 8,
        responded: 2,
        interviews: 1,
        offers: 0,
        response_rate: 0.25,
      },
    ],
    by_remote_policy: [
      { key: "remote", applied: 6, responded: 1, interviews: 0, offers: 0, response_rate: 0.167 },
    ],
    by_role_term: [
      {
        key: "data scientist",
        applied: 5,
        responded: 0,
        interviews: 0,
        offers: 0,
        response_rate: 0,
      },
    ],
    response_times: { n: 4, avg_days: 6.2, median_days: 5, p90_days: 12 },
    recommendations: [
      {
        id: "threshold-62",
        text: "Ningún resultado positivo bajo score 62: sube shortlist_threshold.",
        action_type: "set_criteria",
        payload: { field: "shortlist_threshold", value: 62 },
      },
    ],
    ...overrides,
  };
}

function overview(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    overview: {
      total_jobs: 1,
      counts: { shortlisted: 1 },
      funnel: [{ stage: "shortlisted", count: 1 }],
      response_rate: null,
      interview_rate: null,
      applied: 0,
      ready: 0,
      source_health: [],
      ...overrides,
    },
    needs_action: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.profiles.mockResolvedValue({ profiles: [{ id: "owner", label: "Perfil" }], active: "owner" });
  api.onboarding.mockResolvedValue({
    complete: true,
    profile: "owner",
    cv_present: true,
    audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
  });
  api.board.mockResolvedValue({ columns: [], jobs: {}, dismissed: [] });
  api.analytics.mockResolvedValue(analytics());
});

describe("AnalyticsPage", () => {
  it("renderiza el strip de analítica con datos", async () => {
    api.overview.mockResolvedValue(overview());
    renderRoutes("/analytics");
    expect(await screen.findByRole("heading", { name: "Analítica" })).toBeInTheDocument();
  });

  it("sin jobs y funnel vacío muestra EmptyState", async () => {
    api.overview.mockResolvedValue(overview({ total_jobs: 0, counts: {}, funnel: [] }));
    renderRoutes("/analytics");
    expect(await screen.findByText("Sin datos todavía")).toBeInTheDocument();
    expect(screen.getByText("Corre una búsqueda para poblar el embudo.")).toBeInTheDocument();
  });

  it("si /api/overview falla muestra ErrorState y Reintentar recupera al éxito", async () => {
    api.overview.mockRejectedValueOnce(new Error("500"));
    renderRoutes("/analytics");
    expect(await screen.findByText("No se pudo cargar")).toBeInTheDocument();
    const retryBtn = screen.getByRole("button", { name: "Reintentar" });

    api.overview.mockResolvedValueOnce(overview());
    await userEvent.click(retryBtn);

    expect(await screen.findByRole("heading", { name: "Analítica" })).toBeInTheDocument();
    expect(screen.queryByText("No se pudo cargar")).not.toBeInTheDocument();
  });

  it("renderiza las secciones ricas: funnel con tasas, score_floor, conversión y tiempos", async () => {
    api.overview.mockResolvedValue(overview());
    renderRoutes("/analytics");
    expect(await screen.findByText("Embudo con conversión")).toBeInTheDocument();
    // funnel rate vs previa
    expect(screen.getByText(/50% vs previa/)).toBeInTheDocument();
    // score floor empírico
    expect(screen.getByText(/piso de score: 62/)).toBeInTheDocument();
    // conversion_by breakdown (por fuente)
    expect(screen.getByText("Por fuente")).toBeInTheDocument();
    expect(screen.getByText("Por ATS")).toBeInTheDocument();
    expect(screen.getAllByText("greenhouse").length).toBeGreaterThan(0);
    // response times
    expect(screen.getByText("Tiempos de respuesta")).toBeInTheDocument();
    expect(screen.getByText("6.2")).toBeInTheDocument();
  });

  it("aplicar una recomendación llama a useApplyRec", async () => {
    api.overview.mockResolvedValue(overview());
    api.applyRec.mockResolvedValue({ ok: true, applied: "shortlist_threshold=62" });
    renderRoutes("/analytics");
    expect(await screen.findByText(/sube shortlist_threshold/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Aplicar" }));
    await waitFor(() =>
      expect(api.applyRec).toHaveBeenCalledWith(
        expect.objectContaining({ id: "threshold-62", action_type: "set_criteria" }),
      ),
    );
    expect(toast.success).toHaveBeenCalled();
  });
});
