import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api, toast } = vi.hoisted(() => ({
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
    followups: vi.fn(),
    markFollowupSent: vi.fn(),
  },
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock("../api", () => ({ api }));
vi.mock("sonner", async (importOriginal) => ({
  ...(await importOriginal<typeof import("sonner")>()),
  toast,
}));

import { renderRoutes } from "../test/utils";

function buckets(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    buckets: {
      urgent: [
        {
          id: 1,
          job_id: "j1",
          title: "Data Scientist",
          company: "Acme Robotics",
          kind: "applied",
          touch_number: 1,
          due_at: "2026-07-01T00:00:00+00:00",
          days_overdue: 2.5,
          draft: { subject: "Seguimiento", body: "Hola equipo de Acme…" },
        },
      ],
      overdue: [],
      waiting: [],
      cold: [
        {
          job_id: "j9",
          title: "ML Engineer",
          company: "Globex",
          touches_done: 2,
          touches_pending: 0,
        },
      ],
      ...overrides,
    },
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
  api.overview.mockResolvedValue({
    overview: {
      total_jobs: 1,
      counts: {},
      funnel: [],
      response_rate: null,
      interview_rate: null,
      applied: 0,
      ready: 0,
      source_health: [],
    },
    needs_action: [],
  });
  api.board.mockResolvedValue({ columns: [], jobs: {}, dismissed: [] });
});

describe("FollowupsPage", () => {
  it("renderiza los buckets con el borrador de cada toque", async () => {
    api.followups.mockResolvedValue(buckets());
    renderRoutes("/followups");
    expect(await screen.findByRole("heading", { name: "Follow-ups" })).toBeInTheDocument();
    expect(await screen.findByText("Data Scientist")).toBeInTheDocument();
    expect(screen.getByText("Acme Robotics")).toBeInTheDocument();
    expect(screen.getByText(/Hola equipo de Acme/)).toBeInTheDocument();
    // bucket urgent + cold visibles
    expect(screen.getByText("Urgentes")).toBeInTheDocument();
    expect(screen.getByText("Frías")).toBeInTheDocument();
    expect(screen.getByText("ML Engineer")).toBeInTheDocument();
  });

  it("marcar enviado confirma en dos pasos y llama a la mutación", async () => {
    const user = userEvent.setup();
    api.followups.mockResolvedValue(buckets());
    api.markFollowupSent.mockResolvedValue({ ok: true, next_id: 2 });
    renderRoutes("/followups");
    await screen.findByText("Data Scientist");

    // Primer clic: arma la confirmación (no llama a la API todavía).
    await user.click(screen.getByRole("button", { name: /Marcar enviado/ }));
    expect(api.markFollowupSent).not.toHaveBeenCalled();

    // Segundo clic: confirma y dispara la mutación.
    await user.click(screen.getByRole("button", { name: /Confirmar envío/ }));
    await waitFor(() => expect(api.markFollowupSent).toHaveBeenCalledWith(1, true));
    expect(toast.success).toHaveBeenCalled();
  });

  it("sin toques ni frías muestra EmptyState", async () => {
    api.followups.mockResolvedValue(buckets({ urgent: [], overdue: [], waiting: [], cold: [] }));
    renderRoutes("/followups");
    expect(await screen.findByText("Sin follow-ups pendientes")).toBeInTheDocument();
  });

  it("si /api/followups falla muestra ErrorState y Reintentar recupera al éxito", async () => {
    api.followups.mockRejectedValueOnce(new Error("500"));
    renderRoutes("/followups");
    expect(await screen.findByText("No se pudo cargar")).toBeInTheDocument();

    api.followups.mockResolvedValueOnce(buckets());
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Data Scientist")).toBeInTheDocument();
  });
});
