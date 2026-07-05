import { screen, waitFor } from "@testing-library/react";
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

const onboardingDone = {
  complete: true,
  profile: "owner",
  cv_present: true,
  audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
};
const emptyOverview = {
  overview: {
    total_jobs: 0,
    counts: {},
    funnel: [],
    response_rate: null,
    interview_rate: null,
    applied: 0,
    ready: 0,
    source_health: [],
  },
  needs_action: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  api.profiles.mockResolvedValue({ profiles: [{ id: "owner", label: "Perfil" }], active: "owner" });
  api.onboarding.mockResolvedValue(onboardingDone);
  api.overview.mockResolvedValue(emptyOverview);
  api.board.mockResolvedValue({
    columns: ["shortlisted"],
    jobs: { shortlisted: [] },
    dismissed: [],
  });
});

describe("AppShell + router", () => {
  it("/ redirige a /pipeline y muestra la navegación", async () => {
    renderRoutes("/");
    expect(await screen.findByRole("link", { name: /Pipeline/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Analítica/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Portafolio/ })).toBeInTheDocument();
    // contenido del pipeline (empty state del NeedsAction)
    expect(await screen.findByText(/Todo al día/)).toBeInTheDocument();
  });

  it("con onboarding incompleto redirige a /onboarding", async () => {
    api.onboarding.mockResolvedValue({ ...onboardingDone, complete: false });
    renderRoutes("/pipeline");
    expect(await screen.findByText(/Primer paso: adapta tu CV/)).toBeInTheDocument();
    await waitFor(() => expect(api.board).not.toHaveBeenCalled());
  });

  it("una ruta desconocida cae en /pipeline", async () => {
    renderRoutes("/no-existe");
    expect(await screen.findByText(/Todo al día/)).toBeInTheDocument();
  });
});
