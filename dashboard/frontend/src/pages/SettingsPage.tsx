import { Copy, Download, FolderOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../api";
import { Button, buttonVariants } from "../components/ui/button";
import { Checkbox } from "../components/ui/checkbox";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Separator } from "../components/ui/separator";
import { ErrorState, LoadingState } from "../components/ui/states";
import { useCsvColumns, useCvLibrary, useSetSetting, useSettings } from "../hooks/useSettings";
import { useProfiles, useRenameProfile } from "../hooks/useProfiles";
import { copy } from "../lib";

export function SettingsPage() {
  const settingsQ = useSettings();
  const columnsQ = useCsvColumns();
  const cvLibQ = useCvLibrary();
  const profilesQ = useProfiles();
  const setSetting = useSetSetting();
  const renameProfile = useRenameProfile();

  const [downloadDir, setDownloadDir] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [profileLabel, setProfileLabel] = useState("");

  // Semilla de formularios desde las queries (una vez cargadas).
  useEffect(() => {
    if (settingsQ.data) setDownloadDir(settingsQ.data.download_dir || "");
  }, [settingsQ.data]);
  useEffect(() => {
    if (columnsQ.data) setSelected(columnsQ.data.selected);
  }, [columnsQ.data]);
  useEffect(() => {
    if (profilesQ.data) {
      setProfileLabel(
        profilesQ.data.profiles.find((x) => x.id === profilesQ.data.active)?.label || "",
      );
    }
  }, [profilesQ.data]);

  if (settingsQ.isPending || columnsQ.isPending || profilesQ.isPending) {
    return <LoadingState rows={3} className="mx-auto max-w-[640px]" />;
  }
  if (settingsQ.isError) {
    return (
      <div className="mx-auto max-w-[640px]">
        <ErrorState onRetry={() => settingsQ.refetch()} />
      </div>
    );
  }

  const activeId = profilesQ.data?.active ?? "";

  async function saveProfileName() {
    if (!activeId || !profileLabel.trim()) return;
    try {
      const r = await renameProfile.mutateAsync({ id: activeId, label: profileLabel.trim() });
      setProfileLabel(r.label);
      toast.success("Nombre del perfil guardado");
    } catch {
      toast.error("No se pudo guardar el nombre");
    }
  }

  function toggleColumn(id: string) {
    setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]));
  }

  async function saveDir() {
    try {
      const r = await setSetting.mutateAsync({ key: "download_dir", value: downloadDir });
      setDownloadDir(r.value);
      toast.success("Carpeta guardada");
    } catch {
      toast.error("Ruta inválida");
    }
  }

  async function saveColumns() {
    await setSetting.mutateAsync({ key: "csv_columns", value: JSON.stringify(selected) });
    toast.success("Diseño guardado");
  }

  const cvLib = cvLibQ.data;

  return (
    <div className="mx-auto max-w-[640px]">
      <h1 className="mb-1 text-h1">Ajustes</h1>
      <p className="mb-5 text-sm text-muted-foreground">
        Perfil, carpeta de descarga y diseño del CSV exportado.
      </p>

      <section className="mt-1">
        <div className="mb-1 text-sm font-semibold">Nombre de tu perfil</div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Cómo se llama tu perfil en el selector de arriba.
        </div>
        <div className="flex gap-2">
          <Input
            className="flex-1"
            value={profileLabel}
            onChange={(e) => setProfileLabel(e.target.value)}
            placeholder="Tu nombre"
          />
          <Button variant="secondary" onClick={saveProfileName}>
            Guardar nombre
          </Button>
        </div>
      </section>

      <Separator className="my-4" />

      <section>
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
            Guardar carpeta
          </Button>
        </div>
      </section>

      <Separator className="my-4" />

      <section>
        <div className="mb-1 flex items-center gap-1.5 text-sm font-semibold">
          <FolderOpen className="size-3.5" /> Carpeta de tus CVs
        </div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Cada CV que preparas se guarda aquí, con un nombre por empresa y puesto (
          <code className="font-mono">Nombre__Empresa__Puesto__idioma.pdf</code>).
        </div>
        {cvLib && (
          <div className="flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded-md bg-secondary px-2 py-1.5 font-mono text-[0.72rem] whitespace-nowrap">
              {cvLib.dir}
            </code>
            <span className="text-[0.72rem] whitespace-nowrap text-muted-foreground">
              {cvLib.count} {cvLib.count === 1 ? "archivo" : "archivos"}
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                await copy(cvLib.dir);
                toast.success("Ruta copiada");
              }}
            >
              <Copy className="size-3.5" /> Copiar ruta
            </Button>
          </div>
        )}
      </section>

      <Separator className="my-4" />

      <section>
        <div className="mb-1 text-sm font-semibold">Diseño del CSV</div>
        <div className="mb-3 text-[0.75rem] text-muted-foreground">
          Elige las columnas (el orden de selección es el orden del CSV).
        </div>
        <div className="mb-4 grid grid-cols-2 gap-2">
          {(columnsQ.data?.available ?? []).map((c) => (
            <Label key={c.id} className="cursor-pointer font-normal">
              <Checkbox
                checked={selected.includes(c.id)}
                onCheckedChange={() => toggleColumn(c.id)}
              />
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
    </div>
  );
}
