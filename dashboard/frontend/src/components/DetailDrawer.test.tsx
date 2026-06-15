import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "./ui/tooltip";

// Every action button must DO something AND give feedback — the user reported "Re-preparar"
// looked dead. These tests assert the wiring + the feedback (toast) for the action buttons.
// vi.hoisted so the mocks exist before vi.mock's hoisted factories reference them.
const { toast, api } = vi.hoisted(() => ({
  toast: { loading: vi.fn(() => "tid"), success: vi.fn(), error: vi.fn() },
  api: {
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
vi.mock("sonner", () => ({ toast }));
vi.mock("../api", () => ({ api }));

import { DetailDrawer } from "./DetailDrawer";

function jobDetail() {
  return {
    job: {
      id: "job-1",
      title: "Senior Data Scientist",
      company: "Acme",
      state: "shortlisted",
      fit_score: 90,
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

function renderDrawer() {
  return render(
    <TooltipProvider>
      <DetailDrawer jobId="job-1" onClose={() => {}} onChanged={() => {}} />
    </TooltipProvider>,
  );
}

describe("DetailDrawer action buttons all do something + give feedback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.job.mockResolvedValue(jobDetail());
    api.prep.mockResolvedValue({ ok: true, coverage: 0.6, parse_ok: true, language: "en" });
    api.markApplied.mockResolvedValue({ ok: true });
  });

  it("loads the job detail (país, skills, descripción)", async () => {
    renderDrawer();
    expect(await screen.findByText("Senior Data Scientist")).toBeInTheDocument();
    expect(screen.getByText(/Build models/)).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
  });

  it("Re-preparar calls api.prep and shows a success toast", async () => {
    renderDrawer();
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: /Re-preparar/ }));
    await waitFor(() => expect(api.prep).toHaveBeenCalledWith("job-1"));
    expect(toast.loading).toHaveBeenCalled();
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
  });

  it("Marcar como aplicado calls api.markApplied and toasts", async () => {
    renderDrawer();
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: /Marcar como aplicado/ }));
    await waitFor(() => expect(api.markApplied).toHaveBeenCalledWith("job-1"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("Descartar sets the job to dismissed", async () => {
    renderDrawer();
    await screen.findByText("Senior Data Scientist");
    await userEvent.click(screen.getByRole("button", { name: "Descartar" }));
    await waitFor(() => expect(api.setState).toHaveBeenCalledWith("job-1", "dismissed"));
  });

  it("the CV PDF download is a real, confined download link", async () => {
    renderDrawer();
    await screen.findByText("Senior Data Scientist");
    const pdf = screen.getByRole("link", { name: /CV PDF/ });
    expect(pdf.getAttribute("href")).toMatch(/\/api\/cv\/job-1\/1\/download\?fmt=pdf/);
  });
});
