import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type CsvColumn } from "../api";
import { Button, buttonVariants } from "./ui/button";
import { Checkbox } from "./ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Separator } from "./ui/separator";

// Settings (P1-B): download folder for CLI/brain exports + an editable CSV "design"
// (column selection, persisted per-profile) + a one-click browser CSV download.
export function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [downloadDir, setDownloadDir] = useState("");
  const [available, setAvailable] = useState<CsvColumn[]>([]);
  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    api.settings().then((s) => setDownloadDir(s.download_dir || ""));
    api.csvColumns().then((c) => {
      setAvailable(c.available);
      setSelected(c.selected);
    });
  }, [open]);

  function toggle(id: string) {
    setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]));
  }
  async function saveDir() {
    try {
      const r = await api.setSetting("download_dir", downloadDir);
      setDownloadDir(r.value);
      toast.success("Carpeta guardada");
    } catch {
      toast.error("Ruta inválida");
    }
  }
  async function saveColumns() {
    await api.setSetting("csv_columns", JSON.stringify(selected));
    toast.success("Diseño guardado");
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-[640px] overflow-auto">
        <DialogHeader>
          <DialogTitle>Ajustes</DialogTitle>
          <DialogDescription>Carpeta de descarga y diseño del CSV exportado.</DialogDescription>
        </DialogHeader>

        <section className="mt-1">
          <div className="mb-1 text-sm font-semibold">Carpeta de descarga (CLI / brain)</div>
          <div className="mb-2 text-[0.75rem] text-muted-foreground">
            Dónde guarda <code className="font-mono">atlas export</code>. Desde el navegador, el CSV
            se descarga donde elijas en el diálogo del navegador.
          </div>
          <div className="flex gap-2">
            <Input
              className="flex-1 font-mono text-xs"
              value={downloadDir}
              onChange={(e) => setDownloadDir(e.target.value)}
              placeholder="~/Downloads/atlas"
            />
            <Button variant="secondary" onClick={saveDir}>
              Guardar
            </Button>
          </div>
        </section>

        <Separator className="my-2" />

        <section>
          <div className="mb-1 text-sm font-semibold">Diseño del CSV</div>
          <div className="mb-3 text-[0.75rem] text-muted-foreground">
            Elige las columnas (el orden de selección es el orden del CSV).
          </div>
          <div className="mb-4 grid grid-cols-2 gap-2">
            {available.map((c) => (
              <Label key={c.id} className="cursor-pointer font-normal">
                <Checkbox checked={selected.includes(c.id)} onCheckedChange={() => toggle(c.id)} />
                {c.label}
              </Label>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={saveColumns}>
              Guardar diseño
            </Button>
            <a className={buttonVariants()} href={api.exportUrl(selected)}>
              <Download className="size-4" /> Descargar CSV
            </a>
          </div>
        </section>
      </DialogContent>
    </Dialog>
  );
}
