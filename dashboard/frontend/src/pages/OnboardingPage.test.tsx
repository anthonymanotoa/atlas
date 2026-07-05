import { screen } from "@testing-library/react";
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

beforeEach(() => {
  vi.clearAllMocks();
  api.profiles.mockResolvedValue({ profiles: [{ id: "owner", label: "Perfil" }], active: "owner" });
  api.onboarding.mockResolvedValue({
    complete: false,
    profile: "owner",
    cv_present: true,
    audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
  });
  api.overview.mockResolvedValue({
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
  });
  api.board.mockResolvedValue({ columns: [], jobs: {}, dismissed: [] });
});

describe("OnboardingPage", () => {
  it("renderiza el gate de onboarding con datos", async () => {
    renderRoutes("/onboarding");
    expect(await screen.findByText("Primer paso: adapta tu CV y tu LinkedIn")).toBeInTheDocument();
  });
});
