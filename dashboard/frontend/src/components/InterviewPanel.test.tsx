import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Interview } from "../api";
import { renderWithQuery } from "../test/utils";
import { TooltipProvider } from "./ui/tooltip";
import { InterviewPanel } from "./InterviewPanel";

// The web only READS interviews and ENQUEUES / saves the debrief (never runs an LLM — $0).
// Mock the whole api module so no network happens and we can assert the exact calls.
const { api } = vi.hoisted(() => ({
  api: {
    interviews: vi.fn(),
    addInterview: vi.fn(),
    addInterviewer: vi.fn(),
    genPrep: vi.fn(),
    enqueueIntent: vi.fn(),
    interviewDebrief: vi.fn(),
  },
}));
vi.mock("../api", () => ({ api }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const withDeepPrep: Interview = {
  id: 5,
  job_id: "j1",
  round: "hiring_manager",
  scheduled_at: "2026-07-10",
  deep_prep_md: "# Prep profundo\n\n## Audience map\n- Hiring manager: ownership stories.",
  debrief_md: null,
  interviewers: [],
};

function render() {
  return renderWithQuery(
    <TooltipProvider>
      <InterviewPanel jobId="j1" />
    </TooltipProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.interviews.mockResolvedValue({ interviews: [withDeepPrep] });
  api.enqueueIntent.mockResolvedValue({ ok: true, id: "in_new" });
  api.interviewDebrief.mockResolvedValue({ ok: true, intent_id: "in_deep" });
});

describe("InterviewPanel — deep prep + debrief", () => {
  it("renderiza el prep profundo persistido y el botón de encolar prep profundo", async () => {
    render();
    // The persisted deep prep markdown is shown verbatim.
    expect(await screen.findByText(/Hiring manager: ownership stories/)).toBeInTheDocument();
    // The deep-prep enqueue button (via IntentConfirmDialog) is offered per interview.
    expect(screen.getByRole("button", { name: /prep profundo \(llm\)/i })).toBeInTheDocument();
  });

  it("guarda el debrief y encola el re-análisis con 'Guardar y re-analizar'", async () => {
    render();
    const textarea = await screen.findByPlaceholderText(/qué preguntaron/i);
    await userEvent.type(textarea, "Preguntaron mucho de SQL.");
    await userEvent.click(screen.getByRole("button", { name: /guardar y re-analizar/i }));
    await waitFor(() =>
      expect(api.interviewDebrief).toHaveBeenCalledWith(5, "Preguntaron mucho de SQL.", true),
    );
  });

  it("guarda el debrief sin re-analizar con 'Guardar debrief'", async () => {
    render();
    const textarea = await screen.findByPlaceholderText(/qué preguntaron/i);
    await userEvent.type(textarea, "Charla corta.");
    await userEvent.click(screen.getByRole("button", { name: /^guardar debrief$/i }));
    await waitFor(() =>
      expect(api.interviewDebrief).toHaveBeenCalledWith(5, "Charla corta.", false),
    );
  });

  it("no llama al backend si el debrief está vacío", async () => {
    render();
    await screen.findByPlaceholderText(/qué preguntaron/i);
    await userEvent.click(screen.getByRole("button", { name: /^guardar debrief$/i }));
    expect(api.interviewDebrief).not.toHaveBeenCalled();
  });
});
