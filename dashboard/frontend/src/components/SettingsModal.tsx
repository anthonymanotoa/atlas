import * as Dialog from "@radix-ui/react-dialog";
import { Download, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type CsvColumn } from "../api";

// Settings (P1-B): download folder for CLI/brain exports + an editable CSV "design"
// (column selection, persisted per-profile) + a one-click browser CSV download.
export function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [downloadDir, setDownloadDir] = useState("");
  const [available, setAvailable] = useState<CsvColumn[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!open) return;
    api.settings().then((s) => setDownloadDir(s.download_dir || ""));
    api.csvColumns().then((c) => {
      setAvailable(c.available);
      setSelected(c.selected);
    });
  }, [open]);

  const flash = (m: string) => {
    setMsg(m);
    setTimeout(() => setMsg(""), 1600);
  };
  function toggle(id: string) {
    setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]));
  }
  async function saveDir() {
    try {
      const r = await api.setSetting("download_dir", downloadDir);
      setDownloadDir(r.value);
      flash("Carpeta guardada");
    } catch {
      flash("Ruta inválida");
    }
  }
  async function saveColumns() {
    await api.setSetting("csv_columns", JSON.stringify(selected));
    flash("Diseño guardado");
  }

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-40" />
        <Dialog.Content className="card fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[640px] max-w-[92vw] -translate-x-1/2 -translate-y-1/2 overflow-auto p-5">
          <div className="mb-4 flex items-center justify-between">
            <Dialog.Title className="font-semibold">Ajustes</Dialog.Title>
            <Dialog.Close className="btn !p-2">
              <X size={16} />
            </Dialog.Close>
          </div>

          <section className="mb-6">
            <div className="mb-1 text-sm font-semibold">Carpeta de descarga (CLI / brain)</div>
            <div className="mb-2 text-[0.75rem] text-[var(--color-muted)]">
              Dónde guarda <code>atlas export</code>. Desde el navegador, el CSV se descarga donde
              elijas en el diálogo del navegador.
            </div>
            <div className="flex gap-2">
              <input
                className="btn !justify-start flex-1 font-mono text-xs"
                value={downloadDir}
                onChange={(e) => setDownloadDir(e.target.value)}
                placeholder="~/Downloads/atlas"
              />
              <button className="btn" onClick={saveDir}>
                Guardar
              </button>
            </div>
          </section>

          <section>
            <div className="mb-1 text-sm font-semibold">Diseño del CSV</div>
            <div className="mb-2 text-[0.75rem] text-[var(--color-muted)]">
              Elige las columnas (el orden de selección es el orden del CSV).
            </div>
            <div className="mb-3 grid grid-cols-2 gap-1">
              {available.map((c) => (
                <label key={c.id} className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selected.includes(c.id)}
                    onChange={() => toggle(c.id)}
                  />
                  {c.label}
                </label>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <button className="btn" onClick={saveColumns}>
                Guardar diseño
              </button>
              <a className="btn btn-accent" href={api.exportUrl(selected)}>
                <Download size={14} /> Descargar CSV
              </a>
              {msg && <span className="text-[0.75rem] text-[var(--color-done)]">{msg}</span>}
            </div>
          </section>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
