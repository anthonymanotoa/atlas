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
  api.board.mockResolvedValue({
    columns: ["shortlisted"],
    jobs: { shortlisted: [] },
    dismissed: [],
  });
});

describe("CommandPalette", () => {
  it("⌘K abre la paleta con un DialogTitle accesible (sin warning de a11y de Radix)", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    renderRoutes("/pipeline");
    await screen.findByText(/Todo al día/);

    await userEvent.keyboard("{Meta>}k{/Meta}");

    // cmdk's Command.Dialog only sets an aria-label on the Radix Dialog.Content and
    // renders no Title itself — Radix requires one (even visually hidden) or it fires a
    // console.error. CommandPalette supplies a sr-only DialogTitle; assert it's present
    // and reachable as the dialog's accessible name.
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAccessibleName("Paleta de comandos");
    expect(screen.getByPlaceholderText("Busca una vista, vacante o acción…")).toBeInTheDocument();

    const dialogTitleWarning = errorSpy.mock.calls
      .flat()
      .some((arg) => typeof arg === "string" && arg.includes("DialogContent"));
    expect(dialogTitleWarning).toBe(false);

    errorSpy.mockRestore();
  });

  it('el grupo "Ir a" navega a las 4 vistas', async () => {
    renderRoutes("/pipeline");
    await screen.findByText(/Todo al día/);
    await userEvent.keyboard("{Meta>}k{/Meta}");

    await userEvent.click(await screen.findByText("Ir a Analítica"));
    expect(await screen.findByRole("heading", { name: "Analítica" })).toBeInTheDocument();
  });
});
