import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
    criteria: vi.fn(),
    saveCriteria: vi.fn(),
    renameProfile: vi.fn(),
    completeOnboarding: vi.fn(),
    importCv: vi.fn(),
    cvAudit: vi.fn(),
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
  api.criteria.mockResolvedValue({
    criteria: {
      roles: [],
      role_aliases: [],
      seniority: [],
      remote_required: true,
      onsite_locations: [],
      languages: ["en"],
      salary_floor_usd: 0,
      candidate_years: 0,
      candidate_country: "",
      acceptable_regions: ["worldwide"],
      geo_penalty: 12,
      re_apply_window_days: 0,
      shortlist_threshold: 60,
    },
    prose: "",
  });
});

describe("OnboardingPage", () => {
  it("renderiza el wizard de onboarding con datos", async () => {
    renderRoutes("/onboarding");
    expect(await screen.findByText("Tu perfil")).toBeInTheDocument();
  });
});
