import {
  AlarmClock,
  ChartNoAxesColumn,
  Command as CmdIcon,
  FileText,
  Globe,
  HelpCircle,
  Kanban,
  Loader2,
  Moon,
  RefreshCw,
  Search,
  Settings as SettingsIcon,
  Sun,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { api } from "../api";
import { useBoard } from "../hooks/useBoard";
import { useDiscover, searchSourcesLabel } from "../hooks/useDiscover";
import { useOnboarding } from "../hooks/useOnboarding";
import { useOverview } from "../hooks/useOverview";
import { useProfiles, useSwitchProfile } from "../hooks/useProfiles";
import { useTheme } from "../hooks/useTheme";
import { cn } from "../lib";
import { BrainTasksPanel } from "./BrainTasksPanel";
import { CommandPalette } from "./CommandPalette";
import { CvAuditDialog } from "./CvAuditDialog";
import { HelpGuide } from "./HelpGuide";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { UpskillIcon } from "./ui/icons";
import { Kbd } from "./ui/kbd";
import { ScrollArea } from "./ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Toaster } from "./ui/sonner";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

const NAV = [
  { to: "/pipeline", label: "Pipeline", icon: Kanban },
  { to: "/analytics", label: "Analítica", icon: ChartNoAxesColumn },
  { to: "/followups", label: "Follow-ups", icon: AlarmClock },
  { to: "/upskill", label: "Upskilling", icon: UpskillIcon },
  { to: "/portfolio", label: "Portafolio", icon: Globe },
];

export function AppShell() {
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();

  const onboardingQ = useOnboarding();
  const complete = onboardingQ.data?.complete === true;
  const profilesQ = useProfiles();
  const overviewQ = useOverview(complete);
  const boardQ = useBoard(complete);
  const { searching, seconds, run } = useDiscover(overviewQ.data?.overview);

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [cvOpen, setCvOpen] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const [brief, setBrief] = useState("");

  const switchProfile = useSwitchProfile();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Guía abierta la primera vez (one-time hint) — conservado de v1.
  useEffect(() => {
    if (!localStorage.getItem("atlas-guide-seen")) {
      setHelpOpen(true);
      localStorage.setItem("atlas-guide-seen", "1");
    }
  }, []);

  if (onboardingQ.isPending || profilesQ.isPending) {
    return (
      <div className="grid min-h-full place-items-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Guard de onboarding: sin CV listo no hay tablero (paridad con el gate v1).
  if (!complete && location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }
  if (complete && location.pathname === "/onboarding") {
    return <Navigate to="/pipeline" replace />;
  }

  const ov = overviewQ.data?.overview;
  const allJobs = Object.values(boardQ.data?.jobs ?? {}).flat();

  async function openBrief() {
    const b = await api.brief();
    setBrief(b.markdown);
    setBriefOpen(true);
  }

  async function onSwitchProfile(id: string) {
    if (id === profilesQ.data?.active) return;
    await switchProfile.mutateAsync(id);
    navigate("/pipeline");
  }

  return (
    <div className="flex min-h-full">
      {/* ── Sidebar ── */}
      <aside className="sticky top-0 flex h-screen w-52 shrink-0 flex-col border-r border-sidebar-border bg-sidebar px-3 py-4 text-sidebar-foreground max-lg:w-14">
        <div className="mb-6 flex items-center gap-2.5 px-1.5">
          <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary font-bold text-primary-foreground">
            A
          </div>
          <div className="min-w-0 max-lg:hidden">
            <div className="leading-none font-semibold tracking-tight">Atlas</div>
            <button
              type="button"
              onClick={() => setHelpOpen(true)}
              className="mt-0.5 block truncate text-[0.68rem] text-muted-foreground transition-colors hover:text-foreground"
            >
              {ov?.last_run
                ? `corrida ${new Date(ov.last_run).toLocaleDateString("es")}`
                : "sin corridas"}
            </button>
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-active text-sidebar-active-foreground"
                    : "text-muted-foreground hover:bg-sidebar-active/50 hover:text-foreground",
                )
              }
            >
              <Icon className="size-4 shrink-0" />
              <span className="max-lg:hidden">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-1">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-active text-sidebar-active-foreground"
                  : "text-muted-foreground hover:bg-sidebar-active/50 hover:text-foreground",
              )
            }
          >
            <SettingsIcon className="size-4 shrink-0" />
            <span className="max-lg:hidden">Ajustes</span>
          </NavLink>
          <button
            type="button"
            onClick={toggle}
            className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-active/50 hover:text-foreground"
          >
            {theme === "dark" ? (
              <Sun className="size-4 shrink-0" />
            ) : (
              <Moon className="size-4 shrink-0" />
            )}
            <span className="max-lg:hidden">Tema</span>
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex items-center justify-between gap-3 border-b border-border bg-background/80 px-5 py-3 backdrop-blur-xl">
          <div className="flex items-center gap-2">
            {(profilesQ.data?.profiles.length ?? 0) > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Select value={profilesQ.data?.active ?? ""} onValueChange={onSwitchProfile}>
                    <SelectTrigger size="sm" className="w-auto" aria-label="Perfil activo">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {profilesQ.data?.profiles.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          {p.label}
                          {p.is_owner ? " ★" : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TooltipTrigger>
                <TooltipContent>
                  Perfil activo. Cada perfil es una cuenta local con su propio CV, base de datos y
                  configuración.
                </TooltipContent>
              </Tooltip>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="sm" onClick={run} disabled={searching}>
                  {searching ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Search className="size-3.5" />
                  )}
                  {searching ? `Buscando… ${seconds}s` : "Buscar"}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <b>Buscar vacantes</b> — trae ofertas nuevas de todas las fuentes y las puntúa
                contra tu CV (discover + score). Es Python determinista (sin IA), tarda ~1–2 min.
              </TooltipContent>
            </Tooltip>
            <BrainTasksPanel />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPaletteOpen(true)}
                  className="gap-1.5"
                >
                  <CmdIcon className="size-3.5" /> <Kbd>K</Kbd>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                Paleta de comandos (⌘/Ctrl + K) — navega o salta a una vacante al instante.
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={() => setHelpOpen(true)}>
                  <HelpCircle className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Cómo funciona Atlas — guía de funcionalidades.</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={() => setCvOpen(true)}>
                  <FileText className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Auditoría de tu CV — score y recomendaciones.</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={() => qc.invalidateQueries()}>
                  <RefreshCw className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Actualizar (relee la base de datos local)</TooltipContent>
            </Tooltip>
          </div>
        </header>

        {searching && (
          <Card className="fade-up mx-5 mt-4 flex items-center gap-3 border-primary/40 p-3.5">
            <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">
                Buscando vacantes nuevas… <span className="tabular-nums">{seconds}s</span>
              </div>
              <div className="truncate text-[0.78rem] text-muted-foreground">
                Consultando fuentes y puntuando contra tu CV · {searchSourcesLabel(ov)}
              </div>
              <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-secondary">
                <div className="h-full w-1/3 animate-[indet_1.2s_ease-in-out_infinite] rounded-full bg-primary" />
              </div>
            </div>
          </Card>
        )}

        <main className="mx-auto w-full max-w-[1500px] flex-1 px-5 py-4">
          <Outlet />
        </main>
      </div>

      {/* ── Global overlays ── */}
      <HelpGuide open={helpOpen} onOpenChange={setHelpOpen} />
      <CvAuditDialog open={cvOpen} onOpenChange={setCvOpen} />
      <CommandPalette
        open={paletteOpen}
        setOpen={setPaletteOpen}
        jobs={allJobs}
        onNavigate={(to) => navigate(to)}
        onSearch={run}
        onBrief={openBrief}
        onRefresh={() => qc.invalidateQueries()}
      />

      <Dialog open={briefOpen} onOpenChange={setBriefOpen}>
        <DialogContent className="max-w-[640px]">
          <DialogHeader>
            <DialogTitle>Resumen del día</DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[70vh]">
            <pre className="font-sans text-[0.82rem] whitespace-pre-wrap text-foreground">
              {brief}
            </pre>
          </ScrollArea>
        </DialogContent>
      </Dialog>

      <Toaster theme={theme} />
    </div>
  );
}
