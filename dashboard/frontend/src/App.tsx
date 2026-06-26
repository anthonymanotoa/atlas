import {
  Command as CmdIcon,
  FileText,
  HelpCircle,
  Loader2,
  Moon,
  RefreshCw,
  RotateCcw,
  Search,
  Settings as SettingsIcon,
  Sun,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  api,
  type Action,
  type Job,
  type OnboardingStatus,
  type Overview,
  type Profile,
} from "./api";
import { AnalyticsStrip } from "./components/AnalyticsStrip";
import { Board } from "./components/Board";
import { CommandPalette } from "./components/CommandPalette";
import { CvAuditDialog } from "./components/CvAuditDialog";
import { DetailDrawer } from "./components/DetailDrawer";
import { FilterBar, type Filters } from "./components/FilterBar";
import { HelpGuide } from "./components/HelpGuide";
import { NeedsAction } from "./components/NeedsAction";
import { OnboardingGate } from "./components/OnboardingGate";
import { PortfolioViewer } from "./components/PortfolioViewer";
import { SettingsModal } from "./components/SettingsModal";
import { Button } from "./components/ui/button";
import { Card } from "./components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./components/ui/dialog";
import { DowntimeIcon } from "./components/ui/icons";
import { Kbd } from "./components/ui/kbd";
import { ScrollArea } from "./components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./components/ui/select";
import { Toaster } from "./components/ui/sonner";
import { Tabs, TabsList, TabsTrigger } from "./components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./components/ui/tooltip";

// The discovery sources shown in search progress copy come from the active profile's REAL
// source_health (so they match whatever industry/board set is configured), with a neutral
// fallback before the first overview load.
const SEARCH_SOURCES_FALLBACK = "las fuentes activas de tu perfil";
function searchSourcesLabel(ov: Overview | null): string {
  const names = (ov?.source_health || []).map((s) => s.source).filter(Boolean);
  return names.length > 0 ? names.join(" · ") : SEARCH_SOURCES_FALLBACK;
}

export default function App() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [actions, setActions] = useState<Action[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [jobs, setJobs] = useState<Record<string, Job[]>>({});
  const [dismissed, setDismissed] = useState<Job[]>([]);
  const [showDismissed, setShowDismissed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeProfile, setActiveProfile] = useState<string>("");
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const [brief, setBrief] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [cvOpen, setCvOpen] = useState(false);
  const [view, setView] = useState<"pipeline" | "portfolio">("pipeline");
  const [searching, setSearching] = useState(false);
  const [searchSeconds, setSearchSeconds] = useState(0);
  const [filters, setFilters] = useState<Filters>({
    onlySalary: false,
    language: "",
    maxAgeDays: 0,
  });
  const [theme, setTheme] = useState<string>(() => localStorage.getItem("atlas-theme") || "dark");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("atlas-theme", theme);
  }, [theme]);

  // Open the guide automatically the first time (one-time hint).
  useEffect(() => {
    if (!localStorage.getItem("atlas-guide-seen")) {
      setHelpOpen(true);
      localStorage.setItem("atlas-guide-seen", "1");
    }
  }, []);

  // Live elapsed counter while a search runs, so it's obvious it's working.
  useEffect(() => {
    if (!searching) return;
    setSearchSeconds(0);
    const t = setInterval(() => setSearchSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [searching]);

  const load = useCallback(async () => {
    const [p, ob] = await Promise.all([api.profiles(), api.onboarding()]);
    setProfiles(p.profiles);
    setActiveProfile(p.active);
    setOnboarding(ob);
    if (!ob.complete) return; // onboarding gate: don't load the board until CV+LinkedIn are done
    const [o, b] = await Promise.all([api.overview(), api.board()]);
    setOv(o.overview);
    setActions(o.needs_action);
    setColumns(b.columns);
    setJobs(b.jobs);
    setDismissed(b.dismissed || []);
  }, []);

  const refreshOnboarding = useCallback(async () => {
    setOnboarding(await api.onboarding());
  }, []);

  async function switchProfile(id: string) {
    if (id === activeProfile) return;
    setActiveProfile(id); // optimistic
    await api.switchProfile(id);
    setSelected(null); // a job from the old profile shouldn't stay open
    await load();
  }

  useEffect(() => {
    load();
  }, [load]);

  // Trigger a deterministic discover→score run, then poll until it finishes and refresh.
  const buscarAhora = useCallback(async () => {
    if (searching) return;
    setSearching(true);
    const tid = toast.loading("Buscando vacantes nuevas…", {
      description: `Consultando fuentes y puntuando contra tu CV. ${searchSourcesLabel(ov)}`,
    });
    try {
      await api.discover();
      for (let i = 0; i < 60; i++) {
        // cap polling at ~2 min
        await new Promise((r) => setTimeout(r, 2000));
        const { running } = await api.discoverStatus();
        if (!running) break;
      }
      await load();
      toast.success("Búsqueda completa", {
        id: tid,
        description: "Tablero actualizado. Revisá la columna “Preseleccionados”.",
      });
    } catch {
      toast.error("No se pudo completar la búsqueda", { id: tid });
    } finally {
      setSearching(false);
    }
  }, [searching, load, ov]);

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

  async function move(jobId: string, to: string) {
    setJobs((prev) => {
      // optimistic
      const next: Record<string, Job[]> = {};
      let moved: Job | undefined;
      for (const c of Object.keys(prev)) {
        next[c] = prev[c].filter((j) => {
          if (j.id === jobId) {
            moved = j;
            return false;
          }
          return true;
        });
      }
      if (moved && next[to]) next[to] = [{ ...moved, state: to }, ...next[to]];
      return next;
    });
    await api.setState(jobId, to);
    load();
  }

  // Discard a job the user isn't interested in: drop it off the board, with one-click undo.
  async function dismiss(jobId: string, from: string) {
    setJobs((prev) => {
      const next: Record<string, Job[]> = {};
      for (const c of Object.keys(prev)) next[c] = prev[c].filter((j) => j.id !== jobId);
      return next;
    });
    if (selected === jobId) setSelected(null);
    await api.setState(jobId, "dismissed");
    toast.success("Vacante descartada", {
      description: "No volverá a aparecer en tu tablero.",
      action: {
        label: "Deshacer",
        onClick: async () => {
          await api.setState(jobId, from);
          load();
        },
      },
    });
    load();
  }

  async function restore(jobId: string) {
    setDismissed((prev) => prev.filter((j) => j.id !== jobId));
    await api.setState(jobId, "shortlisted");
    toast.success("Vacante restaurada a Preseleccionados");
    load();
  }

  async function openBrief() {
    const b = await api.brief();
    setBrief(b.markdown);
    setBriefOpen(true);
  }

  const allJobs = Object.values(jobs).flat();
  const languages = Array.from(
    new Set(allJobs.map((j) => j.language).filter((l): l is string => !!l)),
  ).sort();
  const filteredJobs = useMemo(() => {
    const out: Record<string, Job[]> = {};
    for (const c of Object.keys(jobs)) {
      out[c] = jobs[c].filter((j) => {
        const age = j.posted_days ?? j.age_days;
        return (
          (!filters.onlySalary || j.salary_visible) &&
          (!filters.language || j.language === filters.language) &&
          (!filters.maxAgeDays || age == null || age <= filters.maxAgeDays)
        );
      });
    }
    return out;
  }, [jobs, filters]);

  return (
    <TooltipProvider>
      <div className="mx-auto min-h-full max-w-[1500px] px-5 py-4">
        {/* top bar */}
        <header className="sticky top-0 z-40 -mx-5 mb-5 flex items-center justify-between gap-3 border-b border-border/70 bg-background/70 px-5 py-3 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <div
              className="relative grid size-9 place-items-center rounded-xl font-bold text-primary-foreground shadow-[var(--shadow-glow)] before:absolute before:inset-0 before:rounded-xl before:bg-[radial-gradient(circle_at_30%_20%,oklch(1_0_0/0.4),transparent_60%)]"
              style={{
                background: "linear-gradient(135deg, var(--primary), var(--accent2))",
              }}
            >
              A
            </div>
            <div>
              <div className="leading-none font-semibold tracking-tight">Atlas</div>
              <button
                type="button"
                onClick={() => setHelpOpen(true)}
                className="mt-0.5 text-[0.72rem] text-muted-foreground transition-colors hover:text-foreground"
              >
                {ov?.last_run
                  ? `última corrida ${new Date(ov.last_run).toLocaleString("es")}`
                  : "sin corridas"}{" "}
                · cómo funciona
              </button>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {profiles.length > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Select value={activeProfile} onValueChange={switchProfile}>
                    <SelectTrigger size="sm" className="w-auto" aria-label="Perfil activo">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {profiles.map((p) => (
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
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="sm" onClick={buscarAhora} disabled={searching}>
                  {searching ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Search className="size-3.5" />
                  )}
                  {searching ? `Buscando… ${searchSeconds}s` : "Buscar"}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <b>Buscar vacantes</b> — trae ofertas nuevas de todas las fuentes y las puntúa
                contra tu CV (discover + score). Es Python determinista (sin IA), tarda ~1–2 min.
              </TooltipContent>
            </Tooltip>
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
                Paleta de comandos (⌘/Ctrl + K) — saltá a una vacante o acción al instante.
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={() => setHelpOpen(true)}>
                  <HelpCircle className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                Cómo funciona Atlas — guía de todas las funcionalidades y cómo usa la IA.
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={() => setCvOpen(true)}>
                  <FileText className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                Auditoría de tu CV — score y recomendaciones (atlas advise), siempre a mano.
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={() => setSettingsOpen(true)}>
                  <SettingsIcon className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Ajustes y exportar CSV</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
                >
                  {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
                </Button>
              </TooltipTrigger>
              <TooltipContent>Tema claro / oscuro</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={load}>
                  <RefreshCw className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Actualizar el tablero (relee la base de datos local)</TooltipContent>
            </Tooltip>
          </div>
        </header>

        {/* live search progress — so it's obvious Atlas is working */}
        {searching && (
          <Card className="fade-up mb-4 flex items-center gap-3 border-primary/40 p-3.5">
            <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">
                Buscando vacantes nuevas… <span className="tabular-nums">{searchSeconds}s</span>
              </div>
              <div className="truncate text-[0.78rem] text-muted-foreground">
                Consultando fuentes y puntuando contra tu CV · {searchSourcesLabel(ov)}
              </div>
              <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-secondary">
                <div className="h-full w-1/3 animate-[indet_1.2s_ease-in-out_infinite] rounded-full bg-[linear-gradient(90deg,var(--primary),var(--accent2))]" />
              </div>
            </div>
          </Card>
        )}

        {onboarding && !onboarding.complete ? (
          <OnboardingGate status={onboarding} onComplete={load} onRefresh={refreshOnboarding} />
        ) : (
          <>
            <nav className="mb-4">
              <Tabs value={view} onValueChange={(v) => setView(v as "pipeline" | "portfolio")}>
                <TabsList>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
                    </TooltipTrigger>
                    <TooltipContent>
                      Tu embudo de búsqueda: vacantes por estado (preseleccionado → aplicado →
                      entrevista → oferta).
                    </TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <TabsTrigger value="portfolio">Portafolio</TabsTrigger>
                    </TooltipTrigger>
                    <TooltipContent>
                      Generá tu sitio de portafolio local y guardá referencias (peers).
                    </TooltipContent>
                  </Tooltip>
                </TabsList>
              </Tabs>
            </nav>

            {view === "portfolio" ? (
              <PortfolioViewer />
            ) : (
              <>
                {ov?.downtime_hours ? (
                  <Card className="mb-4 flex items-center gap-2 border-warning/50 p-3 text-sm">
                    <DowntimeIcon className="size-4 shrink-0 text-warning" />
                    Estuve sin correr ~{Math.round(ov.downtime_hours)}h. Revisa que el Mac esté
                    despierto y Claude Desktop abierto.
                  </Card>
                ) : null}

                {ov && (
                  <div className="mb-5">
                    <AnalyticsStrip ov={ov} />
                  </div>
                )}

                <div className="mb-6">
                  <NeedsAction actions={actions} onOpen={setSelected} />
                </div>

                <FilterBar filters={filters} setFilters={setFilters} languages={languages} />
                <Board
                  columns={columns}
                  jobs={filteredJobs}
                  onOpen={setSelected}
                  onMove={move}
                  onDismiss={dismiss}
                />

                {dismissed.length > 0 && (
                  <div className="mt-5">
                    <button
                      type="button"
                      onClick={() => setShowDismissed((v) => !v)}
                      className="inline-flex items-center gap-1.5 text-caption text-muted-foreground uppercase transition-colors hover:text-foreground"
                    >
                      <Trash2 className="size-3.5" />
                      Descartadas ({dismissed.length}) {showDismissed ? "▾" : "▸"}
                    </button>
                    {showDismissed && (
                      <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                        {dismissed.map((j) => (
                          <Card
                            key={j.id}
                            className="flex items-center justify-between gap-2 p-3 text-sm"
                          >
                            <button
                              type="button"
                              onClick={() => setSelected(j.id)}
                              className="min-w-0 text-left"
                            >
                              <div className="truncate font-medium">{j.title}</div>
                              <div className="truncate text-xs text-muted-foreground">
                                {j.company}
                              </div>
                            </button>
                            <Button variant="secondary" size="sm" onClick={() => restore(j.id)}>
                              <RotateCcw className="size-3.5" /> Restaurar
                            </Button>
                          </Card>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </>
        )}

        <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
        <HelpGuide open={helpOpen} onOpenChange={setHelpOpen} />
        <CvAuditDialog open={cvOpen} onOpenChange={setCvOpen} />
        <DetailDrawer jobId={selected} onClose={() => setSelected(null)} onChanged={load} />
        <CommandPalette
          open={paletteOpen}
          setOpen={setPaletteOpen}
          jobs={allJobs}
          onOpenJob={setSelected}
          onRefresh={load}
          onBrief={openBrief}
          onSearch={buscarAhora}
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

        <Toaster theme={theme as "dark" | "light"} />
      </div>
    </TooltipProvider>
  );
}
