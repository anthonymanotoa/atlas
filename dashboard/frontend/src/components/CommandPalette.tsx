import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Command as CmdkCommand } from "cmdk";
import {
  ChartNoAxesColumn,
  FileText,
  Globe,
  Kanban,
  RefreshCw,
  Settings as SettingsIcon,
  Sparkles,
} from "lucide-react";
import type { Job } from "../api";
import { STATE_ES } from "../lib";
import { UpskillIcon } from "./ui/icons";
import {
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "./ui/command";

const GOTO = [
  { to: "/pipeline", label: "Ir a Pipeline", icon: Kanban },
  { to: "/analytics", label: "Ir a Analítica", icon: ChartNoAxesColumn },
  { to: "/upskill", label: "Ir a Upskilling", icon: UpskillIcon },
  { to: "/portfolio", label: "Ir a Portafolio", icon: Globe },
  { to: "/settings", label: "Ir a Ajustes", icon: SettingsIcon },
];

export function CommandPalette({
  open,
  setOpen,
  jobs,
  onNavigate,
  onSearch,
  onBrief,
  onRefresh,
}: {
  open: boolean;
  setOpen: (o: boolean) => void;
  jobs: Job[];
  onNavigate: (to: string) => void;
  onSearch: () => void;
  onBrief: () => void;
  onRefresh: () => void;
}) {
  const go = (fn: () => void) => () => {
    fn();
    setOpen(false);
  };
  return (
    <CmdkCommand.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Atlas command palette"
      className="fixed inset-0 z-[80] flex items-start justify-center pt-[12vh]"
      overlayClassName="fixed inset-0 z-[79] bg-black/55 backdrop-blur-[3px]"
      contentClassName="relative z-[81]"
    >
      <div className="w-[600px] max-w-[92vw] overflow-hidden rounded-xl border border-border bg-popover text-popover-foreground shadow-[var(--shadow-lg)]">
        {/* cmdk's Command.Dialog renders a bare Radix Dialog.Content with only an
            aria-label — Radix still requires a Title descendant for a11y, so we
            supply one here, visually hidden (sr-only), plus a description. */}
        <DialogPrimitive.Title className="sr-only">Paleta de comandos</DialogPrimitive.Title>
        <DialogPrimitive.Description className="sr-only">
          Busca una vista, vacante o acción y navega al instante.
        </DialogPrimitive.Description>
        <CommandInput autoFocus placeholder="Busca una vista, vacante o acción…" />
        <CommandList>
          <CommandEmpty>Sin resultados.</CommandEmpty>
          <CommandGroup heading="Ir a">
            {GOTO.map(({ to, label, icon: Icon }) => (
              <CommandItem key={to} value={label} onSelect={go(() => onNavigate(to))}>
                <Icon /> {label}
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Acciones">
            <CommandItem value="buscar vacantes nuevas" onSelect={go(onSearch)}>
              <Sparkles /> Buscar vacantes nuevas
            </CommandItem>
            <CommandItem value="actualizar tablero" onSelect={go(onRefresh)}>
              <RefreshCw /> Actualizar tablero
            </CommandItem>
            <CommandItem value="abrir resumen del dia" onSelect={go(onBrief)}>
              <FileText /> Abrir resumen del día
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Vacantes">
            {jobs.map((j) => (
              <CommandItem
                key={j.id}
                value={`${j.title} ${j.company} ${j.id}`}
                onSelect={go(() => onNavigate(`/jobs/${j.id}`))}
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
