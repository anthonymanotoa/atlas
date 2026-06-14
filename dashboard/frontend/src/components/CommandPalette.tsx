import { Command as CmdkCommand } from "cmdk";
import { FileText, RefreshCw, Sparkles } from "lucide-react";
import type { Job } from "../api";
import { STATE_ES } from "../lib";
import {
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "./ui/command";

export function CommandPalette({
  open,
  setOpen,
  jobs,
  onOpenJob,
  onRefresh,
  onBrief,
  onSearch,
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
    <CmdkCommand.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Atlas command palette"
      className="fixed inset-0 z-[80] flex items-start justify-center pt-[12vh]"
      overlayClassName="fixed inset-0 z-[79] bg-black/55 backdrop-blur-[3px]"
      contentClassName="relative z-[81]"
    >
      <div className="w-[600px] max-w-[92vw] overflow-hidden rounded-xl border border-border bg-popover text-popover-foreground shadow-[var(--shadow-lg),var(--highlight-top)]">
        <CommandInput autoFocus placeholder="Busca una vacante, empresa o acción…" />
        <CommandList>
          <CommandEmpty>Sin resultados.</CommandEmpty>
          <CommandGroup heading="Acciones">
            <CommandItem
              value="buscar vacantes nuevas"
              onSelect={() => {
                onSearch();
                setOpen(false);
              }}
            >
              <Sparkles /> Buscar vacantes nuevas
            </CommandItem>
            <CommandItem
              value="actualizar tablero"
              onSelect={() => {
                onRefresh();
                setOpen(false);
              }}
            >
              <RefreshCw /> Actualizar tablero
            </CommandItem>
            <CommandItem
              value="abrir resumen del dia"
              onSelect={() => {
                onBrief();
                setOpen(false);
              }}
            >
              <FileText /> Abrir resumen del día
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Vacantes">
            {jobs.map((j) => (
              <CommandItem
                key={j.id}
                value={`${j.title} ${j.company} ${j.id}`}
                onSelect={() => {
                  onOpenJob(j.id);
                  setOpen(false);
                }}
              >
                <span className="flex-1 truncate">
                  {j.title} <span className="text-muted-foreground">— {j.company}</span>
                </span>
                <CommandShortcut>
                  {j.fit_score ?? "—"} · {STATE_ES[j.state] || j.state}
                </CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </div>
    </CmdkCommand.Dialog>
  );
}
