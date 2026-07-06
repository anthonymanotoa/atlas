import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
    setState: vi.fn(),
    job: vi.fn(),
  },
}));
vi.mock("../api", () => ({ api }));

import { renderRoutes } from "../test/utils";

const job = {
  id: "j1",
  title: "Data Scientist",
  company: "Acme",
  state: "shortlisted",
  fit_score: 80,
  is_remote: 1,
};

beforeEach(() => {
  vi.clearAllMocks();
  api.profiles.mockResolvedValue({ profiles: [{ id: "owner", label: "Perfil" }], active: "owner" });
  api.onboarding.mockResolvedValue({
    complete: true,
    profile: "owner",
    cv_present: true,
    audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
  });
  api.overview.mockResolvedValue({
    overview: {
      total_jobs: 1,
      counts: { shortlisted: 1 },
      funnel: [],
      response_rate: null,
      interview_rate: null,
      applied: 0,
      ready: 0,
      source_health: [],
    },
    needs_action: [],
  });
  api.board.mockResolvedValue({
    columns: ["shortlisted"],
    jobs: { shortlisted: [job] },
    dismissed: [],
  });
  api.setState.mockResolvedValue({ ok: true });
});

describe("PipelinePage", () => {
  it("renderiza el tablero con la vacante", async () => {
    renderRoutes("/pipeline");
    expect(await screen.findByText("Data Scientist")).toBeInTheDocument();
    expect(screen.getByText("Preseleccionados")).toBeInTheDocument();
  });

  it("descartar una card llama setState('dismissed')", async () => {
    renderRoutes("/pipeline");
    await screen.findByText("Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: "Descartar" }));
    expect(api.setState).toHaveBeenCalledWith("j1", "dismissed");
  });

  it("las descartadas se listan y se pueden restaurar", async () => {
    api.board.mockResolvedValue({
      columns: ["shortlisted"],
      jobs: { shortlisted: [] },
      dismissed: [job],
    });
    renderRoutes("/pipeline");
    await userEvent.click(await screen.findByText(/Descartadas \(1\)/));
    await userEvent.click(screen.getByRole("button", { name: /Restaurar/ }));
    expect(api.setState).toHaveBeenCalledWith("j1", "shortlisted");
  });

  it("si /api/board falla muestra ErrorState accionable", async () => {
    api.board.mockRejectedValue(new Error("500"));
    renderRoutes("/pipeline");
    expect(await screen.findByText("No se pudo cargar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
