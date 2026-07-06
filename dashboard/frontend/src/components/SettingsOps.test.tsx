import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const { toast, api } = vi.hoisted(() => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  api: {
    systemHealth: vi.fn(() =>
      Promise.resolve({
        profile: "owner",
        db: { path: "/tmp/atlas.db", ok: true, jobs: 42 },
        counts: { applied: 3 },
        last_run: "2026-07-04T10:00:00+00:00",
        last_success: "2026-07-04T10:00:00+00:00",
        sources: [
          {
            source: "greenhouse",
            ok: true,
            count: 12,
            run_at: "2026-07-04T10:00:00+00:00",
            error: null,
          },
        ],
        safeguards: { api_key_unset: true, base_url_default: true },
      }),
    ),
    resolveCompany: vi.fn(() =>
      Promise.resolve({
        resolved: true,
        company: "Acme Robotics",
        ats: "greenhouse",
        token: "acmerobotics",
        preview_jobs_count: 3,
        already_configured: false,
      }),
    ),
    addCompany: vi.fn(() => Promise.resolve({ ok: true, added: true })),
    suggestCompanies: vi.fn(() => Promise.resolve({ suggestions: [] })),
    importConnections: vi.fn(() => Promise.resolve({ ok: true, imported: 2 })),
  },
}));
vi.mock("sonner", () => ({ toast }));
vi.mock("../api", () => ({ api }));

import { SettingsOps } from "./SettingsOps";

describe("SettingsOps", () => {
  it("renders system health from /api/system/health", async () => {
    render(<SettingsOps />);
    expect(await screen.findByText(/42 jobs/)).toBeInTheDocument();
    expect(screen.getByText(/greenhouse/)).toBeInTheDocument();
    expect(screen.getByText(/sin fijar/)).toBeInTheDocument();
  });

  it("resolves a careers URL and adds the company", async () => {
    const user = userEvent.setup();
    render(<SettingsOps />);
    await user.type(
      screen.getByPlaceholderText(/boards.greenhouse.io/),
      "https://boards.greenhouse.io/acmerobotics",
    );
    await user.click(screen.getByRole("button", { name: "Detectar" }));
    expect(await screen.findByText("Acme Robotics")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Añadir" }));
    await waitFor(() =>
      expect(api.addCompany).toHaveBeenCalledWith({
        company: "Acme Robotics",
        ats: "greenhouse",
        token: "acmerobotics",
      }),
    );
    expect(toast.success).toHaveBeenCalled();
  });

  it("uploads a Connections.csv via importConnections", async () => {
    const user = userEvent.setup();
    render(<SettingsOps />);
    const file = new File(["First Name,Last Name,Company\nJane,Doe,Acme\n"], "Connections.csv", {
      type: "text/csv",
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);
    await waitFor(() => expect(api.importConnections).toHaveBeenCalledWith(file));
    expect(toast.success).toHaveBeenCalledWith("Importadas 2 conexiones");
  });
});
