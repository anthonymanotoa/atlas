import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ProfileExpansion } from "../api";
import { renderWithQuery } from "../test/utils";
import { ProfileExpandSection } from "./ProfileExpandSection";

// La sección SOLO lee el borrador que el brain produjo y aplica los ítems confirmados (por
// índice). apply es determinista ($0). Mockeamos api entero (el hook + IntentConfirmDialog lo usan).
const { api } = vi.hoisted(() => ({
  api: { profileExpansions: vi.fn(), applyProfileExpansion: vi.fn(), enqueueIntent: vi.fn() },
}));
vi.mock("../api", () => ({ api }));
const { toast } = vi.hoisted(() => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));
vi.mock("sonner", () => ({ toast }));

const EXPANSION: ProfileExpansion = {
  id: 7,
  created_at: "2026-07-06T10:00:00",
  items: [
    { target: "skills", value: "Rust", source: "github.com/ada" },
    {
      target: "certification",
      value: { name: "CKA", issuer: "CNCF", date: "2026" },
      source: "cncf.io/cka",
    },
    { target: "skills", value: "Python", source: "github (ya existe)", applied: true },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ProfileExpandSection", () => {
  it("muestra el estado vacío cuando no hay propuestas", async () => {
    api.profileExpansions.mockResolvedValue({ expansions: [] });
    renderWithQuery(<ProfileExpandSection />);
    expect(await screen.findByText(/Sin propuestas/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Escanear y proponer/ })).toBeInTheDocument();
  });

  it("renderiza cada ítem con su target y fuente; los ya aplicados salen marcados", async () => {
    api.profileExpansions.mockResolvedValue({ expansions: [EXPANSION] });
    renderWithQuery(<ProfileExpandSection />);
    expect(await screen.findByText("Rust")).toBeInTheDocument();
    expect(screen.getByText("CKA")).toBeInTheDocument();
    expect(screen.getByText(/github\.com\/ada/)).toBeInTheDocument();
    // el ítem ya aplicado se muestra como tal
    expect(screen.getByText("Aplicado")).toBeInTheDocument();
  });

  it("aplica SOLO los ítems confirmados (por índice)", async () => {
    api.profileExpansions.mockResolvedValue({ expansions: [EXPANSION] });
    api.applyProfileExpansion.mockResolvedValue({ ok: true, applied: 1, skipped_existing: 0 });
    renderWithQuery(<ProfileExpandSection />);
    await screen.findByText("Rust");

    // marcar solo el primer ítem (Rust) — el checkbox del ya-aplicado está deshabilitado
    const checkboxes = screen.getAllByRole("checkbox");
    await userEvent.click(checkboxes[0]);
    await userEvent.click(screen.getByRole("button", { name: /Aplicar seleccionados \(1\)/ }));

    await waitFor(() => expect(api.applyProfileExpansion).toHaveBeenCalledWith(7, [0]));
    expect(toast.success).toHaveBeenCalled();
  });

  it("el botón aplicar está deshabilitado sin selección", async () => {
    api.profileExpansions.mockResolvedValue({ expansions: [EXPANSION] });
    renderWithQuery(<ProfileExpandSection />);
    await screen.findByText("Rust");
    expect(screen.getByRole("button", { name: /Aplicar seleccionados \(0\)/ })).toBeDisabled();
  });
});
