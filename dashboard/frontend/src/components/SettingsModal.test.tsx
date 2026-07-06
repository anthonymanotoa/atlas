import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// vi.hoisted so the mocks exist before vi.mock's hoisted factories reference them.
const { toast, api } = vi.hoisted(() => ({
  toast: { success: vi.fn(), error: vi.fn() },
  api: {
    settings: vi.fn(),
    cvLibrary: vi.fn(),
    profiles: vi.fn(),
    csvColumns: vi.fn(),
    setSetting: vi.fn(),
    renameProfile: vi.fn(),
    exportUrl: vi.fn(() => "/api/export"),
  },
}));
vi.mock("sonner", () => ({ toast }));
vi.mock("../api", () => ({ api }));

import { SettingsModal } from "./SettingsModal";

function settingsFixture() {
  return { download_dir: "~/Downloads/atlas" };
}
function cvLibraryFixture() {
  return { dir: "/cv", count: 3, files: [] };
}
function profilesFixture() {
  return { active: "p1", profiles: [{ id: "p1", label: "Ana" }] };
}
function csvColumnsFixture() {
  return {
    available: [
      { id: "title", label: "Título" },
      { id: "company", label: "Empresa" },
    ],
    selected: ["title"],
  };
}

describe("SettingsModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.settings.mockResolvedValue(settingsFixture());
    api.cvLibrary.mockResolvedValue(cvLibraryFixture());
    api.profiles.mockResolvedValue(profilesFixture());
    api.csvColumns.mockResolvedValue(csvColumnsFixture());
    api.setSetting.mockResolvedValue({ ok: true, key: "download_dir", value: "~/Downloads/atlas" });
    api.renameProfile.mockResolvedValue({ ok: true, id: "p1", label: "Ana" });
  });

  it("loads current values on open", async () => {
    render(<SettingsModal open={true} onClose={() => {}} />);
    await screen.findByDisplayValue("~/Downloads/atlas");
    expect(api.settings).toHaveBeenCalledTimes(1);
    expect(api.cvLibrary).toHaveBeenCalledTimes(1);
    expect(api.profiles).toHaveBeenCalledTimes(1);
    expect(api.csvColumns).toHaveBeenCalledTimes(1);
  });

  it("does not load when closed", () => {
    render(<SettingsModal open={false} onClose={() => {}} />);
    expect(api.settings).not.toHaveBeenCalled();
    expect(api.cvLibrary).not.toHaveBeenCalled();
    expect(api.profiles).not.toHaveBeenCalled();
    expect(api.csvColumns).not.toHaveBeenCalled();
  });

  it("saves the download dir", async () => {
    render(<SettingsModal open={true} onClose={() => {}} />);
    const dirInput = await screen.findByDisplayValue("~/Downloads/atlas");
    await userEvent.clear(dirInput);
    await userEvent.type(dirInput, "~/Desktop/atlas");
    const saveButtons = screen.getAllByRole("button", { name: "Guardar" });
    // First "Guardar" is the profile-name save; second is the download-dir save.
    await userEvent.click(saveButtons[1]);
    await waitFor(() =>
      expect(api.setSetting).toHaveBeenCalledWith("download_dir", "~/Desktop/atlas"),
    );
  });

  it("saves the profile name", async () => {
    render(<SettingsModal open={true} onClose={() => {}} />);
    const nameInput = await screen.findByDisplayValue("Ana");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Ana Lopez");
    const saveButtons = screen.getAllByRole("button", { name: "Guardar" });
    await userEvent.click(saveButtons[0]);
    await waitFor(() => expect(api.renameProfile).toHaveBeenCalledWith("p1", "Ana Lopez"));
  });
});
