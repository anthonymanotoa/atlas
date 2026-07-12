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
    enqueueIntent: vi.fn(() => Promise.resolve({ ok: true, id: "in_new" })),
    intents: vi.fn(() => Promise.resolve({ intents: [], pending: 0 })),
    cvReviews: vi.fn(() => Promise.resolve({ reviews: [] })),
    applyCvReviewEdit: vi.fn(() => Promise.resolve({ ok: true })),
    resolveCvReviewFlag: vi.fn(() => Promise.resolve({ ok: true })),
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
      geo_scope: "us",
      geo_restriction: "Remote — US only",
      repost_count: 2,
    },
    cv_versions: [
      { id: 1, language: "en", path_pdf: "a", path_docx: "b", keyword_coverage: 0.6, parse_ok: 1 },
    ],
    messages: [],
    referrals: [],
    learnings: [],
    social_mentions: [],
    timeline: [],
    cv_reviews: [],
    review_report: null,
    company_research: null,
    suggested_contacts: [],
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

  it("muestra los chips de restricción geo y repost en la cabecera", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    expect(screen.getByText("us")).toBeInTheDocument();
    expect(screen.getByText("repost")).toBeInTheDocument();
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

  it("el tab CV muestra la revisión determinista (review.md) cuando está presente", async () => {
    api.job.mockResolvedValue({
      ...jobDetail(),
      review_report:
        "# Revisión determinista del CV\n\n" +
        "- ✅ **Texto extraíble**: 1200 caracteres extraídos del DOCX (mínimo 400)\n" +
        "- ⚠️ **Cobertura de keywords** _(informativo)_: 55% de cobertura — faltan: kubernetes\n",
    });
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "CV" }));
    expect(await screen.findByText("Texto extraíble")).toBeInTheDocument();
    expect(screen.getByText(/1200 caracteres extraídos/)).toBeInTheDocument();
    expect(screen.getByText("Cobertura de keywords")).toBeInTheDocument();
    expect(screen.getByText(/faltan: kubernetes/)).toBeInTheDocument();
  });

  it("sin review_report el tab CV no muestra la sección de revisión determinista", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "CV" }));
    await screen.findByRole("link", { name: /CV PDF/ });
    expect(screen.queryByText("Revisión determinista del CV")).not.toBeInTheDocument();
  });

  it("el tab Research muestra la investigación de la empresa cuando está presente", async () => {
    api.job.mockResolvedValue({
      ...jobDetail(),
      company_research: {
        id: 1,
        company_norm: "acme",
        summary: "Acme is scaling its data platform team.",
        signals: ["hiring surge"],
        sources: ["https://acme.example/blog"],
        researched_at: "2026-07-01T00:00:00Z",
      },
    });
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "Research" }));
    expect(await screen.findByText("Sobre la empresa")).toBeInTheDocument();
    expect(screen.getByText("Acme is scaling its data platform team.")).toBeInTheDocument();
    expect(screen.getByText("hiring surge")).toBeInTheDocument();
  });

  it("el tab Research muestra contactos sugeridos por el brain y permite copiar el borrador", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.assign(navigator, { clipboard: { writeText } });
    api.job.mockResolvedValue({
      ...jobDetail(),
      suggested_contacts: [
        {
          id: 7,
          name: "Jamie Rivera",
          company: "Acme",
          title: "Engineering Manager",
          linkedin_url: "https://linkedin.com/in/jamierivera",
          source: "brain_research",
          notes: "[brain_research] confidence=high; posted about the open role",
        },
      ],
      messages: [
        {
          id: 55,
          job_id: "job-1",
          channel: "referral",
          kind: "referral_or_intro",
          variant: "brain",
          language: "en",
          body: "Hi Jamie, I saw the opening on your team...",
          state: "draft",
        },
      ],
    });
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "Research" }));
    expect(await screen.findByText("Contactos sugeridos")).toBeInTheDocument();
    expect(screen.getByText("Jamie Rivera")).toBeInTheDocument();
    expect(screen.getByText(/confianza high/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Copiar borrador de mensaje/ }));
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith("Hi Jamie, I saw the opening on your team..."),
    );
  });

  it("el tab Mensajes ofrece generar borradores cuando no hay mensajes", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "Mensajes" }));
    await userEvent.click(await screen.findByRole("button", { name: /Generar borradores/ }));
    await waitFor(() => expect(api.prep).toHaveBeenCalledWith("job-1", undefined));
  });

  it("el tab Mensajes encola una carta personalizada para el brain (cover_letter)", async () => {
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "Mensajes" }));
    await userEvent.click(await screen.findByRole("button", { name: /Carta personalizada/ }));
    // El diálogo explica el handoff $0 y el CTA encola el intent tipado a esta vacante.
    await userEvent.click(await screen.findByRole("button", { name: /Encolar para el brain/ }));
    await waitFor(() =>
      expect(api.enqueueIntent).toHaveBeenCalledWith("cover_letter", undefined, "job-1"),
    );
  });

  it("el tab Mensajes muestra la carta que persistió el brain y permite copiarla", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.assign(navigator, { clipboard: { writeText } });
    api.job.mockResolvedValue({
      ...jobDetail(),
      messages: [
        {
          id: 42,
          job_id: "job-1",
          channel: "email",
          kind: "cover_letter",
          variant: "brain",
          language: "en",
          subject: "Application — Senior Data Scientist",
          body: "Hi Acme team, I want to help you ship models.",
          state: "draft",
        },
      ],
    });
    renderRoutes("/jobs/job-1");
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("tab", { name: "Mensajes" }));
    // La MessageCard existente renderiza la carta sin cambios (kind → etiqueta ES + cuerpo).
    expect(await screen.findByText("Carta de presentación")).toBeInTheDocument();
    expect(screen.getByText(/I want to help you ship models/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Copiar/ }));
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith(
        "Application — Senior Data Scientist\n\nHi Acme team, I want to help you ship models.",
      ),
    );
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
