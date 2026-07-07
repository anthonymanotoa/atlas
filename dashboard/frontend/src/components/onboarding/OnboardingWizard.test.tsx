import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { OnboardingStatus } from "../../api";

vi.mock("../../api", () => ({
  api: {
    criteria: vi.fn().mockResolvedValue({
      criteria: {
        roles: ["data engineer"],
        role_aliases: [],
        seniority: ["senior"],
        remote_required: true,
        onsite_locations: [],
        languages: ["en", "es"],
        salary_floor_usd: 0,
        candidate_years: 0,
        candidate_country: "",
        acceptable_regions: ["worldwide"],
        geo_penalty: 12,
        re_apply_window_days: 0,
        shortlist_threshold: 60,
      },
      prose: "",
    }),
    profiles: vi.fn().mockResolvedValue({
      active: "owner",
      profiles: [{ id: "owner", label: "Jane Ejemplo" }],
    }),
    saveCriteria: vi.fn().mockResolvedValue({ ok: true, path: "/tmp/criteria.md" }),
    renameProfile: vi.fn().mockResolvedValue({ ok: true, id: "owner", label: "Jane Ejemplo" }),
    completeOnboarding: vi.fn().mockResolvedValue({ ok: true }),
    importCv: vi.fn().mockResolvedValue({ ok: true, draft: "basics:", path: "x", chars: 10 }),
    cvAudit: vi.fn().mockResolvedValue({
      cv_present: false,
      audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
    }),
  },
}));

import { api } from "../../api";
import { OnboardingWizard } from "./OnboardingWizard";

const status: OnboardingStatus = {
  complete: false,
  profile: "owner",
  domain: "data",
  target_label: "",
  cv_present: false,
  audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
};

async function renderWizard(onDone = vi.fn()) {
  render(<OnboardingWizard status={status} onDone={onDone} />);
  await screen.findByText("Tu perfil"); // step 1 heading appears once criteria loaded
  return onDone;
}

describe("OnboardingWizard", () => {
  it("navigates: country step comes after identity", async () => {
    await renderWizard();
    await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
    expect(await screen.findByText("País y regiones")).toBeInTheDocument();
  });

  it("goes back from the country step to the identity step", async () => {
    await renderWizard();
    await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
    expect(await screen.findByText("País y regiones")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Atrás/ }));
    expect(await screen.findByText("Tu perfil")).toBeInTheDocument();
  });

  it("advances through all six steps to the finish button", async () => {
    await renderWizard();
    for (let i = 0; i < 5; i++) {
      await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
    }
    expect(await screen.findByText("Fuentes iniciales")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Finalizar/ })).toBeInTheDocument();
  });

  it("imports a CV on the CV step and shows the returned draft", async () => {
    await renderWizard();
    for (let i = 0; i < 4; i++) {
      await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
    }
    expect(await screen.findByText("Tu CV")).toBeInTheDocument();
    const file = new File(["cv bytes"], "cv.pdf", { type: "application/pdf" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, file);
    await waitFor(() => expect(api.importCv).toHaveBeenCalledWith(file));
    expect(await screen.findByText(/basics:/)).toBeInTheDocument();
  });

  it("saves criteria (with the typed country) and completes onboarding on finish", async () => {
    const onDone = await renderWizard();
    await userEvent.click(screen.getByRole("button", { name: /Siguiente/ })); // → geo
    await userEvent.type(screen.getByLabelText(/País de residencia/), "ec");
    for (let i = 0; i < 4; i++) {
      await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
    }
    await userEvent.click(screen.getByRole("button", { name: /Finalizar/ }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(api.saveCriteria).toHaveBeenCalledWith(
      expect.objectContaining({ candidate_country: "ec" }),
      expect.any(String),
    );
    expect(api.renameProfile).toHaveBeenCalledWith("owner", "Jane Ejemplo");
    expect(api.completeOnboarding).toHaveBeenCalled();
  });

  it("still completes onboarding when the cosmetic profile rename fails", async () => {
    // In legacy mode (no profiles registry yet), POST /api/profiles/owner/label 404s because
    // the virtual owner isn't registered. The display label is cosmetic (settable later in
    // Ajustes, and it self-heals from the CV name), so a rename failure must NOT strand the
    // user on the wizard after criteria + completion have succeeded — the board must unlock.
    vi.mocked(api.renameProfile).mockRejectedValueOnce(new Error("404 unknown profile"));
    const onDone = await renderWizard();
    for (let i = 0; i < 5; i++) {
      await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
    }
    await userEvent.click(screen.getByRole("button", { name: /Finalizar/ }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(api.saveCriteria).toHaveBeenCalled();
    expect(api.completeOnboarding).toHaveBeenCalled();
    expect(api.renameProfile).toHaveBeenCalled();
  });
});
