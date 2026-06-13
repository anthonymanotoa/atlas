import * as Dialog from "@radix-ui/react-dialog";
import {
  Command as CmdIcon,
  Loader2,
  Moon,
  RefreshCw,
  Search,
  Settings as SettingsIcon,
  Sun,
  X,
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
    <div className="min-h-full px-5 py-4 max-w-[1500px] mx-auto">
      {/* top bar */}
      <header className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center font-bold"
            style={{
              background: "linear-gradient(135deg, var(--color-accent), var(--color-accent2))",
              color: "#0d0d12",
            }}
          >
            A
          </div>
          <div>
            <div className="font-semibold leading-none">Atlas</div>
            <div className="text-[0.72rem] text-[var(--color-faint)]">
              {ov?.last_run
                ? `última corrida ${new Date(ov.last_run).toLocaleString("es")}`
                : "sin corridas"}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {profiles.length > 0 && (
            <select
              className="btn !py-1.5 cursor-pointer"
              title="Perfil activo"
              value={activeProfile}
              onChange={(e) => switchProfile(e.target.value)}
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                  {p.is_owner ? " ★" : ""}
                </option>
              ))}
            </select>
          )}
          <button
            className="btn !py-1.5"
            title="Buscar vacantes nuevas (discover + score)"
            onClick={buscarAhora}
            disabled={searching}
          >
            {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
            {searching ? "Buscando…" : "Buscar"}
          </button>
          <button className="btn !py-1.5" onClick={() => setPaletteOpen(true)}>
            <CmdIcon size={14} /> K
          </button>
          <button
            className="btn !py-1.5"
            title="Ajustes y exportar CSV"
            onClick={() => setSettingsOpen(true)}
          >
            <SettingsIcon size={14} />
          </button>
          <button
            className="btn !py-1.5"
            title="Tema claro / oscuro"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          >
            {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
          </button>
          <button className="btn !py-1.5" onClick={load}>
            <RefreshCw size={14} />
          </button>
        </div>
      </header>

      {onboarding && !onboarding.complete ? (
        <OnboardingGate status={onboarding} onComplete={load} onRefresh={refreshOnboarding} />
      ) : (
        <>
          <nav className="mb-4 flex gap-2">
            {(["pipeline", "portfolio"] as const).map((v) => (
              <button
                key={v}
                className="btn !py-1.5"
                style={view === v ? { borderColor: "var(--color-accent)" } : undefined}
                onClick={() => setView(v)}
              >
                {v === "pipeline" ? "Pipeline" : "Portafolio"}
              </button>
            ))}
          </nav>

          {view === "portfolio" ? (
            <PortfolioViewer />
          ) : (
            <>
              {ov?.downtime_hours ? (
                <div
                  className="card p-3 mb-4 text-sm"
                  style={{ borderColor: "var(--color-pending)" }}
                >
                  ⚠️ Estuve sin correr ~{Math.round(ov.downtime_hours)}h. Revisa que el Mac esté
                  despierto y Claude Desktop abierto.
                </div>
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

      <Dialog.Root open={briefOpen} onOpenChange={setBriefOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 card w-[640px] max-w-[92vw] max-h-[80vh] overflow-auto p-5">
            <div className="flex items-center justify-between mb-3">
              <Dialog.Title className="font-semibold">Resumen del día</Dialog.Title>
              <Dialog.Close className="btn !p-2">
                <X size={16} />
              </Dialog.Close>
            </div>
            <pre className="text-[0.82rem] whitespace-pre-wrap font-sans text-[var(--color-fg)]">
              {brief}
            </pre>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
