import * as Dialog from "@radix-ui/react-dialog";
import { Command as CmdIcon, Loader2, Moon, RefreshCw, Search, Sun, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type Action, type Job, type Overview } from "./api";
import { AnalyticsStrip } from "./components/AnalyticsStrip";
import { Board } from "./components/Board";
import { CommandPalette } from "./components/CommandPalette";
import { DetailDrawer } from "./components/DetailDrawer";
import { NeedsAction } from "./components/NeedsAction";

export default function App() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [actions, setActions] = useState<Action[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [jobs, setJobs] = useState<Record<string, Job[]>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const [brief, setBrief] = useState("");
  const [searching, setSearching] = useState(false);
  const [theme, setTheme] = useState<string>(() => localStorage.getItem("atlas-theme") || "dark");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("atlas-theme", theme);
  }, [theme]);

  const load = useCallback(async () => {
    const [o, b] = await Promise.all([api.overview(), api.board()]);
    setOv(o.overview);
    setActions(o.needs_action);
    setColumns(b.columns);
    setJobs(b.jobs);
  }, []);

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

      {ov?.downtime_hours ? (
        <div className="card p-3 mb-4 text-sm" style={{ borderColor: "var(--color-pending)" }}>
          ⚠️ Estuve sin correr ~{Math.round(ov.downtime_hours)}h. Revisa que el Mac esté despierto y
          Claude Desktop abierto.
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

      <h2 className="text-sm font-semibold tracking-wide mb-2">Pipeline</h2>
      <Board columns={columns} jobs={jobs} onOpen={setSelected} onMove={move} />

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
