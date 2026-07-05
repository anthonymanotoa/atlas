import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    profiles: vi.fn(),
    onboarding: vi.fn(),
    overview: vi.fn(),
    board: vi.fn(),
    settings: vi.fn(),
    setSetting: vi.fn(),
    csvColumns: vi.fn(),
    cvLibrary: vi.fn(),
    renameProfile: vi.fn(),
    exportUrl: (cols?: string[]) => `/api/export?columns=${(cols ?? []).join(",")}`,
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
  api.board.mockResolvedValue({ columns: [], jobs: {}, dismissed: [] });
  api.settings.mockResolvedValue({ download_dir: "/tmp/atlas" });
  api.csvColumns.mockResolvedValue({
    available: [
      { id: "title", label: "Título" },
      { id: "company", label: "Empresa" },
    ],
    selected: ["title"],
  });
  api.cvLibrary.mockResolvedValue({ dir: "/tmp/cvs", count: 2, files: [] });
  api.setSetting.mockResolvedValue({ ok: true, key: "download_dir", value: "/tmp/atlas2" });
});

describe("SettingsPage", () => {
  it("renderiza las cuatro secciones con datos de la API", async () => {
    renderRoutes("/settings");
    expect(await screen.findByText("Nombre de tu perfil")).toBeInTheDocument();
    expect(screen.getByText(/Carpeta de descarga/)).toBeInTheDocument();
    expect(screen.getByText(/Carpeta de tus CVs/)).toBeInTheDocument();
    expect(screen.getByText("Diseño del CSV")).toBeInTheDocument();
    expect(await screen.findByDisplayValue("/tmp/atlas")).toBeInTheDocument();
    expect(await screen.findByText("Título")).toBeInTheDocument();
  });

  it("guardar carpeta llama a setSetting(download_dir)", async () => {
    renderRoutes("/settings");
    const input = await screen.findByDisplayValue("/tmp/atlas");
    await userEvent.clear(input);
    await userEvent.type(input, "/tmp/atlas2");
    await userEvent.click(screen.getByRole("button", { name: "Guardar carpeta" }));
    expect(api.setSetting).toHaveBeenCalledWith("download_dir", "/tmp/atlas2");
  });

  it("guardar diseño persiste las columnas seleccionadas", async () => {
    renderRoutes("/settings");
    await screen.findByText("Título");
    await userEvent.click(screen.getByRole("button", { name: "Guardar diseño" }));
    expect(api.setSetting).toHaveBeenCalledWith("csv_columns", JSON.stringify(["title"]));
  });
});
