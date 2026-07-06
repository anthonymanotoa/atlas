import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Intent } from "../api";
import { renderWithQuery } from "../test/utils";
import { BrainTasksPanel, BRAIN_PHRASE } from "./BrainTasksPanel";
import { IntentConfirmDialog } from "./IntentConfirmDialog";

// Mock the whole api module: the web only ever READS the queue and ENQUEUES (never runs an LLM).
const { api } = vi.hoisted(() => ({
  api: { intents: vi.fn(), enqueueIntent: vi.fn() },
}));
vi.mock("../api", () => ({ api }));

// Keep sonner's toast a no-op so tests don't depend on the Toaster being mounted.
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const oneIntent: Intent = {
  id: "in_abc123",
  type: "cv_review",
  job_id: "j1",
  status: "pending",
  created_at: "2026-07-04T09:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  api.intents.mockResolvedValue({ intents: [oneIntent], pending: 1 });
  api.enqueueIntent.mockResolvedValue({ ok: true, id: "in_new999" });
});

describe("BrainTasksPanel", () => {
  it("muestra el badge de pendientes y la frase universal al abrir", async () => {
    renderWithQuery(<BrainTasksPanel />);
    // Badge del conteo de pendientes (viene de useIntents → api.intents()).
    expect(await screen.findByText("1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /tareas del brain/i }));
    // La ÚNICA frase universal que el usuario debe aprenderse.
    expect(await screen.findByText(/corre atlas/)).toBeInTheDocument();
    // El intent listado con su etiqueta humana y su estado en español.
    expect(screen.getByText("Revisión LLM de CV/carta")).toBeInTheDocument();
    expect(screen.getByText("pendiente")).toBeInTheDocument();
  });

  it("expone la frase universal como constante estable", () => {
    expect(BRAIN_PHRASE).toBe("Abre Claude Code en ~/dev/personal/atlas y di: corre atlas");
  });

  it("no muestra el badge cuando no hay pendientes", async () => {
    api.intents.mockResolvedValue({ intents: [], pending: 0 });
    renderWithQuery(<BrainTasksPanel />);
    const btn = await screen.findByRole("button", { name: /tareas del brain/i });
    // El badge (que solo renderiza el número) no debe aparecer con 0 pendientes.
    expect(within(btn).queryByText("0")).not.toBeInTheDocument();
  });
});

describe("IntentConfirmDialog", () => {
  it("muestra qué hace / qué produce / dónde aparece y encola el intent al confirmar", async () => {
    renderWithQuery(
      <IntentConfirmDialog
        buttonLabel="Revisar CV con IA"
        title="Revisión LLM de CV/carta"
        what="analiza tu CV contra la vacante"
        produces="un informe con brechas y sugerencias"
        where="en el panel Tareas del Brain y en la vacante"
        type="cv_review"
        jobId="j1"
        payload={{ job_id: "j1" }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /revisar cv con ia/i }));
    // El diálogo explica las tres cosas obligatorias (spec §7.1).
    expect(await screen.findByText(/analiza tu CV contra la vacante/)).toBeInTheDocument();
    expect(screen.getByText(/un informe con brechas y sugerencias/)).toBeInTheDocument();
    expect(screen.getByText(/en el panel Tareas del Brain y en la vacante/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /encolar para el brain/i }));
    await waitFor(() =>
      expect(api.enqueueIntent).toHaveBeenCalledWith("cv_review", { job_id: "j1" }, "j1"),
    );
  });

  it("llama onQueued con el id devuelto tras encolar", async () => {
    const onQueued = vi.fn();
    renderWithQuery(
      <IntentConfirmDialog
        buttonLabel="Revisar CV con IA"
        title="Revisión LLM de CV/carta"
        what="x"
        produces="y"
        where="z"
        type="cv_review"
        onQueued={onQueued}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /revisar cv con ia/i }));
    await userEvent.click(screen.getByRole("button", { name: /encolar para el brain/i }));
    await waitFor(() => expect(onQueued).toHaveBeenCalledWith("in_new999"));
  });
});

describe("BrainTasksPanel ← encolar actualiza la cola", () => {
  it("refleja el nuevo intent tras encolar (invalidación de la query)", async () => {
    // Primera lectura: vacía. Tras encolar, la invalidación re-lee y ya trae el intent.
    api.intents
      .mockResolvedValueOnce({ intents: [], pending: 0 })
      .mockResolvedValue({ intents: [oneIntent], pending: 1 });

    renderWithQuery(
      <>
        <BrainTasksPanel />
        <IntentConfirmDialog
          buttonLabel="Revisar CV con IA"
          title="Revisión LLM de CV/carta"
          what="x"
          produces="y"
          where="z"
          type="cv_review"
          jobId="j1"
          payload={{ job_id: "j1" }}
        />
      </>,
    );

    // Estado inicial: sin badge.
    const panelBtn = await screen.findByRole("button", { name: /tareas del brain/i });
    expect(within(panelBtn).queryByText("1")).not.toBeInTheDocument();

    // Encolar desde el diálogo.
    await userEvent.click(screen.getByRole("button", { name: /revisar cv con ia/i }));
    await userEvent.click(screen.getByRole("button", { name: /encolar para el brain/i }));
    await waitFor(() => expect(api.enqueueIntent).toHaveBeenCalledTimes(1));

    // La invalidación re-lee la cola → el badge aparece con 1 pendiente.
    expect(await screen.findByText("1", {}, { timeout: 2000 })).toBeInTheDocument();
  });
});
