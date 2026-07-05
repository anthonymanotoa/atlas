import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { toast, api } = vi.hoisted(() => ({
  toast: { loading: vi.fn(() => "tid"), success: vi.fn(), error: vi.fn() },
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
    job: vi.fn(),
    prep: vi.fn(),
    markApplied: vi.fn(),
    setState: vi.fn(() => Promise.resolve({})),
    markSent: vi.fn(() => Promise.resolve({})),
    cvDownload: vi.fn(() => "/api/cv/job-1/1/download?fmt=pdf"),
    cvLibrary: vi.fn(() => Promise.resolve({ dir: "/cv", count: 0, files: [] })),
    socialMentions: vi.fn(() => Promise.resolve({ mentions: [] })),
    startSocialSearch: vi.fn(() => Promise.resolve({ ok: true, queries: {} })),
    addSocialMention: vi.fn(() => Promise.resolve({ ok: true, id: 1 })),
    interviews: vi.fn(() => Promise.resolve({ interviews: [] })),
    addInterview: vi.fn(() => Promise.resolve({ ok: true, id: 1 })),
    addInterviewer: vi.fn(() => Promise.resolve({ ok: true, id: 1 })),
    genPrep: vi.fn(() => Promise.resolve({ ok: true, path: "", markdown: "" })),
    recordOutcome: vi.fn(() => Promise.resolve({ ok: true, learnings: [] })),
  },
}));
vi.mock("sonner", async (importOriginal) => ({
  ...(await importOriginal<typeof import("sonner")>()),
  toast,
}));
vi.mock("../api", () => ({ api }));

import { renderRoutes } from "../test/utils";

function jobDetail() {
  return {
    job: {
      id: "job-1",
      title: "Senior Data Scientist",
      company: "Acme",
      state: "shortlisted",
      fit_score: 90,
      fit_reasons: ["seniority match: senior"],
      knockout_flags: [],
      is_remote: 1,
      workplace_type: "remote",
      location: "Remote · United States",
      description: "Build models. Run A/B tests.",
      jd_skills: ["python", "sql"],
      language: "en",
      posted_days: 1,
    },
    cv_versions: [
      { id: 1, language: "en", path_pdf: "a", path_docx: "b", keyword_coverage: 0.6, parse_ok: 1 },
    ],
    messages: [],
    referrals: [],
    learnings: [],
    social_mentions: [],
    timeline: [],
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
  api.job.mockResolvedValue(jobDetail());
  api.prep.mockResolvedValue({ ok: true, coverage: 0.6, parse_ok: true, language: "en" });
  api.markApplied.mockResolvedValue({ ok: true });
});

describe("JobDetailPage — página /jobs/:id con tabs", () => {
  it("carga el detalle (título, tabs, descripción y skills en Resumen)", async () => {
    renderRoutes("/jobs/job-1");
    expect(await screen.findByText("Senior Data Scientist")).toBeInTheDocument();
    for (const tab of ["Resumen", "CV", "Mensajes", "Entrevistas", "Research"]) {
      expect(screen.getByRole("tab", { name: tab })).toBeInTheDocument();
    }
    expect(screen.getByText(/Build models/)).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
  });

  it("muestra la transparencia de score (Por qué 90 + razones)", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    expect(screen.getByText(/Por qué 90/)).toBeInTheDocument();
    expect(screen.getByText("seniority match: senior")).toBeInTheDocument();
  });

  it("Re-preparar llama api.prep y muestra toast de éxito", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: /Re-preparar/ }));
    await waitFor(() => expect(api.prep).toHaveBeenCalledWith("job-1", undefined));
    expect(toast.loading).toHaveBeenCalled();
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
  });

  it("Marcar como aplicado llama api.markApplied y toastea", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: /Marcar como aplicado/ }));
    await waitFor(() => expect(api.markApplied).toHaveBeenCalledWith("job-1"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("Descartar pasa el job a dismissed y vuelve al pipeline", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: "Descartar" }));
    await waitFor(() => expect(api.setState).toHaveBeenCalledWith("job-1", "dismissed"));
  });

  it("el tab CV tiene el link real de descarga del PDF", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "CV" }));
    const pdf = await screen.findByRole("link", { name: /CV PDF/ });
    expect(pdf.getAttribute("href")).toMatch(/\/api\/cv\/job-1\/1\/download\?fmt=pdf/);
  });

  it("el tab Mensajes ofrece generar borradores cuando no hay mensajes", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "Mensajes" }));
    await userEvent.click(await screen.findByRole("button", { name: /Generar borradores/ }));
    await waitFor(() => expect(api.prep).toHaveBeenCalledWith("job-1", undefined));
  });

  it("si /api/job falla muestra ErrorState y Reintentar vuelve a pedirlo (recupera al éxito)", async () => {
    api.job.mockRejectedValueOnce(new Error("500"));
    renderRoutes("/jobs/job-1");
    expect(await screen.findByText("No se pudo cargar la vacante")).toBeInTheDocument();
    const retryBtn = screen.getByRole("button", { name: "Reintentar" });

    api.job.mockResolvedValueOnce(jobDetail());
    await userEvent.click(retryBtn);

    expect(await screen.findByText("Senior Data Scientist")).toBeInTheDocument();
    expect(screen.queryByText("No se pudo cargar la vacante")).not.toBeInTheDocument();
  });
});
