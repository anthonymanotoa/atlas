import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
  },
}));
vi.mock("../api", () => ({ api }));

import { renderRoutes } from "../test/utils";

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
});
