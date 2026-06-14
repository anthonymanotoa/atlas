import {
  Command as CmdIcon,
  Loader2,
  Moon,
  RefreshCw,
  Search,
  Settings as SettingsIcon,
  Sun,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
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
import { DetailDrawer } from "./components/DetailDrawer";
import { FilterBar, type Filters } from "./components/FilterBar";
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

export default function App() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [actions, setActions] = useState<Action[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [jobs, setJobs] = useState<Record<string, Job[]>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeProfile, setActiveProfile] = useState<string>("");
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const [brief, setBrief] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [view, setView] = useState<"pipeline" | "portfolio">("pipeline");
  const [searching, setSearching] = useState(false);
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
    try {
      await api.discover();
      for (let i = 0; i < 60; i++) {
        // cap polling at ~2 min
        await new Promise((r) => setTimeout(r, 2000));
        const { running } = await api.discoverStatus();
        if (!running) break;
      }
      await load();
    } finally {
      setSearching(false);
    }
  }, [searching, load]);

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
              <div className="mt-0.5 text-[0.72rem] text-muted-foreground">
                {ov?.last_run
                  ? `última corrida ${new Date(ov.last_run).toLocaleString("es")}`
                  : "sin corridas"}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {profiles.length > 0 && (
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
            )}
            <Button
              size="sm"
              onClick={buscarAhora}
              disabled={searching}
              title="Buscar vacantes nuevas (discover + score)"
            >
              {searching ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Search className="size-3.5" />
              )}
              {searching ? "Buscando…" : "Buscar"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setPaletteOpen(true)}
              className="gap-1.5"
            >
              <CmdIcon className="size-3.5" /> <Kbd>K</Kbd>
            </Button>
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
              <TooltipContent>Actualizar</TooltipContent>
            </Tooltip>
          </div>
        </header>

        {onboarding && !onboarding.complete ? (
          <OnboardingGate status={onboarding} onComplete={load} onRefresh={refreshOnboarding} />
        ) : (
          <>
            <nav className="mb-4">
              <Tabs value={view} onValueChange={(v) => setView(v as "pipeline" | "portfolio")}>
                <TabsList>
                  <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
                  <TabsTrigger value="portfolio">Portafolio</TabsTrigger>
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
                <Board columns={columns} jobs={filteredJobs} onOpen={setSelected} onMove={move} />
              </>
            )}
          </>
        )}

        <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
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
