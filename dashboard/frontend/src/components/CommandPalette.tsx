import { Command } from "cmdk";
import { FileText, RefreshCw, Search, Sparkles } from "lucide-react";
import type { Job } from "../api";
import { STATE_ES } from "../lib";

export function CommandPalette({
  open, setOpen, jobs, onOpenJob, onRefresh, onBrief, onSearch,
}: {
  open: boolean;
  setOpen: (o: boolean) => void;
  jobs: Job[];
  onOpenJob: (id: string) => void;
  onRefresh: () => void;
  onBrief: () => void;
  onSearch: () => void;
}) {
  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Atlas command palette"
      className="fixed inset-0 z-[60] flex items-start justify-center pt-[12vh]"
      overlayClassName="fixed inset-0 bg-black/50 backdrop-blur-[2px] z-[59]"
      contentClassName="relative z-[61]"
    >
      <div className="card w-[560px] max-w-[92vw] overflow-hidden shadow-2xl">
        <div className="flex items-center gap-2 px-3 border-b border-[var(--color-border)]">
          <Search size={16} className="text-[var(--color-faint)]" />
          <Command.Input
            autoFocus
            placeholder="Busca una vacante, empresa o acción…"
            className="w-full bg-transparent outline-none py-3 text-sm"
          />
        </div>
        <Command.List className="max-h-[50vh] overflow-auto p-2">
          <Command.Empty className="px-3 py-6 text-center text-sm text-[var(--color-muted)]">
            Sin resultados.
          </Command.Empty>
          <Command.Group heading="Acciones" className="text-[0.7rem] text-[var(--color-faint)] px-2">
            <Item onSelect={() => { onSearch(); setOpen(false); }} icon={<Sparkles size={14} />} text="Buscar vacantes nuevas" />
            <Item onSelect={() => { onRefresh(); setOpen(false); }} icon={<RefreshCw size={14} />} text="Actualizar tablero" />
            <Item onSelect={() => { onBrief(); setOpen(false); }} icon={<FileText size={14} />} text="Abrir resumen del día" />
          </Command.Group>
          <Command.Group heading="Vacantes" className="text-[0.7rem] text-[var(--color-faint)] px-2 mt-1">
            {jobs.map((j) => (
              <Item
                key={j.id}
                onSelect={() => { onOpenJob(j.id); setOpen(false); }}
                text={`${j.title} — ${j.company}`}
                hint={`${j.fit_score ?? "—"} · ${STATE_ES[j.state] || j.state}`}
              />
            ))}
          </Command.Group>
        </Command.List>
      </div>
    </Command.Dialog>
  );
}

function Item({ onSelect, text, icon, hint }: { onSelect: () => void; text: string; icon?: React.ReactNode; hint?: string }) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm cursor-pointer text-[var(--color-fg)] data-[selected=true]:bg-[var(--color-panel2)]"
    >
      {icon}
      <span className="flex-1 truncate">{text}</span>
      {hint && <span className="text-[0.72rem] text-[var(--color-faint)]">{hint}</span>}
    </Command.Item>
  );
}
